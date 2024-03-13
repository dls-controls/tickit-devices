import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

import pydantic
from tickit.core.components.component import ComponentConfig
from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime
from typing_extensions import get_type_hints


@dataclass
class Param:
    """
    Representation of the internal configuration of the Zebra.
    Sometimes is shared state between multiple blocks.
    """

    reg: int
    blocks: List[str]


@dataclass
class Mux:
    """
    Representation of the internal mapping of the Zebra.
    e.g If AND1_INP1=Mux(0x08, ...) is set to 0x09, then
    AND1_INP1 should take the same input as AND1_INP2=Mux(0x09, ...)

    """

    reg: int
    block: Optional[str] = None


DIVS = [f"DIV{i}" for i in range(1, 5)]
PULSES = [f"PULSE{i}" for i in range(1, 5)]
GATES = [f"GATE{i}" for i in range(1, 5)]

register_types: Dict[str, Union[Param, Mux]] = dict(
    AND1_INV=Param(0x00, ["AND1"]),
    AND2_INV=Param(0x01, ["AND2"]),
    AND3_INV=Param(0x02, ["AND3"]),
    AND4_INV=Param(0x03, ["AND4"]),
    AND1_ENA=Param(0x04, ["AND1"]),
    AND2_ENA=Param(0x05, ["AND2"]),
    AND3_ENA=Param(0x06, ["AND3"]),
    AND4_ENA=Param(0x07, ["AND4"]),
    AND1_INP1=Mux(0x08, "AND1"),
    AND1_INP2=Mux(0x09, "AND1"),
    AND1_INP3=Mux(0x0A, "AND1"),
    AND1_INP4=Mux(0x0B, "AND1"),
    AND2_INP1=Mux(0x0C, "AND2"),
    AND2_INP2=Mux(0x0D, "AND2"),
    AND2_INP3=Mux(0x0E, "AND2"),
    AND2_INP4=Mux(0x0F, "AND2"),
    AND3_INP1=Mux(0x10, "AND3"),
    AND3_INP2=Mux(0x11, "AND3"),
    AND3_INP3=Mux(0x12, "AND3"),
    AND3_INP4=Mux(0x13, "AND3"),
    AND4_INP1=Mux(0x14, "AND4"),
    AND4_INP2=Mux(0x15, "AND4"),
    AND4_INP3=Mux(0x16, "AND4"),
    AND4_INP4=Mux(0x17, "AND4"),
    OR1_INV=Param(0x18, ["OR1"]),
    OR2_INV=Param(0x19, ["OR2"]),
    OR3_INV=Param(0x1A, ["OR3"]),
    OR4_INV=Param(0x1B, ["OR4"]),
    OR1_ENA=Param(0x1C, ["OR1"]),
    OR2_ENA=Param(0x1D, ["OR2"]),
    OR3_ENA=Param(0x1E, ["OR3"]),
    OR4_ENA=Param(0x1F, ["OR4"]),
    OR1_INP1=Mux(0x20, "OR1"),
    OR1_INP2=Mux(0x21, "OR1"),
    OR1_INP3=Mux(0x22, "OR1"),
    OR1_INP4=Mux(0x23, "OR1"),
    OR2_INP1=Mux(0x24, "OR2"),
    OR2_INP2=Mux(0x25, "OR2"),
    OR2_INP3=Mux(0x26, "OR2"),
    OR2_INP4=Mux(0x27, "OR2"),
    OR3_INP1=Mux(0x28, "OR3"),
    OR3_INP2=Mux(0x29, "OR3"),
    OR3_INP3=Mux(0x2A, "OR3"),
    OR3_INP4=Mux(0x2B, "OR3"),
    OR4_INP1=Mux(0x2C, "OR4"),
    OR4_INP2=Mux(0x2D, "OR4"),
    OR4_INP3=Mux(0x2E, "OR4"),
    OR4_INP4=Mux(0x2F, "OR4"),
    GATE1_INP1=Mux(0x30, "GATE1"),
    GATE2_INP1=Mux(0x31, "GATE2"),
    GATE3_INP1=Mux(0x32, "GATE3"),
    GATE4_INP1=Mux(0x33, "GATE4"),
    GATE1_INP2=Mux(0x34, "GATE1"),
    GATE2_INP2=Mux(0x35, "GATE2"),
    GATE3_INP2=Mux(0x36, "GATE3"),
    GATE4_INP2=Mux(0x37, "GATE4"),
    DIV1_DIVLO=Param(0x38, ["DIV1"]),
    DIV1_DIVHI=Param(0x39, ["DIV1"]),
    DIV2_DIVLO=Param(0x3A, ["DIV2"]),
    DIV2_DIVHI=Param(0x3B, ["DIV2"]),
    DIV3_DIVLO=Param(0x3C, ["DIV3"]),
    DIV3_DIVHI=Param(0x3D, ["DIV3"]),
    DIV4_DIVLO=Param(0x3E, ["DIV4"]),
    DIV4_DIVHI=Param(0x3F, ["DIV4"]),
    DIV1_INP=Mux(0x40, "DIV1"),
    DIV2_INP=Mux(0x41, "DIV2"),
    DIV3_INP=Mux(0x42, "DIV3"),
    DIV4_INP=Mux(0x43, "DIV4"),
    PULSE1_DLY=Param(0x44, ["PULSE1"]),
    PULSE2_DLY=Param(0x45, ["PULSE2"]),
    PULSE3_DLY=Param(0x46, ["PULSE3"]),
    PULSE4_DLY=Param(0x47, ["PULSE4"]),
    PULSE1_WID=Param(0x48, ["PULSE1"]),
    PULSE2_WID=Param(0x49, ["PULSE2"]),
    PULSE3_WID=Param(0x4A, ["PULSE3"]),
    PULSE4_WID=Param(0x4B, ["PULSE4"]),
    PULSE1_PRE=Param(0x4C, ["PULSE1"]),
    PULSE2_PRE=Param(0x4D, ["PULSE2"]),
    PULSE3_PRE=Param(0x4E, ["PULSE3"]),
    PULSE4_PRE=Param(0x4F, ["PULSE4"]),
    PULSE1_INP=Mux(0x50, "PULSE1"),
    PULSE2_INP=Mux(0x51, "PULSE2"),
    PULSE3_INP=Mux(0x52, "PULSE3"),
    PULSE4_INP=Mux(0x53, "PULSE4"),
    POLARITY=Param(0x54, GATES + DIVS + PULSES),
    QUAD_DIR=Param(0x55, ["QUAD"]),
    QUAD_STEP=Param(0x56, ["QUAD"]),
    PC_ARM_INP=Mux(0x57, "PC"),
    PC_GATE_INP=Mux(0x58, "PC"),
    PC_PULSE_INP=Mux(0x59, "PC"),
    OUT1_TTL=Mux(0x60),
    OUT1_NIM=Mux(0x61),
    OUT1_LVDS=Mux(0x62),
    OUT2_TTL=Mux(0x63),
    OUT2_NIM=Mux(0x64),
    OUT2_LVDS=Mux(0x65),
    OUT3_TTL=Mux(0x66),
    OUT3_OC=Mux(0x67),
    OUT3_LVDS=Mux(0x68),
    OUT4_TTL=Mux(0x69),
    OUT4_NIM=Mux(0x6A),
    OUT4_PECL=Mux(0x6B),
    OUT5_ENCA=Mux(0x6C),
    OUT5_ENCB=Mux(0x6D),
    OUT5_ENCZ=Mux(0x6E),
    OUT5_CONN=Mux(0x6F),
    OUT6_ENCA=Mux(0x70),
    OUT6_ENCB=Mux(0x71),
    OUT6_ENCZ=Mux(0x72),
    OUT6_CONN=Mux(0x73),
    OUT7_ENCA=Mux(0x74),
    OUT7_ENCB=Mux(0x75),
    OUT7_ENCZ=Mux(0x76),
    OUT7_CONN=Mux(0x77),
    OUT8_ENCA=Mux(0x78),
    OUT8_ENCB=Mux(0x79),
    OUT8_ENCZ=Mux(0x7A),
    OUT8_CONN=Mux(0x7B),
    DIV_FIRST=Param(0x7C, DIVS),
    SYS_RESET=Param(0x7E, []),
    SOFT_IN=Param(0x7F, ["SOFT"]),
    POS1_SETLO=Param(0x80, ["POS1"]),
    POS1_SETHI=Param(0x81, ["POS1"]),
    POS2_SETLO=Param(0x82, ["POS2"]),
    POS2_SETHI=Param(0x83, ["POS2"]),
    POS3_SETLO=Param(0x84, ["POS3"]),
    POS3_SETHI=Param(0x85, ["POS3"]),
    POS4_SETLO=Param(0x86, ["POS4"]),
    POS4_SETHI=Param(0x87, ["POS4"]),
    PC_ENC=Param(0x88, ["PC"]),
    PC_TSPRE=Param(0x89, ["PC"]),
    PC_ARM_SEL=Param(0x8A, ["PC"]),
    PC_ARM=Param(0x8B, ["PC"]),
    PC_DISARM=Param(0x8C, ["PC"]),
    PC_GATE_SEL=Param(0x8D, ["PC"]),
    PC_GATE_STARTLO=Param(0x8E, ["PC"]),
    PC_GATE_STARTHI=Param(0x8F, ["PC"]),
    PC_GATE_WIDLO=Param(0x90, ["PC"]),
    PC_GATE_WIDHI=Param(0x91, ["PC"]),
    PC_GATE_NGATELO=Param(0x92, ["PC"]),
    PC_GATE_NGATEHI=Param(0x93, ["PC"]),
    PC_GATE_STEPLO=Param(0x94, ["PC"]),
    PC_GATE_STEPHI=Param(0x95, ["PC"]),
    PC_PULSE_SEL=Param(0x96, ["PC"]),
    PC_PULSE_STARTLO=Param(0x97, ["PC"]),
    PC_PULSE_STARTHI=Param(0x98, ["PC"]),
    PC_PULSE_WIDLO=Param(0x99, ["PC"]),
    PC_PULSE_WIDHI=Param(0x9A, ["PC"]),
    PC_PULSE_STEPLO=Param(0x9B, ["PC"]),
    PC_PULSE_STEPHI=Param(0x9C, ["PC"]),
    PC_PULSE_MAXLO=Param(0x9D, ["PC"]),
    PC_PULSE_MAXHI=Param(0x9E, ["PC"]),
    PC_BIT_CAP=Param(0x9F, ["PC"]),
    PC_DIR=Param(0xA0, ["PC"]),
    PC_PULSE_DLYLO=Param(0xA1, ["PC"]),
    PC_PULSE_DLYHI=Param(0xA2, ["PC"]),
    SYS_VER=Param(0xF0, []),
    SYS_STATERR=Param(0xF1, []),
    SYS_STAT1LO=Param(0xF2, []),
    SYS_STAT1HI=Param(0xF3, []),
    SYS_STAT2LO=Param(0xF4, []),
    SYS_STAT2HI=Param(0xF5, []),
    PC_NUM_CAPLO=Param(0xF6, []),
    PC_NUM_CAPHI=Param(0xF7, []),
)

register_names = {reg.reg: name for name, reg in register_types.items()}
param_types = {name: t for name, t in register_types.items() if isinstance(t, Param)}
mux_types = {name: t for name, t in register_types.items() if isinstance(t, Mux)}

Inputs = TypeVar("Inputs")
Outputs = TypeVar("Outputs")


@dataclass
class Block(Device, ABC, Generic[Inputs, Outputs]):
    name: str
    """
    Blocks take 20ns to propagate a signal across, so we cache the next output value
    and emit it 20ns later.
    """
    previous_outputs: Outputs
    next_outputs: Optional[Outputs] = None
    params: Optional[Dict[str, int]] = None

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        if self.next_outputs:
            self.previous_outputs = self.next_outputs
            self.next_outputs = None
            return DeviceUpdate(self.previous_outputs, call_at=None)
        else:
            self.next_outputs = self._get_next_outputs(inputs)
            return DeviceUpdate(self.previous_outputs, call_at=SimTime(time + 20))

    @abstractmethod
    def _get_next_outputs(self, inputs: Inputs) -> Outputs: ...

    @property
    def num(self):
        match = re.search(r"\d*$", self.name)
        assert match, f"No trailing number in {self.name}"
        return int(match.group())

    def read_mux(self, register: str) -> int:
        return 0

    def set_mux(self, register: str, value: int) -> int:
        return 0


@pydantic.v1.dataclasses.dataclass
class BlockConfig(ComponentConfig, ABC):
    @abstractmethod
    def __call__(self) -> Block:
        """Create a block"""
        ...


def default_filler(typed_dict_type) -> Callable[[], Any]:
    def make_default():
        return {name: typ() for name, typ in get_type_hints(typed_dict_type).items()}

    return make_default


def extract_bit(registers: Dict[str, int], key: str, shift: int) -> bool:
    return bool((registers[key] >> shift) & 1)


def clear_bit(registers: Dict[str, int], key: str, shift: int):
    registers[key] &= ~(1 << shift)


def set_bit(registers: Dict[str, int], key: str, shift: int):
    registers[key] |= 1 << shift


def rising(old: bool, new: bool) -> bool:
    return new and not old


def in_ns(ticks: Optional[int]) -> Optional[SimTime]:
    return None if ticks is None else SimTime(ticks * 20)
