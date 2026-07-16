"""LLM Interpreter: fala -> {impulses, reply}. Roda so no servidor (a API
key nunca vai pro browser). MOCK_LLM=1 desvia pra dev/mock_llm.py — sem rede,
sem custo, determinístico.

Usa tool calling forçado (tool_choice) em vez de pedir JSON dentro do
prompt: um teste real no Note 8 mostrou o Claude respondendo em portugues
natural, no personagem, ignorando a instrução "responda só em JSON" —
reproduzido 2x identico (log com stop_reason/block_types em maos, não é
hipótese). Tool calling faz a própria API garantir o shape da resposta,
sem depender do modelo obedecer uma instrução de texto solta no prompt."""
from __future__ import annotations

import logging
import time

from . import config, persona
from .engine import CHEMS

logger = logging.getLogger("chappie")

FALLBACK = {"impulses": {}, "reply": "Interferência no sinal."}

# Marca sintetica que o initiative loop manda como "fala do usuario" — sinaliza
# pro Claude que ninguem falou, e ele esta puxando assunto por conta propria
# (ver persona.INITIATIVE_NUDGE, que explica essa marca no system prompt).
INITIATIVE_MARKER = "[silêncio prolongado — ninguém falou, mas você pode puxar assunto se quiser]"

EMIT_TOOL = {
    "name": "emit_response",
    "description": "Emite a fala do Chappie e os impulsos químicos que ele sentiu ao responder.",
    "input_schema": {
        "type": "object",
        "properties": {
            "impulses": {
                "type": "object",
                "description": "2 a 5 impulsos químicos (deltas entre -0.7 e 0.7).",
                "properties": {k: {"type": "number"} for k in CHEMS},
                "additionalProperties": False,
            },
            "reply": {
                "type": "string",
                "description": "Fala do Chappie em pt-BR, curta e direta (máx 35 palavras), com uma opinião ou imagem específica — nunca morna ou genérica.",
            },
        },
        "required": ["impulses", "reply"],
        "additionalProperties": False,
    },
}

_client = None


def _get_client():
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic
        _client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def validate_parsed(parsed) -> dict:
    """Levanta ValueError se o shape nao servir; quem chama decide o fallback."""
    if not isinstance(parsed, dict):
        raise ValueError("payload nao e um objeto")
    reply = parsed.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("reply ausente ou vazio")
    impulses_raw = parsed.get("impulses", {})
    if not isinstance(impulses_raw, dict):
        raise ValueError("impulses nao e um objeto")
    impulses = {}
    for k, v in impulses_raw.items():
        if k in CHEMS and isinstance(v, (int, float)) and not isinstance(v, bool):
            impulses[k] = max(-0.7, min(0.7, float(v)))
    return {"impulses": impulses, "reply": reply.strip()}


def build_messages(history: list[dict], text: str) -> list[dict]:
    msgs = []
    for turn in history[-config.HISTORY_MAX_TURNS:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = turn.get("content", "")
        if content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": text})
    return msgs


async def interpret(text: str, chem: dict, history: list[dict]) -> dict:
    if not text or not text.strip():
        return dict(FALLBACK)

    if config.MOCK_LLM:
        from dev.mock_llm import mock_interpret
        return mock_interpret(text)

    if not config.ANTHROPIC_API_KEY:
        return dict(FALLBACK)

    system = "\n\n".join([
        persona.SYSTEM_PROMPT,
        persona.REPLY_GUIDANCE,
        persona.build_state_context(chem),
    ])

    try:
        client = _get_client()
        t0 = time.monotonic()
        resp = await client.messages.create(
            model=config.MODEL,
            max_tokens=1024,
            system=system,
            messages=build_messages(history, text),
            tools=[EMIT_TOOL],
            tool_choice={"type": "tool", "name": "emit_response"},
            timeout=15.0,
        )
        logger.info("latencia: chamada Anthropic (interpret) levou %.0fms", (time.monotonic() - t0) * 1000)
    except Exception:
        logger.exception("chamada a API da Anthropic falhou (model=%s)", config.MODEL)
        return dict(FALLBACK)

    try:
        tool_block = next(b for b in resp.content if getattr(b, "type", None) == "tool_use")
        return validate_parsed(tool_block.input)
    except Exception:
        block_types = [getattr(b, "type", type(b).__name__) for b in resp.content]
        logger.exception(
            "extrair tool_use da resposta do Claude falhou | stop_reason=%s | block_types=%s | content=%r",
            getattr(resp, "stop_reason", None), block_types, resp.content,
        )
        return dict(FALLBACK)


async def interpret_initiative(chem: dict, history: list[dict]) -> dict | None:
    """Fala espontanea (HANDOFF pos-16/07: 'iniciativa'). Diferente de
    interpret(): ninguem perguntou nada, entao falha vira None (skip
    silencioso) em vez de FALLBACK — nao faz sentido Chappie anunciar
    'interferencia no sinal' do nada, sem pergunta pra responder."""
    if config.MOCK_LLM:
        from dev.mock_llm import mock_initiative
        return mock_initiative()

    if not config.ANTHROPIC_API_KEY:
        return None

    system = "\n\n".join([
        persona.SYSTEM_PROMPT,
        persona.REPLY_GUIDANCE,
        persona.build_state_context(chem),
        persona.INITIATIVE_NUDGE,
    ])

    try:
        client = _get_client()
        resp = await client.messages.create(
            model=config.MODEL,
            max_tokens=1024,
            system=system,
            messages=build_messages(history, INITIATIVE_MARKER),
            tools=[EMIT_TOOL],
            tool_choice={"type": "tool", "name": "emit_response"},
            timeout=15.0,
        )
    except Exception:
        logger.exception("chamada de iniciativa a API da Anthropic falhou (model=%s)", config.MODEL)
        return None

    try:
        tool_block = next(b for b in resp.content if getattr(b, "type", None) == "tool_use")
        return validate_parsed(tool_block.input)
    except Exception:
        block_types = [getattr(b, "type", type(b).__name__) for b in resp.content]
        logger.exception(
            "extrair tool_use da iniciativa falhou | stop_reason=%s | block_types=%s | content=%r",
            getattr(resp, "stop_reason", None), block_types, resp.content,
        )
        return None
