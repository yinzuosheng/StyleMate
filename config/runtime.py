from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RuntimeSettings:
    app_mode: str
    vision_model_name: str
    text_model_name: str
    max_upload_bytes: int = 8 * 1024 * 1024
    weather_timeout_seconds: int = 5
    model_timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "RuntimeSettings":
        mode = os.getenv("APP_MODE", "local").strip().lower()
        if mode not in {"demo", "local"}:
            raise ValueError("APP_MODE must be 'demo' or 'local'")
        return cls(
            app_mode=mode,
            vision_model_name=os.getenv("VISION_MODEL_NAME", "qwen-vl-plus"),
            text_model_name=os.getenv("TEXT_MODEL_NAME", "qwen-plus"),
        )
