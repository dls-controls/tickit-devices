from dataclasses import dataclass, field, fields
from typing import Any, List

from tickit_devices.eiger.eiger_schema import ro_str_list, rw_bool, rw_int, rw_state


def monitor_config_keys() -> list[str]:
    return ["buffer_size", "discard_new", "mode"]


@dataclass
class MonitorConfig:
    """Eiger monitor configuration taken from the API spec."""

    mode: str = field(
        default="enabled", metadata=rw_state(allowed_values=["enabled", "disabled"])
    )
    buffer_size: int = field(default=512, metadata=rw_int())
    discard_new: bool = field(default=False, metadata=rw_bool())

    keys: List[str] = field(default_factory=monitor_config_keys, metadata=ro_str_list())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        f = {}
        for field_ in fields(self):
            f[field_.name] = {
                "value": vars(self)[field_.name],
                "metadata": field_.metadata,
            }
        return f[key]

    def __setitem__(self, key: str, value: Any) -> None:  # noqa: D105
        self.__dict__[key] = value
