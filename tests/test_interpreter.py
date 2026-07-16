import pytest

from server import interpreter


def test_clean_json_text_strips_fences():
    raw = "```json\n{\"a\": 1}\n```"
    assert interpreter.clean_json_text(raw) == '{"a": 1}'


def test_clean_json_text_passes_through_plain_json():
    raw = '{"a": 1}'
    assert interpreter.clean_json_text(raw) == '{"a": 1}'


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
async def test_interpret_malformed_json_falls_back(monkeypatch):
    monkeypatch.setattr(interpreter.config, "MOCK_LLM", False)
    monkeypatch.setattr(interpreter.config, "ANTHROPIC_API_KEY", "fake-key")

    class FakeBlock:
        type = "text"
        text = "isso nao e json valido {{{"

    class FakeResponse:
        content = [FakeBlock()]

    class FakeMessages:
        async def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(interpreter, "_get_client", lambda: FakeClient())
    result = await interpreter.interpret("oi", {"cortisol": 0.25}, [])
    assert result == interpreter.FALLBACK


@pytest.mark.asyncio
async def test_interpret_valid_response_with_fences(monkeypatch):
    monkeypatch.setattr(interpreter.config, "MOCK_LLM", False)
    monkeypatch.setattr(interpreter.config, "ANTHROPIC_API_KEY", "fake-key")

    class FakeBlock:
        type = "text"
        text = '```json\n{"impulses": {"dopamine": 0.4}, "reply": "oi!"}\n```'

    class FakeResponse:
        content = [FakeBlock()]

    class FakeMessages:
        async def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(interpreter, "_get_client", lambda: FakeClient())
    result = await interpreter.interpret("oi", {"cortisol": 0.25}, [])
    assert result == {"impulses": {"dopamine": 0.4}, "reply": "oi!"}
