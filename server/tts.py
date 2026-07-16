"""TTS server-side (HANDOFF v2, voz fase 2). edge-tts gera a voz base
(Antonio, unica opcao masculina pt-BR) e um pos-processo via ffmpeg da o
timbre "androide de cinema" aprovado pelo Jack (16/07): camada harmonica
grave em quinta + aguda em quinta + toque de oitava, amarradas com chorus
leve — sem distorcao/growl, testado contra 6 variantes antes de fechar
nesta (ver scratch_voice/ na maquina de dev).

ffmpeg precisa ser buildado com --enable-librubberband (confirmado no
build.sh oficial do termux-packages — instala via `pkg install ffmpeg`
sem passo extra)."""
from __future__ import annotations

import asyncio
import logging
import time

import edge_tts

from . import config

logger = logging.getLogger("chappie")

# Filtro fixo (nao e parametro de runtime — e a identidade sonora do
# personagem, igual ao SYSTEM_PROMPT). Camadas: principal + quinta grave
# (profundidade/metalico) + quinta aguda (calor melodico) + oitava aguda
# bem sutil (brilho), mixadas e amarradas com chorus leve.
_VOICE_FILTER = (
    "[0:a]volume=1.0[main];"
    "[0:a]rubberband=pitch=0.667,volume=0.28[fifth_low];"
    "[0:a]rubberband=pitch=1.5,volume=0.20[fifth_high];"
    "[0:a]rubberband=pitch=2.0,volume=0.08[oct_high];"
    "[main][fifth_low][fifth_high][oct_high]amix=inputs=4:duration=first:dropout_transition=0:normalize=0,"
    "chorus=0.4:0.8:45:0.25:0.2:1.5,"
    "alimiter=limit=0.95"
)

_EDGE_TTS_TIMEOUT_S = 15.0
_FFMPEG_TIMEOUT_S = 15.0


async def _edge_tts_bytes(text: str) -> bytes:
    comm = edge_tts.Communicate(text, voice=config.TTS_VOICE, rate=config.TTS_RATE, pitch=config.TTS_PITCH)
    chunks = []
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


async def _ffmpeg_postprocess(mp3_bytes: bytes) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "mp3", "-i", "pipe:0",
        "-filter_complex", _VOICE_FILTER,
        "-f", "mp3", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=mp3_bytes)
    if proc.returncode != 0 or not stdout:
        raise RuntimeError(f"ffmpeg falhou (code={proc.returncode}): {stderr[-500:]!r}")
    return stdout


async def synthesize(text: str) -> bytes | None:
    """None em qualquer falha (edge-tts fora do ar, ffmpeg ausente, timeout)
    — quem chama decide o fallback (HTTP 502), nunca deixa a excecao subir."""
    if not text or not text.strip():
        return None

    t_start = time.monotonic()
    try:
        raw = await asyncio.wait_for(_edge_tts_bytes(text), timeout=_EDGE_TTS_TIMEOUT_S)
    except Exception:
        logger.exception("edge-tts falhou (voice=%s)", config.TTS_VOICE)
        return None
    t_edge = time.monotonic()
    logger.info("latencia: edge-tts levou %.0fms", (t_edge - t_start) * 1000)
    if not raw:
        logger.warning("edge-tts nao retornou audio (voice=%s, text=%r)", config.TTS_VOICE, text[:80])
        return None

    try:
        processed = await asyncio.wait_for(_ffmpeg_postprocess(raw), timeout=_FFMPEG_TIMEOUT_S)
    except Exception:
        logger.exception("pos-processamento ffmpeg falhou")
        return None
    t_ffmpeg = time.monotonic()
    logger.info(
        "latencia: ffmpeg levou %.0fms | total /tts %.0fms",
        (t_ffmpeg - t_edge) * 1000, (t_ffmpeg - t_start) * 1000,
    )
    return processed
