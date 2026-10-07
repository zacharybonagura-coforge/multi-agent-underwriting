"""Store port: load applicant records without tying callers to a file format."""


from collections.abc import Mapping
from typing import Any, Protocol


class Store(Protocol):
    """Source of applicant credit, claims, and asset records."""

    def load(self) -> list[dict[str, Any]]:
        """Return every applicant record in the store."""
        ...
    
    def save(self, payload: Mapping[str, Any]) -> None:
        """Replace the store with ``records``."""
        ...