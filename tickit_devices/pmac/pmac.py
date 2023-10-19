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

M_TRAJ_VERSION = 4049
M_TRAJ_BUFSIZE = 4037
M_TRAJ_A_ADR = 4041
M_TRAJ_B_ADR = 4042


class PMACDevice(Device):

    Inputs: TypedDict = TypedDict("Inputs", {"flux": float})
    Outputs: TypedDict = TypedDict("Outputs", {"flux": float})

    def __init__(self) -> None:
        self.mvars = dict()
        self.mvars[M_TRAJ_VERSION] = 3.0
        self.mvars[M_TRAJ_BUFSIZE] = 1000
        self.mvars[M_TRAJ_A_ADR] = 0x40000
        self.mvars[M_TRAJ_B_ADR] = 0x30000
        self.mvars[70] = 11990
        self.mvars[71] = 554
        self.mvars[72] = 2621
        self.mvars[73] = 76
        self.pvars: Dict = dict()

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

    @RegexCommand(rb"[mM]([0-9]{1,5})\r?\n?")  # 1-4 or 1-5?
    async def get_m_var(self, mvar: int):
        """Regex bytestring command that returns the value of a specific mvar.

        Args:
            mvar (int): the mvar to be returned.
        """
        value = self.device.mvars.get(mvar, None)
        if value is None:
            self.device.mvars[mvar] = 0
        return f"{self.device.mvars[mvar]}\r".encode()

    @RegexCommand(rb"[mM]([0-9]{1,5})=([0-9]*.?[0-9]*)\r?\n?")
    async def set_m_var(self, mvar: int, value: float):
        """Regex bytestring command that sets the value of a specific mvar.

        Args:
            mvar (int): the mvar to be set.
            value (float): the value for the mvar to be set to.
        """
        self.device.mvars[mvar] = value
        return b"\r"

    @RegexCommand(rb"[pP]([0-9]{1,5})\r?\n?")  # 1-4 or 1-5?
    async def get_p_var(self, pvar: int):
        """Regex bytestring command that returns the value of a specific pvar.

        Args:
            pvar (int): the p var to be returned.
        """
        value = self.device.pvars.get(pvar, None)
        if value is None:
            self.device.pvars[pvar] = 0
        return f"{self.device.pvars[pvar]}\r".encode()

    @RegexCommand(rb"[pP]([0-9]{1,5})=([0-9]*.?[0-9]*)\r?\n?")
    async def set_p_var(self, pvar: int, value: float):
        """Regex bytestring command that sets the value of a specific pvar.

        Args:
            pvar (int): the pvar to be set.
            value (float): the value for the pvar to be set to.
        """
        self.device.pvars[pvar] = value
        return b"\r"

    @RegexCommand(rb"[iI][0-9]{1,4}\r?\n?")
    async def i_var(self):
        return b"2\r"

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
