from dataclasses import dataclass, field, fields
from typing import Any, List

from tickit_devices.eiger.eiger_schema import ro_int, ro_state, ro_str_list


def stream_status_keys() -> list[str]:
    return ["error", "dropped", "state"]


@dataclass
class StreamStatus:
    """Eiger stream status taken from the API spec."""

    state: str = field(default="ready", metadata=ro_state())
    error: List[str] = field(default_factory=lambda: [], metadata=ro_str_list())
    dropped: int = field(default=0, metadata=ro_int())

    keys: List[str] = field(default_factory=stream_status_keys, metadata=ro_str_list())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        f = {}
        for field_ in fields(self):
            f[field_.name] = {
                "value": vars(self)[field_.name],
                "metadata": field_.metadata,
            }
        return f[key]
