"""FastAPI: WS /face (~20Hz), POST /say, GET /neuro, GET /health, GET / (renderer).
O engine roda num tick loop de fundo independente de clientes conectados
(o "humor" precisa evoluir mesmo sem ninguem olhando)."""
from __future__ import annotations

import asyncio
import logging
import os
import random
import subprocess
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, persistence
from .engine import Engine
from .interpreter import interpret, interpret_initiative
from .schemas import NeuroSnapshot, SayRequest, SayResponse
from .tts import synthesize

logger = logging.getLogger("chappie")

RENDERER_DIR = config.REPO_ROOT / "renderer"

INITIATIVE_HISTORY_MARKER = "[silêncio prolongado]"

state: dict = {
    "engine": None,
    "history": [],
    "startup_ok": False,
    "startup_error": None,
    "started_at": None,
    "tick_task": None,
    "initiative_task": None,
    "ws_clients": 0,
    "last_interaction_at": 0.0,
    "initiative_threshold_s": 0.0,
    "pending_initiative": None,
    "initiative_seq": 0,
}


def _load_engine_and_history() -> tuple[Engine, list]:
    snap = persistence.load(config.STATE_PATH)
    history = list(snap.get("history", [])) if snap else []
    engine = Engine.from_snapshot(snap or {})
    return engine, history


def _self_check() -> tuple[bool, str | None]:
    if config.MOCK_LLM:
        return True, None
    if not config.ANTHROPIC_API_KEY:
        return False, "ANTHROPIC_API_KEY ausente — defina no .env ou exporte antes de subir o server"
    return True, None


def _persist_now() -> None:
    eng = state["engine"]
    if eng is None:
        return
    persistence.save({"chem": eng.chem, "history": state["history"]}, config.STATE_PATH)


async def _tick_loop() -> None:
    dt = 1.0 / config.TICK_HZ
    last_persist = time.monotonic()
    while True:
        state["engine"].tick(dt)
        now = time.monotonic()
        if now - last_persist >= config.PERSIST_INTERVAL_S:
            _persist_now()
            last_persist = now
        await asyncio.sleep(dt)


def _roll_initiative_threshold() -> float:
    return random.uniform(config.INITIATIVE_MIN_S, config.INITIATIVE_MAX_S)


async def _maybe_fire_initiative() -> None:
    """Decide se o Chappie puxa assunto sozinho (pedido do Jack 16/07): so
    dispara com pelo menos 1 cliente WS conectado e depois de um silencio
    >= limiar sorteado (reamostrado a cada disparo — pausa nunca fixa).
    Extraida do loop pra ser testavel direto, sem esperar wall-clock real."""
    if state["ws_clients"] <= 0 or not state["startup_ok"]:
        return
    if time.monotonic() - state["last_interaction_at"] < state["initiative_threshold_s"]:
        return

    eng = state["engine"]
    result = await interpret_initiative(eng.chem, state["history"])
    state["last_interaction_at"] = time.monotonic()
    state["initiative_threshold_s"] = _roll_initiative_threshold()
    if result is None:
        return

    eng.apply_impulses(result["impulses"])
    state["history"].append({"role": "user", "content": INITIATIVE_HISTORY_MARKER})
    state["history"].append({"role": "assistant", "content": result["reply"]})
    max_msgs = config.HISTORY_MAX_TURNS * 2
    if len(state["history"]) > max_msgs:
        state["history"] = state["history"][-max_msgs:]

    word_count = len(result["reply"].split())
    eng.start_speaking(word_count / 2.5 + 0.3)

    state["initiative_seq"] += 1
    state["pending_initiative"] = {"id": state["initiative_seq"], "text": result["reply"]}


async def _initiative_loop() -> None:
    if not config.INITIATIVE_ENABLED:
        return
    while True:
        await asyncio.sleep(config.INITIATIVE_POLL_S)
        await _maybe_fire_initiative()


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine, history = _load_engine_and_history()
    state["engine"] = engine
    state["history"] = history
    state["started_at"] = time.time()
    state["last_interaction_at"] = time.monotonic()
    state["initiative_threshold_s"] = _roll_initiative_threshold()
    state["pending_initiative"] = None
    state["ws_clients"] = 0
    ok, err = _self_check()
    state["startup_ok"] = ok
    state["startup_error"] = err
    if not ok:
        logger.warning("self-check falhou no boot: %s", err)
    state["tick_task"] = asyncio.create_task(_tick_loop())
    state["initiative_task"] = asyncio.create_task(_initiative_loop())
    try:
        yield
    finally:
        for task_key in ("tick_task", "initiative_task"):
            task = state[task_key]
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        _persist_now()


app = FastAPI(lifespan=lifespan)

if RENDERER_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(RENDERER_DIR)), name="assets")


@app.get("/")
async def root():
    index = RENDERER_DIR / "index.html"
    if not index.exists():
        return {"error": "renderer/index.html nao encontrado"}
    return FileResponse(str(index))


@app.get("/health")
async def health():
    eng = state["engine"]
    return {
        "ok": state["startup_ok"],
        "error": state["startup_error"],
        "mock_llm": config.MOCK_LLM,
        "uptime_s": round(time.time() - state["started_at"], 1) if state["started_at"] else None,
        "engine_t": round(eng.t, 1) if eng else None,
    }


@app.get("/neuro", response_model=NeuroSnapshot)
async def neuro():
    from .engine import derive_emotions, dominant_emotion

    eng = state["engine"]
    emotions = derive_emotions(eng.chem)
    dom_key, _ = dominant_emotion(emotions)
    return NeuroSnapshot(chemicals=eng.chem, emotions=emotions, dominant=dom_key)


@app.post("/say", response_model=SayResponse)
async def say(req: SayRequest):
    eng = state["engine"]
    result = await interpret(req.text, eng.chem, state["history"])
    eng.apply_impulses(result["impulses"])

    state["history"].append({"role": "user", "content": req.text})
    state["history"].append({"role": "assistant", "content": result["reply"]})
    max_msgs = config.HISTORY_MAX_TURNS * 2
    if len(state["history"]) > max_msgs:
        state["history"] = state["history"][-max_msgs:]

    word_count = len(result["reply"].split())
    eng.start_speaking(word_count / 2.5 + 0.3)

    # Interacao real empurra a proxima fala espontanea pra frente (nao faz
    # sentido puxar assunto sozinho logo depois de uma conversa de verdade).
    state["last_interaction_at"] = time.monotonic()

    return SayResponse(reply=result["reply"], impulses=result["impulses"])


@app.post("/tts")
async def tts(req: SayRequest):
    audio = await synthesize(req.text)
    if audio is None:
        raise HTTPException(status_code=502, detail="sintese de voz indisponivel")
    return Response(content=audio, media_type="audio/mpeg")


@app.websocket("/face")
async def face_ws(ws: WebSocket):
    await ws.accept()
    state["ws_clients"] += 1
    dt = 1.0 / config.TICK_HZ
    try:
        while True:
            payload = state["engine"].face_state()
            # "initiative" nao faz parte do contrato FaceState (HANDOFF §3) —
            # e um extra pro cliente detectar fala espontanea por mudanca de
            # id, nunca validado contra FaceStateModel (extra="forbid" e so
            # pro shape puro do engine, ver tests/test_contract.py).
            payload["initiative"] = state["pending_initiative"]
            await ws.send_json(payload)
            await asyncio.sleep(dt)
    except WebSocketDisconnect:
        pass
    finally:
        state["ws_clients"] -= 1


def _schedule_restart(delay_s: float = 1.0) -> None:
    """So sai do processo — quem sobe de novo e o supervisor runit
    (deploy/chappie.service), ja lendo o codigo atualizado do git pull."""
    asyncio.get_event_loop().call_later(delay_s, lambda: os._exit(0))


@app.post("/admin/update")
async def admin_update(request: Request):
    """git pull + restart remoto (HANDOFF §5). So funciona com
    CHAPPIE_ADMIN_TOKEN configurado; sem token, o endpoint fica desativado.
    So faz pull de codigo — deps novas exigem `bash deploy/update.sh`."""
    if not config.ADMIN_TOKEN or request.headers.get("X-Admin-Token", "") != config.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="token invalido ou admin desabilitado")

    result = subprocess.run(
        ["git", "-C", str(config.REPO_ROOT), "pull", "--ff-only"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"git pull falhou: {result.stderr[:500]}")

    _persist_now()
    _schedule_restart()
    return {"pulled": result.stdout.strip(), "restarting_in_s": 1}
