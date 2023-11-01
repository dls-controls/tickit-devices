from dataclasses import dataclass, field, fields
from typing import Any, List

from tickit_devices.eiger.eiger_schema import ro_bool, ro_int, ro_state, ro_str_list


def monitor_status_keys() -> list[str]:
    # TO DO: The real detector does not have errors
    return ["buffer_fill_level", "buffer_free", "dropped", "error", "state"]


@dataclass
class MonitorStatus:
    """Eiger monitor status taken from the API spec."""

    error: List[str] = field(default_factory=lambda: [], metadata=ro_str_list())
    buffer_fill_level: int = field(default=2, metadata=ro_int())
    buffer_free: bool = field(default_factory=bool, metadata=ro_bool())
    dropped: int = field(default=0, metadata=ro_int())
    state: str = field(
        default="normal", metadata=ro_state(allowed_values=["normal", "overflow"])
    )
    keys: List[str] = field(default_factory=monitor_status_keys, metadata=ro_str_list())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        f = {}
        for field_ in fields(self):
            f[field_.name] = {
                "value": vars(self)[field_.name],
                "metadata": field_.metadata,
            }
        return f[key]
