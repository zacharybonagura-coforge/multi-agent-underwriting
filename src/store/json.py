"""JSON file adapter for an applicant record store."""


import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class JsonStore:
    """Load or replace the applicant records in one JSON file."""

    def __init__(self, path: Path) -> None:
        """Bind this store to ``path``."""
        self._path = path

    def load(self) -> list[dict[str, Any]]:
        """Read the file and return the applicant records."""
        payload = json.loads(self._path.read_text())
        if not isinstance(payload, list):
            raise TypeError("applicant store must be a JSON array")
        return payload

    def save(self, payload: Mapping[str, Any]) -> None:
        """Write ``records`` as a JSON array to this store's file."""
        self._path.write_text(json.dumps(payload, indent=2) + "\n")