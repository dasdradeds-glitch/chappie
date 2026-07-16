"""Runner de calibracao (HANDOFF v2 §2.8). Le scenarios.yaml e valida o
pipeline completo (texto -> impulsos -> emocao dominante) contra MOCK_LLM
por padrao — gratis, deterministico, roda em todo `pytest`. O modo live
contra o Claude real e opt-in (CHAPPIE_LIVE_SCENARIOS=1 + API key), pra
nunca gastar credito sem pedir."""
import os
from pathlib import Path

import pytest
import yaml

from dev.mock_llm import mock_interpret
from server.engine import Engine

SCENARIOS_PATH = Path(__file__).resolve().parent / "scenarios.yaml"
with open(SCENARIOS_PATH, encoding="utf-8") as f:
    SCENARIOS = yaml.safe_load(f)["scenarios"]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["text"] for s in SCENARIOS])
def test_scenario_matches_expected_dominant_mock(scenario):
    result = mock_interpret(scenario["text"])
    assert result["reply"], "mock deveria sempre devolver uma reply nao vazia"

    e = Engine()
    e.apply_impulses(result["impulses"])
    face = e.face_state()

    assert face["dominant"] == scenario["expected_dominant"], (
        f"'{scenario['text']}': esperava {scenario['expected_dominant']}, "
        f"veio {face['dominant']} (emocoes: {face['emotions']})"
    )
    got_intensity = face["emotions"][scenario["expected_dominant"]]
    assert got_intensity >= scenario["min_intensity"], (
        f"'{scenario['text']}': intensidade {got_intensity:.3f} "
        f"abaixo do minimo {scenario['min_intensity']}"
    )


@pytest.mark.skipif(
    os.environ.get("CHAPPIE_LIVE_SCENARIOS") != "1",
    reason="opt-in: exige CHAPPIE_LIVE_SCENARIOS=1 (gasta credito de API real)",
)
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["text"] for s in SCENARIOS])
async def test_scenario_matches_expected_dominant_live(scenario, monkeypatch):
    from server import config, interpreter

    monkeypatch.setattr(config, "MOCK_LLM", False)
    if not config.ANTHROPIC_API_KEY:
        pytest.skip("ANTHROPIC_API_KEY ausente")

    result = await interpreter.interpret(scenario["text"], dict(Engine().chem), [])
    e = Engine()
    e.apply_impulses(result["impulses"])
    face = e.face_state()
    if face["dominant"] != scenario["expected_dominant"]:
        pytest.fail(
            f"DIVERGENCIA (Claude real): '{scenario['text']}' esperava "
            f"{scenario['expected_dominant']}, veio {face['dominant']} | reply: {result['reply']!r}"
        )
