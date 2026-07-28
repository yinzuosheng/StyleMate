"""Vision gateway abstraction and DashScope implementation."""

import base64
import json
import os
from collections.abc import Mapping
from typing import Any, Protocol

from config.runtime import RuntimeSettings


class VisionGateway(Protocol):
    def analyze(self, image_bytes: bytes, mime_type: str, user_note: str) -> dict: ...


class VisionError(RuntimeError):
    """Base class for errors that can fall back to manual garment entry."""


class VisionUnavailable(VisionError):
    """Raised only when a vision request cannot start without a configured key."""


class VisionTransportError(VisionError):
    """Raised when the configured vision provider cannot complete a request."""


class VisionResponseError(VisionError, ValueError):
    """Raised when the provider gives no usable structured response."""


class DashScopeVisionGateway:
    """Small, injectable DashScope adapter that never logs image payloads."""

    def __init__(
        self,
        settings: RuntimeSettings,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        self.settings = settings
        self.api_key = api_key if api_key is not None else os.getenv("DASHSCOPE_API_KEY")
        self.client = client

    def analyze(self, image_bytes: bytes, mime_type: str, user_note: str) -> dict:
        if not self.api_key:
            raise VisionUnavailable("Vision service is not configured")

        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        response = self._call_provider(data_url, user_note)
        text = self._response_text(response)
        if not text.strip():
            raise VisionResponseError("Vision service returned an empty response")

        try:
            payload = json.loads(self._remove_code_fence(text))
        except json.JSONDecodeError as exc:
            raise VisionResponseError("Vision service returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise VisionResponseError("Vision service returned a non-object JSON response")
        return payload

    def _call_provider(self, data_url: str, user_note: str) -> Any:
        client = self.client
        if client is None:
            try:
                import dashscope
            except ImportError as exc:  # pragma: no cover - dependency is declared at runtime
                raise VisionUnavailable("Vision client is unavailable") from exc
            client = dashscope.MultiModalConversation

        prompt = (
            "Identify this garment. Return only a JSON object with exactly these keys: "
            "name, category, primary_color, material, seasons, styles, confidence. "
            "Use arrays for seasons and styles, and confidence values between 0 and 1."
        )
        if user_note.strip():
            prompt = f"{prompt} User note: {user_note.strip()}"
        try:
            return client.call(
                model=self.settings.vision_model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [{"image": data_url}, {"text": prompt}],
                    }
                ],
                api_key=self.api_key,
                timeout=self.settings.model_timeout_seconds,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise VisionTransportError("Vision request failed") from exc

    @staticmethod
    def _remove_code_fence(text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise VisionResponseError("Vision service returned an incomplete code fence")
        return "\n".join(lines[1:-1]).strip()

    @classmethod
    def _response_text(cls, response: Any) -> str:
        output = cls._value(response, "output")
        choices = cls._value(output, "choices")
        if not choices:
            raise VisionResponseError("Vision service returned no choices")
        message = cls._value(choices[0], "message")
        content = cls._value(message, "content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = [cls._value(item, "text") for item in content]
            return "".join(text for text in texts if isinstance(text, str))
        raise VisionResponseError("Vision service returned no text content")

    @staticmethod
    def _value(value: Any, name: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(name)
        return getattr(value, name, None)
