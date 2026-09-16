"""Configuration tests that do not require provider credentials or network access."""

from __future__ import annotations

import os

from sra_schools.config import (
    GROQ_BASE_URL,
    GROQ_DEFAULT_MODEL,
    LlmSettings,
    OPENAI_BASE_URL,
    Settings,
    _load_dotenv,
)
from sra_schools.extract.llm import LlmExtractor


_ENV_KEYS = (
    "SRA_LLM_API_KEY",
    "OPENAI_API_KEY",
    "SRA_GROQ_API_KEY",
    "GROQ_API_KEY",
    "SRA_LLM_BASE_URL",
    "SRA_LLM_MODEL",
)


def _clear_llm_env(monkeypatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_groq_key_selects_groq_defaults(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

    settings = LlmSettings.from_env()

    assert settings.api_key == "groq-test-key"
    assert settings.base_url == GROQ_BASE_URL
    assert settings.model == GROQ_DEFAULT_MODEL
    assert LlmExtractor(settings)._endpoint() == f"{GROQ_BASE_URL}/chat/completions"


def test_prefixed_groq_key_and_generic_overrides(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SRA_GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("SRA_LLM_BASE_URL", "https://groq-proxy.example/v1/")
    monkeypatch.setenv("SRA_LLM_MODEL", "custom-groq-model")

    settings = LlmSettings.from_env()

    assert settings.api_key == "groq-test-key"
    assert settings.base_url == "https://groq-proxy.example/v1/"
    assert settings.model == "custom-groq-model"
    assert LlmExtractor(settings)._endpoint() == "https://groq-proxy.example/v1/chat/completions"


def test_dotenv_loader_enables_groq_without_overriding_process_env(tmp_path, monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.delenv("SRA_USE_LLM", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SRA_USE_LLM=1\nGROQ_API_KEY=dotenv-groq-key\nSRA_LLM_MODEL=dotenv-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SRA_LLM_MODEL", "process-model")

    _load_dotenv(env_file)
    settings = Settings.from_env()

    assert settings.use_llm is True
    assert settings.llm.api_key == "dotenv-groq-key"
    assert settings.llm.model == "process-model"
    assert os.environ["GROQ_API_KEY"] == "dotenv-groq-key"


def test_explicit_generic_key_takes_precedence_over_groq(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SRA_LLM_API_KEY", "generic-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

    settings = LlmSettings.from_env()

    assert settings.api_key == "generic-test-key"
    assert settings.base_url == OPENAI_BASE_URL
