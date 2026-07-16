"""FastAPI: WS /face (~20Hz), POST /say, GET /neuro, GET /health, GET / (renderer).
O engine roda num tick loop de fundo independente de clientes conectados
(o "humor" precisa evoluir mesmo sem ninguem olhando)."""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, persistence
from .engine import Engine
from .interpreter import interpret
from .schemas import NeuroSnapshot, SayRequest, SayResponse

logger = logging.getLogger("chappie")

RENDERER_DIR = config.REPO_ROOT / "renderer"

state: dict = {
    "engine": None,
    "history": [],
    "startup_ok": False,
    "startup_error": None,
    "started_at": None,
    "tick_task": None,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine, history = _load_engine_and_history()
    state["engine"] = engine
    state["history"] = history
    state["started_at"] = time.time()
    ok, err = _self_check()
    state["startup_ok"] = ok
    state["startup_error"] = err
    if not ok:
        logger.warning("self-check falhou no boot: %s", err)
    state["tick_task"] = asyncio.create_task(_tick_loop())
    try:
        yield
    finally:
        state["tick_task"].cancel()
        try:
            await state["tick_task"]
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

    return SayResponse(reply=result["reply"], impulses=result["impulses"])


@app.websocket("/face")
async def face_ws(ws: WebSocket):
    await ws.accept()
    dt = 1.0 / config.TICK_HZ
    try:
        while True:
            await ws.send_json(state["engine"].face_state())
            await asyncio.sleep(dt)
    except WebSocketDisconnect:
        pass


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
