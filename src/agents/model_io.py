"""Shared prompt rendering and JSON parsing for agents."""

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from prompts.repository import render

MessageT = TypeVar("MessageT", bound=BaseModel)


def render_prompt(prompt_file: str, payload: dict[str, Any]) -> str:
    """Fill ``prompt_file`` with ``payload`` as JSON."""
    return render(prompt_file, payload=json.dumps(payload, default=str))


def parse_message[MessageT: BaseModel](text: str, message_type: type[MessageT], agent: str) -> MessageT:
    """Parse the JSON object in ``text`` into ``message_type``."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"{agent} model returned no JSON object")
    try:
        return message_type.model_validate_json(text[start : end + 1])
    except ValidationError as exc:
        raise ValueError(f"{agent} model returned an unusable response") from exc
