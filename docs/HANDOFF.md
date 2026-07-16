# CHAPPIE COMPANION — Handoff de Design → Build (Claude Code)

> Documento de orquestração. Consolida todas as decisões de design validadas
> no protótipo (v1→v8) e define a arquitetura de produção 100% on-device.
> Protótipo de referência: `chappie-companion-v8.jsx` (React artifact).

---

## 1. Conceito

Companion device físico usando um Samsung Galaxy Note 8 com capinha armor azul
(kickstand) como corpo. A tela É o rosto — estética Chappie minimalista.
Emoções não são labels: são **projeções de um estado neuroquímico simulado**
(modelo kindalive), alimentado pelo Claude, que interpreta a fala do usuário
em impulsos químicos. Conversa contínua por voz, mãos livres.

Referência conceitual: `github.com/smithandrewjohn/kindalive` (MIT).
Pipeline: fala → LLM Interpreter (Claude) → ChemicalImpulse[] → Engine
(decay/integração) → Emotion Projection → FaceState → Renderer.

## 2. Arquitetura de produção (tudo no Note 8)

```
┌────────────────── Note 8 ──────────────────┐
│ Termux (wake-lock, sem battery optimization)│
│  └─ Python 3: kindalive core + FastAPI/    │
│     aiohttp em localhost:8000               │
│     ├─ engine químico (tick contínuo,      │
│     │  estado persiste entre sessões)      │
│     ├─ POST /say  → chama API Anthropic    │
│     │  (impulsos + reply), aplica no engine│
│     ├─ WS /face   → stream FaceState+cor   │
│     └─ GET /neuro → snapshot químicos      │
│                                             │
│ Chrome kiosk → http://localhost:8000        │
│  └─ renderer (HTML/JS, portado da v8)      │
│     ├─ SpeechRecognition pt-BR (mic)       │
│     ├─ speechSynthesis (TTS Android)       │
│     └─ desenha rosto a partir do WS        │
└─────────────────────────────────────────────┘
        │ única saída externa
        ▼
   api.anthropic.com
```

Decisões:
- **Nada roda na máquina de automações.** Note 8 autossuficiente + API key.
- `localhost` = secure context → mic/áudio OK sem HTTPS.
- Estado químico vive no Python (não no browser): sobrevive a reload da
  página e permite humor de longo prazo (kindalive suporta short/long-term).
- Persistência: JSON em disco a cada N segundos (estado químico + histórico).
- Guard de sanidade: relógio do engine com sub-stepping (usar o do kindalive).

Setup Termux (referência):
```
pkg install python
pip install kindalive fastapi uvicorn
termux-wake-lock
# battery optimization OFF para Termux e Chrome
# Chrome: "Adicionar à tela inicial" da URL localhost → abre sem barra
```

## 3. Contrato FaceState (renderer-agnostic)

O servidor emite via WebSocket a ~20 Hz:

```json
{
  "chemicals":  { "dopamine": 0.62, "...": 0 },
  "emotions":   { "happiness": 0.71, "...": 0 },
  "dominant":   "happiness",
  "color":      "#ffb545",
  "face": {
    "eyeOpen": 0.8, "browAngle": -0.1, "browLift": 0.3,
    "mouthCurve": 0.6, "mouthOpen": 0.0,
    "scale": 1.05, "dropY": 0.0, "jitter": 0.0, "tilt": 0.1
  },
  "speaking": false
}
```

Todos os floats 0..1 (ou -1..1 onde indicado). O renderer não conhece
químicos — só consome `face` + `color`. Compatível com a filosofia do
kindalive (mesmos floats podem dirigir hardware físico no futuro).

## 4. Especificação visual (validada no protótipo)

Fundo: `#000` puro (funde com a bezel). Fonte UI: Chakra Petch.

### Paleta emocional (cor = canal primário de emoção)
| emoção      | hex      |
|-------------|----------|
| felicidade  | #ffb545  |
| empolgação  | #ffd23e  |
| afeto       | #ff7ab8  |
| calma       | #5fd4c4  |
| raiva       | #ff4b2e  |
| medo        | #b48cff  |
| tristeza    | #5c8fd6  |
| curiosidade | #7ee0ff  |

Transição de cor: crossfade RGB contínuo (~0.45s), nunca troca seca.
Glow (box-shadow) escala com intensidade da emoção dominante + "flash"
de 1.0 decaindo em ~0.7s a cada impulso recebido.

### Olhos (puros — sem rotação, sem pupila)
- Dois retângulos arredondados, ~17vw × (15±Δ)vh, gap 13vw, cor plena C.
- Altura: +empolgação/medo, −tristeza/calma. Piscada: 1.2vh por 100ms,
  intervalo 2.2–6s, 25% de chance de piscada dupla.

### Sobrancelhas (canal de expressão facial principal)
- Barras ~15vw × 1.6vh acima dos olhos, pivô no canto EXTERNO.
- Raiva: pontas internas descem (rot ±24° máx), engrossam (+0.8vh),
  encurtam (−2vw), colam no olho (gap −3.5vh).
- Tristeza/medo: pontas internas sobem (rot −16°/−10°).
- Medo/surpresa: disparam pra cima (gap +5vh). Curiosidade: +3.5vh.
- Felicidade/afeto: translateY suave pra cima (arqueadas relaxadas).
- Transição: cubic-bezier(.34,1.3,.64,1) 220ms — o overshoot é expressão.

### Boca (parábola emocional — ATENÇÃO ao eixo Y do SVG)
- Path: `M 10,30 Q 100,(30+curve−open) 190,30 Q 100,(30+curve+open) 10,30 Z`
  em viewBox 200×60, largura container ~13vw.
- `curve = (happyArc − sadArc) × 20` → **+ = ∪ sorriso (a>0), − = ∩ tristeza**.
  (Bug histórico v7: sinal invertido por causa do y-down do SVG. Não repetir.)
- Tristeza: parábola ∩ mais AMPLA (largura +2.5vw).
- Raiva: hífen — largura despenca pra ~5.5vw, curva ~0. Transição de
  largura 350ms (o "comprimir" é parte da expressão).
- Fala: `open` separa as duas quadráticas em torno da espinha emocional
  (fala sorrindo / fala triste). Aberta: fill preto, stroke C.

### Postura (linguagem corporal do conjunto)
- Curiosidade: scale +10%, inclina cabeça seguindo olhar (gaze wander).
- Medo: recua (scale −16%) + tremor 30Hz.
- Tristeza: despenca (translateY +10vh).
- Empolgação >0.45: pulinhos (|sin| 6Hz).
- Idle: respiração senoidal ~1.1Hz sutil.

### UI mínima
- 1 botão: mic (58px, base). Ligado: preenchido C, pulsa ao escutar.
- Etiqueta da emoção dominante (topo-direita) → toque abre painel
  neuroquímico (8 químicos + 8 emoções, barras ao vivo). Toque fecha.
- Nada mais na tela.

## 5. Modelo químico (baseline do protótipo — substituir pelo kindalive real)

O protótipo usa engine próprio simplificado; no build, usar o engine do
kindalive (decay, interações entre químicos, sub-stepping) e mapear as
projeções. Valores do protótipo como referência de calibração:

- Baseline: dop .45 / ser .55 / oxy .40 / cor .25 / adr .20 / end .40 / tes .35 / gaba .50
- Decay por segundo (fração da distância ao baseline): adr .14 (mais rápido),
  ser .05 (mais lento). Emoção deve persistir 15–20s após impulso forte.
- Projeções de emoção: ver `deriveEmotions()` na v8 (pesos calibrados para
  separar medo × empolgação e raiva × medo — não colidir).

## 6. LLM Interpreter (Claude)

- Endpoint: Messages API, modelo Sonnet (custo/latência) — chamado pelo
  servidor Python, nunca pelo browser (API key fica no Termux, env var).
- Prompt retorna JSON estrito: `{"impulses": {...}, "reply": "..."}`.
  Deltas -0.7..0.7, 2–5 químicos, instruir expressividade (≥0.3).
- Contexto: estado químico atual + últimas 8 trocas do histórico.
- Personalidade: curiosa e ingênua, pt-BR, respostas ≤25 palavras.
- Parse defensivo: strip de fences, try/catch, fallback "interferência".

## 7. Voz

Fase 1 (browser): SpeechRecognition pt-BR contínuo + speechSynthesis
(pitch 0.75). Lip sync por `onboundary` (pulso por palavra, energia
proporcional ao tamanho da palavra, decay 5.5/s, vibrato 17Hz enquanto
há energia). Auto-mute do mic durante a fala, re-arma no onend.

Fase 2 (upgrade, no Termux): `edge-tts` gera áudio pt-BR de qualidade →
servidor serve o WAV → browser toca via WebAudio + AnalyserNode →
lip sync por amplitude REAL. Vale também avaliar STT melhor (Vosk small
pt-BR roda offline em Termux) se o SpeechRecognition do Chrome decepcionar.

## 8. Riscos & mitigação

| risco | mitigação |
|---|---|
| Android mata o Termux | wake-lock + battery opt. off + `termux-services` |
| Chrome recicla a aba | kiosk via "tela inicial", `keep screen on` (Fully Kiosk como plano B) |
| onboundary não dispara no TTS Samsung | fallback: estimar ritmo pelo texto (palavras/rate); fase 2 resolve |
| Burn-in AMOLED (rosto estático) | micro-drift lento de posição (±1vw a cada poucos min) — já existe via gaze/respiração; adicionar drift do conjunto |
| Latência API percebida | animação "pensando" (olhos oscilam) durante busy |
| Custo API | Sonnet + max_tokens baixo; opcional Haiku para trocas triviais |

## 9. Milestones

- **M1** — Porta do renderer v8 para HTML/JS vanilla servido pelo Python;
  engine químico ainda em JS. Kiosk funcionando no Note 8. (validação física)
- **M2** — Engine migra pro Python (kindalive real), WS /face, estado
  persistente, API key no servidor. Browser vira renderer burro.
- **M3** — Voz fase 2 (edge-tts + lip sync por amplitude), STT avaliado,
  drift anti-burn-in, autostart no boot (Termux:Boot).

## 10. Decisões fechadas (não reabrir sem motivo)

1. Corpo físico = capinha armor + kickstand existente. Sem impressão 3D.
2. Estética minimalista Chappie: 2 olhos + 2 sobrancelhas + boca parábola.
3. Cor = canal emocional primário; sobrancelha = expressão; postura = intensidade.
4. Sem boca no formato "equalizer"; parábola com abertura simétrica.
5. Feliz = ∪ (a>0). Triste = ∩ ampla. Raiva = hífen curto.
6. Emoções emergem de químicos (kindalive), nunca labels diretas.
7. Voz como interface primária; um único botão (mic).
8. Neuroquímica inspecionável via toque na etiqueta de emoção.
9. Infra 100% on-device (Termux no Note 8); única dependência externa = API Anthropic.
