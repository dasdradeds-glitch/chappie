from server.engine import Engine, derive_emotions


def test_susto_medo_maior_que_empolgacao_e_raiva():
    """Bug historico v4 (HANDOFF §2.3): medo e empolgacao/raiva nao podem
    colidir — um susto tem que dar medo, nao empolgacao."""
    e = Engine()
    e.apply_impulses({"cortisol": 0.5, "adrenaline": 0.6, "gaba": -0.3})
    emo = derive_emotions(e.chem)
    assert emo["fear"] > emo["excitement"]
    assert emo["fear"] > emo["anger"]


def test_provocacao_raiva_dominante():
    e = Engine()
    e.apply_impulses({"testosterone": 0.5, "cortisol": 0.3, "serotonin": -0.2})
    emo = derive_emotions(e.chem)
    assert max(emo, key=emo.get) == "anger"


def test_carinho_afeto_dominante():
    e = Engine()
    e.apply_impulses({"oxytocin": 0.6, "serotonin": 0.2})
    emo = derive_emotions(e.chem)
    assert max(emo, key=emo.get) == "affection"


def test_mouth_curve_positivo_quando_felicidade_domina():
    e = Engine()
    e.apply_impulses({"serotonin": 0.4, "dopamine": 0.3, "endorphins": 0.3})
    face = e.face_state()["face"]
    assert face["mouthCurve"] > 0


def test_mouth_curve_negativo_quando_tristeza_domina():
    e = Engine()
    e.apply_impulses({"dopamine": -0.5, "serotonin": -0.5, "endorphins": -0.3})
    face = e.face_state()["face"]
    assert face["mouthCurve"] < 0


def test_mouth_width_estreita_muito_com_raiva_extrema():
    """HANDOFF §2.3: 'width < 7vw quando anger > 0.5'. Achado por busca
    numerica: com os pesos calibrados do v8, raiva>0.5 sozinha nao basta —
    medo/tristeza sobem junto (compartilham cortisol) e engordam a boca de
    volta. Precisa empurrar raiva perto do teto pra vencer esse efeito."""
    e = Engine()
    e.chem.update({
        "dopamine": 1.0, "serotonin": 0.0, "oxytocin": 0.0, "cortisol": 1.0,
        "adrenaline": 0.25, "endorphins": 1.0, "testosterone": 1.0, "gaba": 1.0,
    })
    emo = derive_emotions(e.chem)
    assert emo["anger"] > 0.5
    face = e.face_state()["face"]
    assert face["mouthWidthVw"] < 7
