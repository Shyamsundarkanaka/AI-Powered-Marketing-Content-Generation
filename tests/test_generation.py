"""Tests for the generate/retry loop in graph/llm.py.

The provider client is replaced with a scripted fake, so these exercise the
control flow — retry on a bad shape, feed the error back, give up cleanly,
never invent content — without a network call or an API key.
"""
from __future__ import annotations

import pytest

from config import settings
from graph import llm
from graph.llm import (
    LLMConfigurationError,
    LLMUnavailableError,
    MalformedResponseError,
    SchemaError,
    generate_json,
)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class ScriptedModel:
    """Returns each queued response in turn; raises whatever is queued instead."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(messages)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeMessage(item)


@pytest.fixture
def fake_model(monkeypatch):
    """Install a scripted model in place of the real provider client."""

    def install(*responses):
        model = ScriptedModel(*responses)
        monkeypatch.setattr(llm, "get_chat_model", lambda: model)
        return model

    return install


def require_ab(payload):
    if "a" not in payload:
        raise SchemaError('"a" is required')
    return {"a": payload["a"]}


class TestGenerateJson:
    def test_returns_a_validated_payload(self, fake_model):
        fake_model('{"a": 1, "extra": "dropped"}')
        result = generate_json(node="t", system="s", user="u", validator=require_ab)
        assert result.payload == {"a": 1}
        assert result.attempts == 1
        assert result.repairs == ()

    def test_retries_once_on_a_bad_shape_and_recovers(self, fake_model):
        model = fake_model('{"b": 2}', '{"a": 1}')
        result = generate_json(node="t", system="s", user="u", validator=require_ab)
        assert result.payload == {"a": 1}
        assert result.attempts == 2
        assert result.repairs == ('"a" is required',)
        assert len(model.calls) == 2

    def test_the_retry_tells_the_model_what_was_wrong(self, fake_model):
        model = fake_model('{"b": 2}', '{"a": 1}')
        generate_json(node="t", system="s", user="u", validator=require_ab)
        followup = "\n".join(str(message.content) for message in model.calls[1])
        assert '"a" is required' in followup
        assert '{"b": 2}' in followup  # the bad output is echoed back

    def test_gives_up_after_the_configured_attempts(self, fake_model, monkeypatch):
        monkeypatch.setattr(settings, "LLM_JSON_ATTEMPTS", 3)
        model = fake_model('{"b": 1}', "not json at all", '{"c": 3}')
        with pytest.raises(MalformedResponseError, match="3 attempts"):
            generate_json(node="t", system="s", user="u", validator=require_ab)
        assert len(model.calls) == 3

    def test_never_substitutes_content_on_failure(self, fake_model, monkeypatch):
        """The property that matters most: a failure produces an exception, not
        a plausible-looking payload that would reach a reviewer as real copy."""
        monkeypatch.setattr(settings, "LLM_JSON_ATTEMPTS", 1)
        fake_model("I'm sorry, I can't help with that request.")
        with pytest.raises(MalformedResponseError):
            generate_json(node="t", system="s", user="u", validator=require_ab)

    def test_transport_failure_is_not_retried_here(self, fake_model):
        # The provider client already retries connection errors internally;
        # re-asking a dead endpoint two more times just delays the failure.
        model = fake_model(ConnectionError("connection reset"), '{"a": 1}')
        with pytest.raises(LLMUnavailableError, match="connection reset"):
            generate_json(node="t", system="s", user="u", validator=require_ab)
        assert len(model.calls) == 1

    def test_handles_content_block_responses(self, fake_model):
        fake_model([
            {"type": "thinking", "thinking": "considering {options}"},
            {"type": "text", "text": '{"a": 7}'},
        ])
        assert generate_json(node="t", system="s", user="u", validator=require_ab).payload == {"a": 7}

    def test_records_provenance(self, fake_model, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-pro")
        fake_model('{"a": 1}')
        result = generate_json(node="t", system="s", user="u", validator=require_ab)
        assert result.provider == "gemini"
        assert result.model == "gemini-2.5-pro"


class TestConfiguration:
    def test_missing_key_is_reported_by_name(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
        with pytest.raises(LLMConfigurationError, match="GEMINI_API_KEY"):
            llm.check_configuration()

    @pytest.mark.parametrize("key", ["dummy-key", "your-key-here", "changeme", "TODO", "xxx"])
    def test_placeholder_keys_are_treated_as_missing(self, monkeypatch, key):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "GEMINI_API_KEY", key)
        with pytest.raises(LLMConfigurationError):
            llm.check_configuration()

    def test_a_real_looking_key_passes(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "AIzaSyB-not-a-real-one-but-plausible")
        llm.check_configuration()

    def test_unknown_provider_is_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "llamafile")
        with pytest.raises(LLMConfigurationError, match="expected one of"):
            llm.active_provider()

    def test_every_supported_provider_has_a_config_block(self):
        for provider in llm.SUPPORTED_PROVIDERS:
            assert provider in llm._provider_configs()
