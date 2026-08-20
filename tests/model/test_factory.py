from stylemate.config.runtime import RuntimeSettings
from stylemate.model.factory import build_chat_model, build_chat_model_from_env


def settings() -> RuntimeSettings:
    return RuntimeSettings(
        app_mode="demo",
        vision_model_name="vision-test",
        text_model_name="chat-test",
        text_provider_name="compatible-test",
        text_base_url="https://provider.example/v1",
    )


def test_chat_model_is_disabled_without_a_key():
    assert build_chat_model(settings(), "") is None


def test_chat_model_from_env_uses_the_configured_primary(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    model = build_chat_model_from_env(settings())

    assert model is not None
    assert model.model_name == "chat-test"
    assert str(model.openai_api_base) == "https://provider.example/v1"

