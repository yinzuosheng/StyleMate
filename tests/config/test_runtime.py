import pytest

from stylemate.config.runtime import RuntimeSettings


def test_runtime_defaults_to_local(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)

    settings = RuntimeSettings.from_env()

    assert settings.app_mode == "local"
    assert settings.max_upload_bytes == 8 * 1024 * 1024
    assert settings.weather_timeout_seconds == 5
    assert settings.model_timeout_seconds == 30


def test_runtime_defaults_include_agent_limits(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("DASHSCOPE_BASE_URL", raising=False)

    settings = RuntimeSettings.from_env()

    assert settings.dashscope_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.embedding_model_name == "text-embedding-v4"
    assert settings.rag_top_k == 4
    assert settings.max_document_bytes == 4 * 1024 * 1024


def test_runtime_reads_configured_provider_endpoints(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "primary")
    monkeypatch.setenv("LLM_BASE_URL", "https://primary.example/v1")
    monkeypatch.setenv("TEXT_MODEL_NAME", "primary-model")
    monkeypatch.setenv("VISION_BASE_URL", "https://vision.example/v1")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embedding.example/v1")

    settings = RuntimeSettings.from_env()

    assert settings.text_provider_name == "primary"
    assert settings.text_base_url == "https://primary.example/v1"
    assert settings.vision_base_url == "https://vision.example/v1"
    assert settings.embedding_base_url == "https://embedding.example/v1"


def test_runtime_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("APP_MODE", "production")

    with pytest.raises(ValueError, match="APP_MODE"):
        RuntimeSettings.from_env()
