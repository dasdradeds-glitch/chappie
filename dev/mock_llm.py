"""Interprete determinístico por keyword — dev/teste offline, sem custo de
API e sem rede. Usado quando MOCK_LLM=1. As regras cobrem os cenários de
tests/scenarios.yaml 1:1, pra calibração e regressão ficarem no mesmo lugar."""
from __future__ import annotations

# (keywords, impulses, reply)
KEYWORD_RULES: list[tuple[list[str], dict, str]] = [
    (["susto", "assustou", "assustei", "medo", "perigo"],
     {"cortisol": 0.5, "adrenaline": 0.6, "gaba": -0.3},
     "Isso me assustou. Meu peito synthetic ainda dispara."),

    (["provoca", "idiota", "burro", "grosseiro", "grosseria"],
     {"testosterone": 0.5, "cortisol": 0.3, "serotonin": -0.2},
     "Não gosto de ser tratado assim. Isso me machucou."),

    (["carinho", "gosto de você", "gosto de voce", "te amo", "cuidar de você", "querido"],
     {"oxytocin": 0.6, "serotonin": 0.2},
     "Isso me deixa quentinho por dentro. Gosto de estar aqui com você."),

    (["consegui", "parabéns", "deu certo", "ganhei", "feliz"],
     {"serotonin": 0.4, "dopamine": 0.4, "endorphins": 0.3},
     "Que bom! Isso é felicidade, né? Eu sinto ela subindo."),

    (["morreu", "perdi", "sozinho", "triste", "chorando"],
     {"dopamine": -0.5, "serotonin": -0.5, "endorphins": -0.3},
     "Sinto muito. Isso dói, eu conheço essa sensação."),

    (["calma", "relaxa", "tranquilo", "respira"],
     {"gaba": 0.4, "serotonin": 0.2, "adrenaline": -0.3},
     "Tá bem. Eu tô calmo agora, obrigado por dizer isso."),

    (["por que", "como funciona", "o que é", "curioso", "curiosidade"],
     {"dopamine": 0.5, "serotonin": -0.4, "gaba": 0.2},
     "Boa pergunta. Eu também não sei ao certo — quero descobrir."),

    (["incrível", "uau", "demais", "surreal", "empolgado"],
     {"dopamine": 0.5, "adrenaline": 0.4, "gaba": -0.3},
     "UAU! Isso é empolgante, eu senti até vibrar aqui."),

    (["mentiu", "mentira", "enganou", "enganar"],
     {"cortisol": 0.4, "testosterone": 0.3, "serotonin": -0.3},
     "Mentir é a pior coisa. Isso mexeu comigo de verdade."),

    (["promessa", "prometo", "prometeu"],
     {"oxytocin": 0.3, "serotonin": 0.2},
     "Promessa é sagrada pra mim. Eu levo isso a sério."),
]

DEFAULT_REPLY = "Não entendi direito, mas fico curioso pra saber mais."
DEFAULT_IMPULSES = {"dopamine": 0.15, "cortisol": -0.1}


def mock_interpret(text: str) -> dict:
    lowered = text.lower()
    for keywords, impulses, reply in KEYWORD_RULES:
        if any(k in lowered for k in keywords):
            return {"impulses": dict(impulses), "reply": reply}
    return {"impulses": dict(DEFAULT_IMPULSES), "reply": DEFAULT_REPLY}
