import os

import pytest

from server import tts


@pytest.mark.asyncio
async def test_synthesize_empty_text_returns_none():
    assert await tts.synthesize("") is None
    assert await tts.synthesize("   ") is None


@pytest.mark.asyncio
async def test_synthesize_happy_path(monkeypatch):
    async def fake_edge_tts_bytes(text):
        return b"raw-mp3-bytes"

    async def fake_ffmpeg_postprocess(raw):
        assert raw == b"raw-mp3-bytes"
        return b"processed-mp3-bytes"

    monkeypatch.setattr(tts, "_edge_tts_bytes", fake_edge_tts_bytes)
    monkeypatch.setattr(tts, "_ffmpeg_postprocess", fake_ffmpeg_postprocess)

    result = await tts.synthesize("oi")
    assert result == b"processed-mp3-bytes"


@pytest.mark.asyncio
async def test_synthesize_edge_tts_failure_returns_none(monkeypatch):
    async def fake_edge_tts_bytes(text):
        raise RuntimeError("edge-tts fora do ar")

    monkeypatch.setattr(tts, "_edge_tts_bytes", fake_edge_tts_bytes)

    assert await tts.synthesize("oi") is None


@pytest.mark.asyncio
async def test_synthesize_edge_tts_empty_audio_returns_none(monkeypatch):
    async def fake_edge_tts_bytes(text):
        return b""

    monkeypatch.setattr(tts, "_edge_tts_bytes", fake_edge_tts_bytes)

    assert await tts.synthesize("oi") is None


@pytest.mark.asyncio
async def test_synthesize_ffmpeg_failure_returns_none(monkeypatch):
    async def fake_edge_tts_bytes(text):
        return b"raw-mp3-bytes"

    async def fake_ffmpeg_postprocess(raw):
        raise RuntimeError("ffmpeg ausente ou build sem librubberband")

    monkeypatch.setattr(tts, "_edge_tts_bytes", fake_edge_tts_bytes)
    monkeypatch.setattr(tts, "_ffmpeg_postprocess", fake_ffmpeg_postprocess)

    assert await tts.synthesize("oi") is None


@pytest.mark.skipif(
    os.environ.get("CHAPPIE_LIVE_TTS") != "1",
    reason="opt-in: exige CHAPPIE_LIVE_TTS=1 (rede real + ffmpeg instalado)",
)
@pytest.mark.asyncio
async def test_synthesize_live_real_pipeline():
    audio = await tts.synthesize("Isso e um teste da voz do Chappie.")
    assert audio is not None
    assert len(audio) > 1000
