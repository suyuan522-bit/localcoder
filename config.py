"""Configuration values and safe environment loading for LocalCoder."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import os

MAX_STEPS = 30
MAX_DYNAMIC_MESSAGES = 24
READ_FILE_MAX_LINES = 200
LIST_FILES_MAX_ENTRIES = 500
SEARCH_MAX_MATCHES = 100
MAX_TOOL_OUTPUT_CHARS = 12_000
MAX_WRITE_FILE_CHARS = 1_000_000
DEFAULT_COMMAND_TIMEOUT_SECONDS = 30
MAX_COMMAND_TIMEOUT_SECONDS = 60


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is unavailable."""


@dataclass(frozen=True, slots=True)
class LLMConfig:
    """OpenAI-compatible provider configuration without secret repr leakage."""

    api_key: str = field(repr=False)
    base_url: str
    model: str


def load_llm_config(environ: Mapping[str, str] | None = None) -> LLMConfig:
    """Load required LLM settings from an environment-like mapping."""

    source = os.environ if environ is None else environ
    names = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")
    values = {name: source.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigurationError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return LLMConfig(
        api_key=values["LLM_API_KEY"],
        base_url=values["LLM_BASE_URL"],
        model=values["LLM_MODEL"],
    )
