"""Language-model adapter protocol for prompt completion."""

from dataclasses import dataclass
from typing import Protocol


class ModelTimeoutError(Exception):
    """The model call exceeded its time limit."""


@dataclass(frozen=True)
class Generation:
    """Text returned by a model call, with token counts for tracing."""

    text: str
    input_tokens: int
    output_tokens: int


class ModelAdapter(Protocol):
    """Interface for turning a prompt into generated text.

    Implementations call a local or remote chat/completion model.
    Callers can swap providers as long as they satisfy this protocol.
    """

    provider: str
    model_id: str

    def generate(self, prompt: str) -> Generation:
        """Return the model's completion and token counts for ``prompt``."""
        ...