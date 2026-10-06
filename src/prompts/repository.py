"""Load versioned prompt files and fill {{placeholders}}."""

from pathlib import Path

_DIR = Path(__file__).resolve().parent


def render(prompt_file: str, **fields: str) -> str:
    """Return ``prompt_file`` with each ``{{field}}`` replaced."""
    text = (_DIR / f"{prompt_file}").read_text(encoding="utf-8")
    for key, value in fields.items():
        text = text.replace("{{" + key + "}}", value)
    return text