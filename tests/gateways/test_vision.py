import json

import pytest

from stylemate.config.runtime import RuntimeSettings
from stylemate.gateways.vision import (
    DashScopeVisionGateway,
    OpenAICompatibleVisionGateway,
    VisionNotFashion,
    VisionResponseError,
    VisionUnavailable,
)


class RecordingDashScope:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class SDKCompatibleDashScope:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def call(self, *, model, messages, api_key, request_timeout, response_format):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "api_key": api_key,
                "request_timeout": request_timeout,
                "response_format": response_format,
            }
        )
        return self.response


def settings():
    return RuntimeSettings(
        app_mode="demo",
        vision_model_name="vision-test",
        text_model_name="text-test",
        model_timeout_seconds=30,
    )


def test_gateway_without_a_key_defers_failure_until_analyze(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    gateway = DashScopeVisionGateway(settings=settings(), api_key=None)

    with pytest.raises(VisionUnavailable):
        gateway.analyze(b"image", "image/jpeg", "note")


def test_gateway_uses_dashscope_request_timeout_and_removes_a_markdown_fence():
    expected = {
        "name": "coat",
        "category": "outerwear",
        "primary_color": "beige",
        "material": "cotton",
        "seasons": ["spring"],
        "styles": ["minimal"],
        "confidence": {"category": 0.9},
    }
    client = SDKCompatibleDashScope(
        {"output": {"choices": [{"message": {"content": "```json\n" + json.dumps(expected) + "\n```"}}]}}
    )
    gateway = DashScopeVisionGateway(settings=settings(), api_key="test-key", client=client)

    result = gateway.analyze(b"image", "image/jpeg", "note")

    assert result == expected
    assert client.calls[0]["request_timeout"] == 30
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    image_part = client.calls[0]["messages"][0]["content"][0]
    assert image_part["image"].startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "coat",
            "category": "outerwear",
            "primary_color": "beige",
            "material": "cotton",
            "seasons": ["spring"],
            "styles": ["minimal"],
            "confidence": {"category": 0.9},
            "unexpected": "not allowed",
        },
        {
            "name": "",
            "category": "outerwear",
            "primary_color": "beige",
            "material": "cotton",
            "seasons": ["spring"],
            "styles": ["minimal"],
            "confidence": {"category": 0.9},
        },
        {
            "name": "coat",
            "category": "outerwear",
            "primary_color": "beige",
            "material": "cotton",
            "seasons": ["spring"],
            "styles": ["minimal"],
            "confidence": {"category": 1.1},
        },
    ],
)
def test_gateway_rejects_malformed_provider_schema(payload):
    client = RecordingDashScope({"output": {"choices": [{"message": {"content": json.dumps(payload)}}]}})
    gateway = DashScopeVisionGateway(settings=settings(), api_key="test-key", client=client)

    with pytest.raises(VisionResponseError, match="malformed"):
        gateway.analyze(b"image", "image/jpeg", "")


def test_gateway_rejects_a_non_fashion_image_before_garment_schema_validation():
    payload = {
        "is_fashion_item": False,
        "item_type": "not_fashion",
        "fashion_confidence": 0.99,
        "rejection_reason": "animal photo",
    }
    client = RecordingDashScope(
        {"output": {"choices": [{"message": {"content": json.dumps(payload)}}]}}
    )
    gateway = DashScopeVisionGateway(settings=settings(), api_key="test-key", client=client)

    with pytest.raises(VisionNotFashion, match="clothing"):
        gateway.analyze(b"image", "image/jpeg", "这是眼镜")


def test_gateway_rejects_low_fashion_confidence():
    payload = {
        "is_fashion_item": True,
        "item_type": "garment",
        "fashion_confidence": 0.42,
        "name": "coat",
        "category": "outerwear",
        "primary_color": "beige",
        "material": "cotton",
        "seasons": ["spring"],
        "styles": ["minimal"],
        "confidence": {"category": 0.9},
    }
    client = RecordingDashScope(
        {"output": {"choices": [{"message": {"content": json.dumps(payload)}}]}}
    )
    gateway = DashScopeVisionGateway(settings=settings(), api_key="test-key", client=client)

    with pytest.raises(VisionNotFashion, match="confidence"):
        gateway.analyze(b"image", "image/jpeg", "")


def test_openai_compatible_gateway_sends_a_standard_image_url_message():
    expected = {
        "name": "coat",
        "category": "outerwear",
        "primary_color": "beige",
        "material": "cotton",
        "seasons": ["spring"],
        "styles": ["minimal"],
        "confidence": {"category": 0.9},
    }

    class Completions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            message = type("Message", (), {"content": json.dumps(expected)})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    completions = Completions()
    client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": completions})()},
    )()
    configured = settings().__class__(
        **{
            **settings().__dict__,
            "vision_base_url": "https://vision.example/v1",
        }
    )
    gateway = OpenAICompatibleVisionGateway(configured, "test-key", client)

    result = gateway.analyze(b"image", "image/jpeg", "note")

    assert result == expected
    image_part = completions.calls[0]["messages"][0]["content"][0]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_openai_compatible_gateway_normalizes_scalar_confidence():
    payload = {
        "name": "shirt",
        "category": "top",
        "primary_color": "blue",
        "material": "cotton",
        "seasons": ["spring"],
        "styles": ["casual"],
        "confidence": 0.85,
    }

    class Completions:
        def create(self, **_kwargs):
            message = type("Message", (), {"content": json.dumps(payload)})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": Completions()})()},
    )()
    configured = settings().__class__(
        **{
            **settings().__dict__,
            "vision_base_url": "https://vision.example/v1",
        }
    )

    result = OpenAICompatibleVisionGateway(
        configured, "test-key", client
    ).analyze(b"image", "image/jpeg", "")

    assert result["confidence"] == {"overall": 0.85}
