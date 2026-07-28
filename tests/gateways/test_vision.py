import json

import pytest

from config.runtime import RuntimeSettings
from gateways.vision import DashScopeVisionGateway, VisionUnavailable


class RecordingDashScope:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
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


def test_gateway_requests_json_and_removes_a_markdown_fence():
    expected = {"name": "coat", "category": "outerwear"}
    client = RecordingDashScope(
        {"output": {"choices": [{"message": {"content": "```json\n" + json.dumps(expected) + "\n```"}}]}}
    )
    gateway = DashScopeVisionGateway(settings=settings(), api_key="test-key", client=client)

    result = gateway.analyze(b"image", "image/jpeg", "note")

    assert result == expected
    assert client.calls[0]["timeout"] == 30
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    image_part = client.calls[0]["messages"][0]["content"][0]
    assert image_part["image"].startswith("data:image/jpeg;base64,")
