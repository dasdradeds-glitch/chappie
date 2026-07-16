from server.engine import Engine, BASELINE, CHEMS
from server import persistence


def _run_ticks(engine, seconds, dt=0.05):
    for _ in range(int(seconds / dt)):
        engine.tick(dt)


def test_decay_converges_to_baseline_without_impulses():
    e = Engine()
    e.chem["cortisol"] = 1.0
    _run_ticks(e, 120)
    assert abs(e.chem["cortisol"] - BASELINE["cortisol"]) < 0.01


def test_decay_persistence_envelope_12_to_30s():
    """Impulso forte de adrenalina (HANDOFF §2.3): o efeito ainda deve estar
    perceptivel aos 12s e ja quase todo dissipado aos 30s — trava a
    calibracao de DECAY['adrenaline']=0.14/s contra mudanca acidental."""
    e = Engine()
    e.apply_impulses({"adrenaline": 0.6})
    distance = 0.6
    threshold = BASELINE["adrenaline"] + 0.1 * distance

    _run_ticks(e, 12)
    assert e.chem["adrenaline"] > threshold, "adrenalina ja decaiu demais antes dos 12s"

    _run_ticks(e, 18)  # completa 30s
    assert e.chem["adrenaline"] < threshold, "adrenalina nao decaiu o suficiente ate os 30s"


def test_apply_impulses_clamped_to_upper_bound():
    e = Engine()
    e.apply_impulses({k: 10.0 for k in CHEMS})
    assert all(v == 1.0 for v in e.chem.values())


def test_apply_impulses_clamped_to_lower_bound():
    e = Engine()
    e.apply_impulses({k: -10.0 for k in CHEMS})
    assert all(v == 0.0 for v in e.chem.values())


def test_apply_impulses_ignores_unknown_keys():
    e = Engine()
    before = dict(e.chem)
    e.apply_impulses({"not_a_chemical": 0.9})
    assert e.chem == before


def test_color_survives_multiple_transitions():
    """Regressao do bug real encontrado 16/07: mix_color retornava string
    'rgb(...)' e col.frm era reatribuido a partir de col.cur, que na
    proxima transicao virava argumento invalido pra hex_to_rgb (ValueError,
    matando a task do tick loop em silencio). A cor agora fica em tupla RGB
    internamente; isso precisa sobreviver a varias trocas de dominante
    seguidas sem excecao."""
    e = Engine()
    impulse_sequence = [
        {"cortisol": 0.5, "adrenaline": 0.6, "gaba": -0.3},          # -> medo
        {"testosterone": 0.6, "cortisol": 0.3, "serotonin": -0.3},   # -> raiva
        {"oxytocin": 0.6, "serotonin": 0.3},                          # -> afeto
        {"gaba": 0.4, "adrenaline": -0.3},                            # -> calma
        {"dopamine": -0.5, "serotonin": -0.5, "endorphins": -0.3},   # -> tristeza
    ]
    for impulse in impulse_sequence:
        e.apply_impulses(impulse)
        _run_ticks(e, 3)
        color = e.face_state()["color"]
        assert color.startswith("rgb(")
        r, g, b = (int(x) for x in color[4:-1].split(","))
        assert all(0 <= v <= 255 for v in (r, g, b))


def test_snapshot_roundtrip_preserves_chem(tmp_path):
    e = Engine()
    e.apply_impulses({"cortisol": 0.4, "adrenaline": 0.3})
    _run_ticks(e, 2)
    path = tmp_path / "state.json"
    persistence.save({"chem": e.chem, "history": [{"role": "user", "content": "oi"}]}, path)

    loaded = persistence.load(path)
    e2 = Engine.from_snapshot(loaded)
    for k in CHEMS:
        assert abs(e2.chem[k] - e.chem[k]) < 1e-9


def test_persistence_survives_process_restart_simulation(tmp_path):
    """M2: 'persistencia sobrevive a restart' — simula matar e resubir o
    processo trocando a instancia de Engine inteira, sem sleep real."""
    path = tmp_path / "state.json"
    e1 = Engine()
    e1.apply_impulses({"oxytocin": 0.5, "serotonin": 0.2})
    _run_ticks(e1, 5)
    persistence.save({"chem": e1.chem, "history": []}, path)
    del e1  # "mata o processo"

    snap = persistence.load(path)
    e2 = Engine.from_snapshot(snap)  # "resobe o processo"
    assert e2.face_state()["dominant"] == "affection"


def test_from_snapshot_falls_back_to_baseline_on_missing_keys():
    e = Engine.from_snapshot({"chem": {"dopamine": 0.9}})
    assert e.chem == BASELINE


def test_from_snapshot_falls_back_to_baseline_on_empty_snapshot():
    e = Engine.from_snapshot({})
    assert e.chem == BASELINE


def test_blink_is_transient_not_stuck():
    e = Engine()
    states = []
    for _ in range(int(20 / 0.05)):  # 20s simulados
        e.tick(0.05)
        states.append(e.blinking)
    assert True in states, "nenhuma piscada ocorreu em 20s simulados"
    assert False in states, "piscada ficou travada permanentemente ligada"
