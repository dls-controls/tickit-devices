"""Eiger_status temporary docstring - to be changed."""

from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any, List

from .eiger_schema import (
    ro_datetime,
    ro_float,
    ro_state,
    ro_str_list,
)


class State(Enum):
    """Possible states of the Eiger detector."""

    NA = "na"
    READY = "ready"
    INITIALIZE = "initialize"
    CONFIGURE = "configure"
    ACQUIRE = "acquire"
    IDLE = "idle"
    TEST = "test"
    ERROR = "error"


def status_keys() -> list[str]:
    # TO DO: The real detector does not have errors
    return ["humidity", "state", "temperature", "time", "error"]


@dataclass
class EigerStatus:
    """Stores the status parameters of the Eiger detector."""

    state: State = field(
        default=State.IDLE,
        metadata=ro_state(allowed_values=[state.value for state in State]),
    )
    error: List[str] = field(default_factory=list, metadata=ro_str_list())
    temperature: float = field(default=24.5, metadata=ro_float())
    humidity: float = field(default=0.2, metadata=ro_float())
    time: datetime = field(default=datetime.now(), metadata=ro_datetime())
    dcu_buffer_free: float = field(default=0.5, metadata=ro_float())

    keys: List[str] = field(default_factory=status_keys, metadata=ro_str_list())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        for field_ in fields(self):
            if field_.name == key:
                return {"value": vars(self)[field_.name], "metadata": field_.metadata}
        raise ValueError(f"No field with name {key}")
