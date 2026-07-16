import pytest
from pydantic import ValidationError

from server.engine import Engine, derive_emotions
from server.schemas import FaceStateModel, NeuroSnapshot, SayRequest, SayResponse

IMPULSE_SCENARIOS = [
    {"cortisol": 0.5, "adrenaline": 0.6, "gaba": -0.3},
    {"testosterone": 0.6, "cortisol": 0.3, "serotonin": -0.3},
    {"oxytocin": 0.6, "serotonin": 0.3},
    {"gaba": 0.4, "adrenaline": -0.3},
    {"dopamine": -0.5, "serotonin": -0.5, "endorphins": -0.3},
    {"dopamine": 0.5, "adrenaline": 0.4, "gaba": -0.3},
]


def test_face_state_validates_against_schema_at_baseline():
    e = Engine()
    for _ in range(50):
        e.tick(0.05)
    FaceStateModel(**e.face_state())


def test_face_state_validates_after_impulses_across_all_emotions():
    e = Engine()
    for impulse in IMPULSE_SCENARIOS:
        e.apply_impulses(impulse)
        for _ in range(20):
            e.tick(0.05)
        FaceStateModel(**e.face_state())


def test_say_request_rejects_empty_text():
    with pytest.raises(ValidationError):
        SayRequest(text="")


def test_say_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        SayRequest(text="oi", extra="nope")


def test_say_response_accepts_valid_shape():
    resp = SayResponse(reply="oi", impulses={"dopamine": 0.3})
    assert resp.reply == "oi"


def test_neuro_snapshot_rejects_invalid_dominant():
    e = Engine()
    emotions = derive_emotions(e.chem)
    with pytest.raises(ValidationError):
        NeuroSnapshot(chemicals=e.chem, emotions=emotions, dominant="nao-e-uma-emocao")


def test_neuro_snapshot_accepts_valid_shape():
    e = Engine()
    emotions = derive_emotions(e.chem)
    snap = NeuroSnapshot(chemicals=e.chem, emotions=emotions, dominant="happiness")
    assert snap.dominant == "happiness"
