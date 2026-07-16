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
