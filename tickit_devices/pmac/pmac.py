from dataclasses import dataclass
from typing import Dict

from tickit.adapters.composed import ComposedAdapter
from tickit.adapters.interpreters.command import CommandInterpreter
from tickit.adapters.interpreters.command.regex_command import RegexCommand
from tickit.adapters.interpreters.wrappers import (
    BeheadingInterpreter,
    JoiningInterpreter,
    SplittingInterpreter,
)
from tickit.adapters.servers.tcp import TcpServer
from tickit.core.components.component import Component, ComponentConfig
from tickit.core.components.device_simulation import DeviceSimulation
from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.utils.byte_format import ByteFormat
from tickit.utils.compat.typing_compat import TypedDict


class PMACAxis:
    def __init__(self):
        self.ivars = dict()
        self.ivars[13] = 10000
        self.ivars[14] = -10000
        self.ivars[31] = 50
        self.ivars[32] = 50
        self.ivars[33] = 50


class PMACDevice(Device):

    Inputs: TypedDict = TypedDict("Inputs", {"flux": float})
    Outputs: TypedDict = TypedDict("Outputs", {"flux": float})

    def __init__(self) -> None:
        self.axes = {
            1: PMACAxis(),
            2: PMACAxis(),
            3: PMACAxis(),
            4: PMACAxis(),
            5: PMACAxis(),
            6: PMACAxis(),
            7: PMACAxis(),
            8: PMACAxis(),
        }
        self.system_ivars: Dict = dict()
        self.system_ivars[20] = "$78400"
        self.system_ivars[21] = "$0"
        self.system_ivars[22] = "$0"
        self.system_ivars[23] = "$0"
        self.other_ivars: Dict = dict()

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        print("Updating\n")
        return DeviceUpdate(self.Outputs(flux=2.0), None)


class PMACAdapter(ComposedAdapter):

    device: PMACDevice

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1025,
    ) -> None:
        """A PMAC which instantiates a TcpServer with configured host and port.

        Args:
            device (Device): The device which this adapter is attached to
            raise_interrupt (Callable): A callback to request that the device is
                updated immediately.
            host (Optional[str]): The host address of the TcpServer. Defaults to
                "localhost".
            port (Optional[int]): The bound port of the TcpServer. Defaults to 1025.
        """
        super().__init__(
            TcpServer(host, port, ByteFormat(b"%b\n")),
            BeheadingInterpreter(
                JoiningInterpreter(
                    SplittingInterpreter(CommandInterpreter(), b" "), b""
                ),
                header_size=8,
            ),
        )

    @RegexCommand(rb"\r?\n?")
    async def parse_just_bytes(self):
        return b"\r"

    @RegexCommand(rb"(?i:CID)\r?\n?")
    async def get_cid(self):
        return b"603382\r"

    @RegexCommand(rb"(?i:CPU)\r?\n?")
    async def get_cpu(self):
        return b"DSP56321\r"

    @RegexCommand(rb"#([1-8])[pP]\r?\n?")
    async def get_axis_position(self, axis_no: int):
        return str(1.0).encode() + b"1\r"

    @RegexCommand(rb"#([1-8])[fF]\r?\n?")
    async def get_axis_following_error(self):
        # target - current
        return b"0\r"

    @RegexCommand(rb"#([1-8])\?\r?\n?")
    async def get_axis_status(self):
        return b"880000018401\r"

    @RegexCommand(rb"[mM]([0-9]{1,4})\r?\n?")
    async def m_var(self):
        return b"1\r"

    @RegexCommand(rb"[iI]([0-9]{1,2})\r?\n?")
    async def read_system_ivar(self, ivar: int):
        """Regex bytestring command that returns the value of a specific system ivar.

        Args:
            ivar (int): the ivar to read.
        """
        value = self.device.system_ivars.get(ivar, None)
        if value is None:
            self.device.system_ivars[ivar] = 0
        return f"{self.device.system_ivars[ivar]}\r".encode()

    @RegexCommand(rb"[iI]([0-9]{1,2})=\$?(\d+(?:.\d+)?)\r?\n?")
    async def write_system_ivar(self, ivar: int, value: float):
        """Regex bytestring command that sets the value of a specific system ivar.

        Args:
            ivar (int): the ivar to set.
            value (float): the value to set the ivar to.
        """
        self.device.system_ivars[ivar] = value
        return b"\r"

    @RegexCommand(rb"[iI]([0-9])([0-9]{2})\r?\n?")
    async def read_axis_var(self, axis: int, ivar: int):
        """Regex bytestring command that returns the value of a specific axis ivar.

        Args:
            axis (int): the axis to read ivars from.
            ivar (int): the ivar to read.
        """
        value = self.device.axes[axis].ivars.get(ivar, None)
        if value is None:
            self.device.axes[axis].ivars[ivar] = 0
        return f"{self.device.axes[axis].ivars[ivar]}\r".encode()

    @RegexCommand(rb"[iI]([0-9])([0-9]{2})=-?(\d+(?:.\d+)?)\r?\n?")
    async def write_axis_ivar(self, axis: int, ivar: int, value: float):
        """Regex bytestring command that sets the value of a specific axis ivar.

        Args:
            axis (int): the axis to set ivars on.
            ivar (int): the ivar to set.
            value (float): the value to set the ivar to.
        """
        self.device.axes[axis].ivars[ivar] = value
        return b"\r"

    @RegexCommand(rb"[iI]([0-9]{4})\r?\n?")
    async def read_other_ivar(self, ivar: int):
        """Regex bytestring command that returns the value of a specific ivar.

        Args:
            ivar (int): the ivar to read.
        """
        value = self.device.other_ivars.get(ivar, None)
        if value is None:
            self.device.other_ivars[ivar] = 0
        return f"{self.device.other_ivars[ivar]}\r".encode()

    @RegexCommand(rb"[iI]([0-9]{4})=-?(\d+(?:\.\d+)?)\r?\n?")
    async def write_other_var(self, ivar: int, value: float):
        """Regex bytestring command that sets the value of a specific ivar.

        Args:
            ivar (int): the ivar to set.
            value (float): the value to set the ivar to.
        """
        self.device.other_ivars[ivar] = value
        return b"\r"

    @RegexCommand(rb"\?\?\?\r?\n?")
    async def get_status(self):
        return b"000000000000\r"


@dataclass
class PMAC(ComponentConfig):
    """PMAC accessible over TCP."""

    host: str = "localhost"
    port: int = 1025

    def __call__(self) -> Component:  # noqa: D102
        return DeviceSimulation(
            name=self.name,
            device=PMACDevice(),
            adapters=[PMACAdapter(host=self.host, port=self.port)],
        )
