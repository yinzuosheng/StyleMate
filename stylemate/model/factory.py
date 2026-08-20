"""Lazy OpenAI-compatible chat model construction."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from stylemate.config.runtime import RuntimeSettings


def build_chat_model(
    settings: RuntimeSettings, api_key: str | None
) -> BaseChatModel | None:
    if not api_key or not api_key.strip():
        return None
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    return ChatOpenAI(
        model=settings.text_model_name,
        api_key=SecretStr(api_key.strip()),
        base_url=settings.text_base_url,
        timeout=settings.model_timeout_seconds,
        max_retries=0,
        temperature=0.2,
    )


def build_chat_model_from_env(settings: RuntimeSettings) -> BaseChatModel | None:
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or ""
    )
    return build_chat_model(settings, api_key)


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]: ...


class ChatModelFactory(BaseModelFactory):
    def __init__(
        self,
        settings: RuntimeSettings | None = None,
        api_key: str | None = None,
    ):
        self.settings, self.api_key = settings, api_key

    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return build_chat_model(
            self.settings or RuntimeSettings.from_env(), self.api_key
        )


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return None


# Legacy public names are intentionally inert; callers must opt in via builders.
chat_model = None
embed_model = None


__all__ = ["build_chat_model", "build_chat_model_from_env"]
