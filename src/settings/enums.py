"""Fixed names for the model and the applicant store."""

from enum import StrEnum


class ModelProvider(StrEnum):
    OLLAMA = "ollama"


class StoreProvider(StrEnum):
    JSON = "json"