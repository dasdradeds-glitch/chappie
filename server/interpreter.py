"""LLM Interpreter: fala -> {impulses, reply}. Roda so no servidor (a API
key nunca vai pro browser). MOCK_LLM=1 desvia pra dev/mock_llm.py — sem rede,
sem custo, determinístico. Parse defensivo: fences, JSON malformado, timeout
e qualquer outra falha caem no mesmo fallback ("Interferência no sinal")."""
from __future__ import annotations

import json
import re

from . import config, persona
from .engine import CHEMS

FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.MULTILINE)
FALLBACK = {"impulses": {}, "reply": "Interferência no sinal."}

_client = None


def _get_client():
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic
        _client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def clean_json_text(raw: str) -> str:
    return FENCE_RE.sub("", raw).strip()


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
        persona.OUTPUT_FORMAT_INSTRUCTIONS,
        persona.build_state_context(chem),
    ])

    try:
        client = _get_client()
        resp = await client.messages.create(
            model=config.MODEL,
            max_tokens=300,
            system=system,
            messages=build_messages(history, text),
            timeout=15.0,
        )
        raw = "".join(
            block.text for block in resp.content
            if getattr(block, "type", None) == "text"
        )
        parsed = json.loads(clean_json_text(raw))
        return validate_parsed(parsed)
    except Exception:
        return dict(FALLBACK)
