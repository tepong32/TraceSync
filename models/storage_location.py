from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class StorageLocation:
    """Provider-neutral identity and display text for one stored item."""

    provider_type: str
    native_id: str
    display_location: str

    def __post_init__(self) -> None:
        if not self.provider_type.strip():
            raise ValueError("Storage location provider type is required.")
        if not self.native_id.strip():
            raise ValueError("Storage location native identity is required.")
        if not self.display_location.strip():
            raise ValueError("Storage location display text is required.")

    @classmethod
    def local(cls, path: str | Path, *, resolve: bool = True) -> "StorageLocation":
        if resolve:
            value = str(Path(path).resolve())
        else:
            value = str(path)
        return cls(
            provider_type="local",
            native_id=value,
            display_location=value,
        )

    def as_local_path(self) -> Path:
        if self.provider_type.casefold() != "local":
            raise TypeError("Only local storage locations can be converted to pathlib.Path.")
        return Path(self.native_id)

    def to_dict(self) -> dict[str, str]:
        return {
            "provider_type": self.provider_type,
            "native_id": self.native_id,
            "display_location": self.display_location,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StorageLocation":
        return cls(
            provider_type=str(data["provider_type"]),
            native_id=str(data["native_id"]),
            display_location=str(data["display_location"]),
        )

    def __str__(self) -> str:
        return self.display_location
