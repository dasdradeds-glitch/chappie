"""Smoke E2E (HANDOFF v2 §2.5): sobe o app inteiro (lifespan real, tick loop
real) in-process via TestClient — sem processo OS separado, sem rede real,
sem os artefatos de scheduling de processo em background observados durante
o dev manual (ver server/engine.py, nota do bug de crossfade de cor).
Manda "que susto!" e confere que o FaceState reage."""
from fastapi.testclient import TestClient

from server import config


def test_full_pipeline_reacts_to_susto(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(config, "PERSIST_INTERVAL_S", 999)  # nao precisa persistir durante o teste

    from server.main import app  # import tardio: precisa do monkeypatch acima antes do lifespan

    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["ok"] is True
        assert health["mock_llm"] is True

        say = client.post("/say", json={"text": "que susto, tem alguem na porta!"})
        assert say.status_code == 200
        body = say.json()
        assert body["reply"]
        assert body["impulses"].get("cortisol", 0) > 0

        neuro = client.get("/neuro").json()
        assert neuro["dominant"] == "fear"

        with client.websocket_connect("/face") as ws:
            frame = ws.receive_json()
            assert frame["dominant"] == "fear"
            assert frame["color"].startswith("rgb(")
            assert "mouthCurve" in frame["face"]


def test_ws_face_payload_includes_initiative_field(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    from server.main import app

    with TestClient(app) as client:
        with client.websocket_connect("/face") as ws:
            frame = ws.receive_json()
            assert "initiative" in frame
            assert frame["initiative"] is None


def test_initiative_fires_when_idle_and_client_connected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    import server.main as main

    with TestClient(main.app) as client:
        with client.websocket_connect("/face"):
            main.state["last_interaction_at"] = 0.0  # "silencio" ha muito tempo
            main.state["initiative_threshold_s"] = 0.0  # dispara na primeira checagem
            import asyncio
            asyncio.run(main._maybe_fire_initiative())

        assert main.state["pending_initiative"] is not None
        assert main.state["pending_initiative"]["id"] == 1
        assert main.state["pending_initiative"]["text"]
        assert main.state["history"][-2] == {"role": "user", "content": main.INITIATIVE_HISTORY_MARKER}
        assert main.state["history"][-1]["role"] == "assistant"


def test_initiative_skips_without_connected_ws_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    import asyncio
    import server.main as main

    with TestClient(main.app) as client:
        main.state["ws_clients"] = 0
        main.state["last_interaction_at"] = 0.0
        main.state["initiative_threshold_s"] = 0.0
        asyncio.run(main._maybe_fire_initiative())
        assert main.state["pending_initiative"] is None


def test_initiative_skips_before_threshold_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    import asyncio
    import time
    import server.main as main

    with TestClient(main.app) as client:
        with client.websocket_connect("/face"):
            main.state["last_interaction_at"] = time.monotonic()  # acabou de interagir
            main.state["initiative_threshold_s"] = 999.0
            asyncio.run(main._maybe_fire_initiative())
            assert main.state["pending_initiative"] is None


def test_say_pushes_back_initiative_threshold(tmp_path, monkeypatch):
    """Uma interacao real precisa empurrar o relogio da iniciativa pra
    frente — conversa de verdade nao deve ser seguida imediatamente por
    Chappie 'quebrando o silencio' que ele mesmo acabou de quebrar."""
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    import server.main as main

    with TestClient(main.app) as client:
        main.state["last_interaction_at"] = 0.0
        before = main.state["last_interaction_at"]
        resp = client.post("/say", json={"text": "oi chappie"})
        assert resp.status_code == 200
        assert main.state["last_interaction_at"] > before


def test_tts_endpoint_returns_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    import server.main as main

    async def fake_synthesize(text):
        return b"fake-mp3-bytes"

    monkeypatch.setattr(main, "synthesize", fake_synthesize)

    with TestClient(main.app) as client:
        resp = client.post("/tts", json={"text": "oi"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/mpeg"
        assert resp.content == b"fake-mp3-bytes"


def test_tts_endpoint_returns_502_when_synthesis_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    import server.main as main

    async def fake_synthesize(text):
        return None

    monkeypatch.setattr(main, "synthesize", fake_synthesize)

    with TestClient(main.app) as client:
        resp = client.post("/tts", json={"text": "oi"})
        assert resp.status_code == 502


def test_health_reports_missing_api_key_when_not_mocked(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", False)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    from server.main import app

    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["ok"] is False
        assert "ANTHROPIC_API_KEY" in health["error"]


def test_renderer_index_served_at_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")

    from server.main import app

    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Chappie" in resp.text
        assert client.get("/assets/face_math.js").status_code == 200
        assert client.get("/assets/app.js").status_code == 200


def test_admin_update_disabled_without_token(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")

    import server.main as main

    with TestClient(main.app) as client:
        resp = client.post("/admin/update", headers={"X-Admin-Token": "qualquer-coisa"})
        assert resp.status_code == 403


def test_admin_update_rejects_wrong_token(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(config, "ADMIN_TOKEN", "segredo-certo")

    import server.main as main

    with TestClient(main.app) as client:
        resp = client.post("/admin/update", headers={"X-Admin-Token": "chute-errado"})
        assert resp.status_code == 403


def test_admin_update_pulls_and_schedules_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(config, "ADMIN_TOKEN", "segredo-certo")

    import server.main as main

    class FakeCompletedProcess:
        returncode = 0
        stdout = "Already up to date."
        stderr = ""

    restart_calls = []
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **kw: FakeCompletedProcess())
    monkeypatch.setattr(main, "_schedule_restart", lambda *a, **kw: restart_calls.append(True))

    with TestClient(main.app) as client:
        resp = client.post("/admin/update", headers={"X-Admin-Token": "segredo-certo"})
        assert resp.status_code == 200
        assert resp.json()["pulled"] == "Already up to date."
        assert restart_calls == [True]


def test_admin_update_returns_500_on_git_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_LLM", True)
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(config, "ADMIN_TOKEN", "segredo-certo")

    import server.main as main

    class FakeFailedProcess:
        returncode = 1
        stdout = ""
        stderr = "conflito de merge"

    monkeypatch.setattr(main.subprocess, "run", lambda *a, **kw: FakeFailedProcess())

    with TestClient(main.app) as client:
        resp = client.post("/admin/update", headers={"X-Admin-Token": "segredo-certo"})
        assert resp.status_code == 500
