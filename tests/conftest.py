from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.llm_client import LLMResponse, LLMUsage


@pytest.fixture
def mock_llm(monkeypatch):
    """Monkeypatches LLMClient.complete to return canned responses.

    Usage:
        def test_something(mock_llm):
            mock_llm.set_response('{"key": "value"}')
            resp = get_client().complete(messages=[{"role": "user", "content": "hi"}])
            assert resp.text == '{"key": "value"}'
    """

    fake = MagicMock()
    fake.return_value = LLMResponse(text='{"result": "ok"}', usage=LLMUsage(10, 20))

    def set_response(text: str = '{"result": "ok"}', prompt_tokens: int = 10, completion_tokens: int = 20):
        fake.return_value = LLMResponse(text=text, usage=LLMUsage(prompt_tokens, completion_tokens))

    def fake_complete(self, messages, max_tokens=1024, temperature=0.1, use_fast=False):
        fake(messages=messages, max_tokens=max_tokens, temperature=temperature, use_fast=use_fast)
        return fake.return_value

    monkeypatch.setattr("tools.llm_client.LLMClient.complete", fake_complete)

    fake.set_response = set_response
    return fake


@pytest.fixture
def wiki_test_dir(tmp_path: Path) -> Path:
    """Create a minimal wiki directory structure for isolated testing."""
    for sub in ("sources", "entities", "concepts", "syntheses"):
        (tmp_path / sub).mkdir(parents=True)
    (tmp_path / "index.md").write_text("# Index\n")
    return tmp_path
