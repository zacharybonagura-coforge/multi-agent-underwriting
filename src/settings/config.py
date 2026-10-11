"""Runtime settings for the underwriting pipeline."""

import os
from dataclasses import dataclass
from pathlib import Path

from settings.enums import ModelProvider, StoreProvider

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Paths and model host read from the environment, with lab defaults."""

    generation_provider: ModelProvider
    generation_model: str
    ollama_host: str
    max_retries: int
    store_provider: StoreProvider
    applicants_path: Path
    runs_dir: Path
    logs_dir: Path
    reviews_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from env vars, falling back to local lab defaults."""
        return cls(
            generation_provider=ModelProvider(
                os.environ.get("GENERATION_PROVIDER", ModelProvider.OLLAMA)
            ),
            generation_model=os.environ.get("GENERATION_MODEL", "qwen3:8b"),
            ollama_host=os.environ.get(
                "OLLAMA_HOST", "http://host.docker.internal:11434"
            ),
            max_retries=int(os.environ.get("MAX_RETRIES", "3")),
            store_provider=StoreProvider(
                os.environ.get("STORE_PROVIDER", StoreProvider.JSON)
            ),
            applicants_path=Path(
                os.environ.get("APPLICANTS_PATH", str(ROOT / "data" / "applicants.json"))
            ),
            runs_dir=Path(os.environ.get("RUNS_DIR", str(ROOT / "runs"))),
            logs_dir=Path(os.environ.get("LOGS_DIR", str(ROOT / "logs"))),
            reviews_path=Path(
                os.environ.get(
                    "REVIEWS_PATH",
                    str(ROOT / "reviews" / "human-review.jsonl"),
                )
            ),
        )