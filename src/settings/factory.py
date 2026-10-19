"""Build the model and applicant store named in the environment."""

from model.base import ModelAdapter
from model.ollama import OllamaAdapter
from settings.config import Settings
from settings.enums import ModelProvider, StoreProvider
from store.base import Store
from store.json import JsonStore


def build_model(settings: Settings) -> ModelAdapter:
    """Return the generation model named by ``settings``."""
    if settings.generation_provider is ModelProvider.OLLAMA:
        return OllamaAdapter(
            model_id=settings.generation_model,
            host=settings.ollama_host,
        )
    raise ValueError(f"unknown generation provider: {settings.generation_provider}")


def build_store(settings: Settings) -> Store:
    """Return the applicant store named by ``settings``."""
    if settings.store_provider is StoreProvider.JSON:
        return JsonStore(settings.applicants_path)
    raise ValueError(f"unknown store provider: {settings.store_provider}")
