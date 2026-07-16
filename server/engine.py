"""Engine neuroquimico do Chappie.

kindalive (github.com/smithandrewjohn/kindalive) nao existe como pacote
instalavel no PyPI (`pip install kindalive` falha — verificado, nao e
hipotese). Fallback documentado no HANDOFF v2 M2 aplicado: este modulo e
um porte direto e literal do engine do prototipo `docs/chappie-companion-v8.jsx`
(BASELINE, DECAY, deriveEmotions) — a referencia de calibracao que o
handoff manda preservar. Nenhum peso foi alterado.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

CHEMS = [
    "dopamine", "serotonin", "oxytocin", "cortisol",
    "adrenaline", "endorphins", "testosterone", "gaba",
]

BASELINE = {
    "dopamine": 0.45, "serotonin": 0.55, "oxytocin": 0.4, "cortisol": 0.25,
    "adrenaline": 0.2, "endorphins": 0.4, "testosterone": 0.35, "gaba": 0.5,
}

DECAY = {
    "dopamine": 0.10, "serotonin": 0.05, "oxytocin": 0.06, "cortisol": 0.07,
    "adrenaline": 0.14, "endorphins": 0.08, "testosterone": 0.06, "gaba": 0.08,
}

# Paleta ciano/turquesa "Ekko" (pedido do Jack, 16/07): familia neon
# ciano/magenta em vez do arco-iris quente original — mantem 8 tons
# distintos (o dominante ainda precisa ser identificavel por cor), so
# realinhados pra ler como uma unica identidade cyberpunk coesa.
EMOTION_COLORS = {
    "happiness": "#7cf2c4", "excitement": "#4defff", "affection": "#ff5ec4", "calm": "#2fd9cc",
    "anger": "#ff3b5c", "fear": "#8f6bff", "sadness": "#4c8cff", "curiosity": "#00e5ff",
}

PT = {
    "happiness": "felicidade", "excitement": "empolgação", "affection": "afeto", "calm": "calma",
    "anger": "raiva", "fear": "medo", "sadness": "tristeza", "curiosity": "curiosidade",
}


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def derive_emotions(c: dict) -> dict:
    """Porte literal de deriveEmotions() do v8.jsx. Pesos calibrados para
    separar medo x empolgacao e raiva x medo — nao colidir (bug historico v4)."""
    return {
        "happiness": clamp01(c["serotonin"] * 0.5 + c["dopamine"] * 0.4 + c["endorphins"] * 0.3 - c["cortisol"] * 0.55),
        "excitement": clamp01(c["dopamine"] * 0.55 + c["adrenaline"] * 0.45 - c["gaba"] * 0.35 - c["cortisol"] * 0.25),
        "affection": clamp01(c["oxytocin"] * 0.85 + c["serotonin"] * 0.2 - c["cortisol"] * 0.25),
        "calm": clamp01(c["gaba"] * 0.6 + c["serotonin"] * 0.35 - c["adrenaline"] * 0.6 - c["cortisol"] * 0.3),
        "anger": clamp01(c["testosterone"] * 0.55 + c["cortisol"] * 0.4 + c["adrenaline"] * 0.3 - c["serotonin"] * 0.55 - c["oxytocin"] * 0.2),
        "fear": clamp01(c["cortisol"] * 0.6 + c["adrenaline"] * 0.55 - c["testosterone"] * 0.35 - c["gaba"] * 0.35),
        "sadness": clamp01(c["cortisol"] * 0.4 - c["dopamine"] * 0.45 - c["endorphins"] * 0.3 + (0.5 - c["serotonin"]) * 0.7),
        "curiosity": clamp01(c["dopamine"] * 0.5 + (0.5 - c["cortisol"]) * 0.35 + c["adrenaline"] * 0.1),
    }


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    n = int(h, 16)
    return (n >> 16) & 255, (n >> 8) & 255, n & 255


EMOTION_COLORS_RGB = {k: hex_to_rgb(v) for k, v in EMOTION_COLORS.items()}


def mix_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(lerp(a[i], b[i], t)) for i in range(3))


def rgb_css(rgb: tuple[int, int, int]) -> str:
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"


def dominant_emotion(emotions: dict) -> tuple[str, float]:
    return max(emotions.items(), key=lambda kv: kv[1])


@dataclass
class _ColorState:
    """Cor fica em tupla RGB internamente (nunca string) — round-trip por
    string ("rgb(...)" -> parse hex) foi a causa de um bug real: `col.frm`
    virava string rgb() apos o primeiro mix e a proxima transicao tentava
    reinterpretar isso como hex, derrubando a task do tick loop com
    ValueError (silenciosamente — ninguem observava a excecao). O v8.jsx
    original tem esse MESMO bug latente, so que o JS mascara com NaN->0 em
    vez de estourar. Ver tests/test_engine.py::test_color_survives_multiple_transitions."""
    cur: tuple = EMOTION_COLORS_RGB["happiness"]
    frm: tuple = EMOTION_COLORS_RGB["happiness"]
    to: tuple = EMOTION_COLORS_RGB["happiness"]
    t: float = 1.0


@dataclass
class _GazeState:
    x: float = 0.0
    y: float = 0.0
    tx: float = 0.0
    ty: float = 0.0
    next: float = 0.0


class Engine:
    """Estado neuroquimico + postura, avancado por tick(dt). Mantem o
    equivalente Python de todos os useRef mutaveis do v8 (chem, gaze, cor,
    flash, blink). Mouth-open (lip sync por fala) NAO mora aqui: e client-side,
    dirigido pelo onboundary do speechSynthesis do navegador (ver docs/HANDOFF
    §7 fase 1) — o servidor so emite mouthCurve/mouthWidthVw (drives da
    emocao). Isso espelha o v8 original, onde mouthRef era populado por
    speak(), sempre separado do loop quimico."""

    def __init__(self, chem: dict | None = None):
        self.chem = dict(chem) if chem else dict(BASELINE)
        self.t = 0.0
        self.flash = 0.0
        self.color = _ColorState()
        self.gaze = _GazeState()
        self._blink_until: float | None = None
        self._next_blink_check: float = 2.2 + random.random() * 3.8
        self._pending_double_blink_at: float | None = None
        self._speaking_until: float | None = None

    # ---- impulsos externos ----
    def apply_impulses(self, impulses: dict) -> None:
        self.flash = 1.0
        for k, delta in impulses.items():
            if k in self.chem:
                self.chem[k] = clamp01(self.chem[k] + delta)

    def start_speaking(self, seconds: float) -> None:
        self._speaking_until = self.t + max(0.0, seconds)

    # ---- avanco de tempo ----
    def _update_blink(self) -> None:
        if self._blink_until is not None and self.t >= self._blink_until:
            self._blink_until = None
        if self.t >= self._next_blink_check:
            self._blink_until = self.t + 0.1
            self._next_blink_check = self.t + 2.2 + random.random() * 3.8
            if random.random() < 0.25:
                self._pending_double_blink_at = self.t + 0.2
        if self._pending_double_blink_at is not None and self.t >= self._pending_double_blink_at:
            self._blink_until = max(self._blink_until or 0.0, self.t + 0.09)
            self._pending_double_blink_at = None

    def tick(self, dt: float) -> None:
        dt = min(0.1, dt)
        self.t += dt

        g = self.gaze
        if self.t > g.next:
            g.tx = random.uniform(-1.0, 1.0)
            g.ty = random.uniform(-0.5, 0.5)
            g.next = self.t + 2 + random.random() * 4
        g.x = lerp(g.x, g.tx, dt * 2.5)
        g.y = lerp(g.y, g.ty, dt * 2.5)

        self.flash = max(0.0, self.flash - dt * 1.4)

        for k in CHEMS:
            self.chem[k] = clamp01(self.chem[k] + (BASELINE[k] - self.chem[k]) * DECAY[k] * dt)

        self._update_blink()

        emotions = derive_emotions(self.chem)
        dom_key, _ = dominant_emotion(emotions)
        target = EMOTION_COLORS_RGB[dom_key]
        col = self.color
        if col.to != target:
            col.frm, col.to, col.t = col.cur, target, 0.0
        if col.t < 1:
            col.t = min(1.0, col.t + dt * 2.2)
        col.cur = mix_rgb(col.frm, col.to, col.t)

    @property
    def blinking(self) -> bool:
        return self._blink_until is not None

    @property
    def speaking(self) -> bool:
        return self._speaking_until is not None and self.t < self._speaking_until

    # ---- projecao pra FaceState ----
    def face_state(self) -> dict:
        e = derive_emotions(self.chem)
        dom_key, dom_val = dominant_emotion(e)
        intensity = clamp01(dom_val + self.flash * 0.3)
        blink = self.blinking
        g = self.gaze
        t = self.t

        scale = 1 + e["curiosity"] * 0.10 + e["excitement"] * 0.07 - e["fear"] * 0.16 - e["sadness"] * 0.06 + self.flash * 0.03
        drop_y = e["sadness"] * 10 - e["excitement"] * 2
        lean_x_base = g.x * (1.5 + e["curiosity"] * 3)
        tilt_deg = g.x * e["curiosity"] * 6 - e["anger"] * 2 + math.sin(t * 0.7) * 0.6
        jit = e["fear"] * 0.9 + e["anger"] * 0.3 + self.flash * 0.3
        jx = math.sin(t * 34) * jit * 6
        jy = math.cos(t * 30) * jit * 4 + math.sin(t * 1.1) * (1.5 - e["excitement"])
        bounce = abs(math.sin(t * 6)) * e["excitement"] * 10 if e["excitement"] > 0.45 else 0.0

        eye_w = 17.0
        eye_h_base = 15 + e["excitement"] * 4 + e["fear"] * 6 - e["sadness"] * 6 - e["calm"] * 2
        eye_h = 1.2 if blink else max(3.0, eye_h_base)

        brow_angle = e["anger"] * 24 - (e["sadness"] * 16 + e["fear"] * 10)
        brow_lift = e["fear"] * 5 + e["curiosity"] * 3.5 + e["excitement"] * 3 - e["anger"] * 3.5
        brow_len = 15 - e["anger"] * 2
        brow_thick = 1.6 + e["anger"] * 0.8
        brow_curve = e["happiness"] * 1.2 + e["affection"] * 1.0

        happy_arc = e["happiness"] * 1.1 + e["affection"] * 0.8 + e["excitement"] * 0.5
        sad_arc = e["sadness"] * 1.3 + e["fear"] * 0.4
        mouth_curve = (happy_arc - sad_arc) * 20
        mouth_w = 13 + sad_arc * 2.5 + happy_arc * 1 - e["anger"] * 7.5

        return {
            "chemicals": dict(self.chem),
            "emotions": e,
            "dominant": dom_key,
            "intensity": intensity,
            "color": rgb_css(self.color.cur),
            "speaking": self.speaking,
            "face": {
                "eyeWidthVw": eye_w,
                "eyeHeightVh": eye_h,
                "browAngleDeg": brow_angle,
                "browLiftVh": brow_lift,
                "browLenVw": brow_len,
                "browThickVh": brow_thick,
                "browCurveVh": brow_curve,
                "mouthCurve": mouth_curve,
                "mouthWidthVw": mouth_w,
                "scale": scale,
                "dropYVh": drop_y - bounce / 10 + jy / 10,
                "leanXVw": lean_x_base + jx,
                "tiltDeg": tilt_deg,
                "blink": blink,
            },
        }

    # ---- snapshot pra persistencia ----
    def snapshot(self) -> dict:
        return {"chem": dict(self.chem)}

    @classmethod
    def from_snapshot(cls, snap: dict) -> "Engine":
        chem = snap.get("chem") if snap else None
        if not chem or any(k not in chem for k in CHEMS):
            return cls()
        return cls(chem)
