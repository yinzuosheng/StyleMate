import pytest

from config.runtime import RuntimeSettings


def test_runtime_defaults_to_local(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)

    settings = RuntimeSettings.from_env()

    assert settings.app_mode == "local"
    assert settings.max_upload_bytes == 8 * 1024 * 1024
    assert settings.weather_timeout_seconds == 5
    assert settings.model_timeout_seconds == 30


def test_runtime_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("APP_MODE", "production")

    with pytest.raises(ValueError, match="APP_MODE"):
        RuntimeSettings.from_env()
