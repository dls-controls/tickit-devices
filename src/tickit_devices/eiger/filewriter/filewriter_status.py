from dataclasses import dataclass, field, fields
from typing import Any, List

from tickit_devices.eiger.eiger_schema import ro_str, ro_str_list


@dataclass
class FileWriterStatus:
    """Eiger filewriter status taken from the API spec."""

    state: str = field(default="ready", metadata=ro_str())
    error: List[str] = field(default_factory=lambda: [], metadata=ro_str_list())
    files: List[str] = field(default_factory=lambda: [], metadata=ro_str_list())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        for field_ in fields(self):
            if field_.name == key:
                return {"value": vars(self)[field_.name], "metadata": field_.metadata}
        raise ValueError(f"No field with name {key}")
