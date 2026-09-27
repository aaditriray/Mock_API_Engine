import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_directory: Path

    @classmethod
    def from_environment(cls, data_directory: Path | None = None) -> "Settings":
        configured_directory = data_directory or Path(
            os.environ.get("MOCK_API_DATA_DIR", "data")
        )
        return cls(data_directory=configured_directory.expanduser())