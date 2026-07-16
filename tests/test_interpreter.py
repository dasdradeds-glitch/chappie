import pytest

from server import interpreter


def test_validate_parsed_happy_path():
    parsed = {"impulses": {"dopamine": 0.3, "cortisol": -0.2}, "reply": " oi "}
    result = interpreter.validate_parsed(parsed)
    assert result == {"impulses": {"dopamine": 0.3, "cortisol": -0.2}, "reply": "oi"}


def test_validate_parsed_clamps_deltas_to_0_7():
    parsed = {"impulses": {"dopamine": 5.0, "cortisol": -5.0}, "reply": "oi"}
    result = interpreter.validate_parsed(parsed)
    assert result["impulses"]["dopamine"] == 0.7
    assert result["impulses"]["cortisol"] == -0.7


def test_validate_parsed_drops_unknown_chemical_keys():
    parsed = {"impulses": {"not_a_chemical": 0.5}, "reply": "oi"}
    result = interpreter.validate_parsed(parsed)
    assert result["impulses"] == {}


def test_validate_parsed_raises_on_missing_reply():
    with pytest.raises(ValueError):
        interpreter.validate_parsed({"impulses": {}})


def test_validate_parsed_raises_on_empty_reply():
    with pytest.raises(ValueError):
        interpreter.validate_parsed({"impulses": {}, "reply": "   "})


def test_validate_parsed_raises_on_non_dict_payload():
    with pytest.raises(ValueError):
        interpreter.validate_parsed(["not", "a", "dict"])


def test_validate_parsed_raises_on_non_dict_impulses():
    with pytest.raises(ValueError):
        interpreter.validate_parsed({"impulses": "nope", "reply": "oi"})


@pytest.mark.asyncio
async def test_interpret_empty_text_returns_fallback():
    result = await interpreter.interpret("", {}, [])
    assert result == interpreter.FALLBACK


@pytest.mark.asyncio
async def test_interpret_mock_mode_uses_deterministic_rules(monkeypatch):
    monkeypatch.setattr(interpreter.config, "MOCK_LLM", True)
    result = await interpreter.interpret("que susto!", {}, [])
    assert "cortisol" in result["impulses"]
    assert result["reply"]


@pytest.mark.asyncio
async def test_interpret_no_api_key_returns_fallback(monkeypatch):
    monkeypatch.setattr(interpreter.config, "MOCK_LLM", False)
    monkeypatch.setattr(interpreter.config, "ANTHROPIC_API_KEY", "")
    result = await interpreter.interpret("oi", {}, [])
    assert result == interpreter.FALLBACK


@pytest.mark.asyncio
async def test_interpret_timeout_falls_back(monkeypatch):
    monkeypatch.setattr(interpreter.config, "MOCK_LLM", False)
    monkeypatch.setattr(interpreter.config, "ANTHROPIC_API_KEY", "fake-key")

    class FakeMessages:
        async def create(self, **kwargs):
            raise TimeoutError("simulated timeout")

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(interpreter, "_get_client", lambda: FakeClient())
    result = await interpreter.interpret("oi", {"cortisol": 0.25}, [])
    assert result == interpreter.FALLBACK


@pytest.mark.asyncio
async def test_interpret_ignores_natural_language_reply_without_tool_use(monkeypatch):
    """Regressao do bug real encontrado 16/07 no Note 8 (2x reproduzido,
    log com stop_reason/block_types em maos): o Claude as vezes responde
    em portugues natural, no personagem, mesmo com tool_choice forcado
    fica sujeito a variacao — se por algum motivo so vier ThinkingBlock +
    TextBlock (sem tool_use), tem que cair no fallback, nao quebrar."""
    monkeypatch.setattr(interpreter.config, "MOCK_LLM", False)
    monkeypatch.setattr(interpreter.config, "ANTHROPIC_API_KEY", "fake-key")

    class FakeThinkingBlock:
        type = "thinking"
        thinking = "..."

    class FakeTextBlock:
        type = "text"
        text = "Tô sim, te escutando direitinho agora."

    class FakeResponse:
        content = [FakeThinkingBlock(), FakeTextBlock()]
        stop_reason = "end_turn"

    class FakeMessages:
        async def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(interpreter, "_get_client", lambda: FakeClient())
    result = await interpreter.interpret("oi", {"cortisol": 0.25}, [])
    assert result == interpreter.FALLBACK


@pytest.mark.asyncio
async def test_interpret_valid_tool_use_response(monkeypatch):
    monkeypatch.setattr(interpreter.config, "MOCK_LLM", False)
    monkeypatch.setattr(interpreter.config, "ANTHROPIC_API_KEY", "fake-key")

    class FakeToolUseBlock:
        type = "tool_use"
        name = "emit_response"
        input = {"impulses": {"dopamine": 0.4}, "reply": "oi!"}

    class FakeResponse:
        content = [FakeToolUseBlock()]
        stop_reason = "tool_use"

    class FakeMessages:
        async def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(interpreter, "_get_client", lambda: FakeClient())
    result = await interpreter.interpret("oi", {"cortisol": 0.25}, [])
    assert result == {"impulses": {"dopamine": 0.4}, "reply": "oi!"}


@pytest.mark.asyncio
async def test_interpret_forces_tool_choice(monkeypatch):
    """Trava o contrato: a chamada real tem que forcar tool_choice pro
    emit_response, senao a gente volta a depender do modelo 'obedecer'
    uma instrucao solta de texto (a causa raiz do bug real)."""
    monkeypatch.setattr(interpreter.config, "MOCK_LLM", False)
    monkeypatch.setattr(interpreter.config, "ANTHROPIC_API_KEY", "fake-key")

    captured = {}

    class FakeToolUseBlock:
        type = "tool_use"
        name = "emit_response"
        input = {"impulses": {}, "reply": "oi"}

    class FakeResponse:
        content = [FakeToolUseBlock()]
        stop_reason = "tool_use"

    class FakeMessages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(interpreter, "_get_client", lambda: FakeClient())
    await interpreter.interpret("oi", {"cortisol": 0.25}, [])

    assert captured["tool_choice"] == {"type": "tool", "name": "emit_response"}
    assert captured["tools"][0]["name"] == "emit_response"
