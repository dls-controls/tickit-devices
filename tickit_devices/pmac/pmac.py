from dataclasses import dataclass
from typing import Dict, Optional

from tickit.adapters.composed import ComposedAdapter
from tickit.adapters.interpreters.command import MultiCommandInterpreter
from tickit.adapters.interpreters.command.regex_command import RegexCommand
from tickit.adapters.interpreters.wrappers import (
    BeheadingInterpreter,
    JoiningInterpreter,
)
from tickit.adapters.servers.tcp import TcpServer
from tickit.core.components.component import Component, ComponentConfig
from tickit.core.components.device_simulation import DeviceSimulation
from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.utils.byte_format import ByteFormat
from tickit.utils.compat.typing_compat import TypedDict

# Some constants copied from the old PMAC sim.
M_TRAJ_VERSION = 4049
M_TRAJ_BUFSIZE = 4037
M_TRAJ_A_ADR = 4041
M_TRAJ_B_ADR = 4042


class PMACAxis:
    def __init__(self):
        self.ivars = dict()
        self.ivars[13] = 10000
        self.ivars[14] = -10000
        self.ivars[22] = 32.0  # velocity in counts per millisecond
        self.ivars[31] = 50
        self.ivars[32] = 50
        self.ivars[33] = 50
        self.target_position = 0
        self.current_position = 0

    @property
    def velocity(self):
        return self.ivars[22]

    @property
    def in_position(self):
        return self.target_position == self.current_position

    @property
    def status(self):
        status_digit = "1" if self.in_position else "0"
        return "88000001840" + status_digit

    def move(self, period_ms: float):
        """A helper method used to compute the new position of the axis motor.

        A helper method used to compute the new position of the axis motor given a
        period over which the change occurs. Movement is performed at the rate defined
        by ivar22 and comes to a "hard" stop when the desired position is reached.

        Args:
            period_ms (float): The period over which the change occurs in milliseconds.
        """
        if self.in_position:
            return
        current_pos = self.current_position
        target_pos = self.target_position
        print(current_pos, target_pos)
        velocity = self.velocity
        if current_pos < target_pos:
            new_position = min(current_pos + velocity * period_ms, target_pos)
        elif current_pos > target_pos:
            new_position = max(current_pos - velocity * period_ms, target_pos)
        self.current_position = new_position


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
        self.axes = {i: PMACAxis() for i in range(1, 17)}
        self.system_ivars: Dict = dict()
        self.system_ivars[20] = "$78400"
        self.system_ivars[21] = "$0"
        self.system_ivars[22] = "$0"
        self.system_ivars[23] = "$0"
        self.other_ivars: Dict = dict()
        self.current_axis_index = 1
        self.current_cs = 1
        self.last_update_time: Optional[SimTime] = None

    @property
    def current_axis(self):
        return self.axes[self.current_axis_index]

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        if self.last_update_time is not None:
            # Calculate time interval in milliseconds
            time_interval = SimTime(time - self.last_update_time) / 1e6
            for axis in self.axes.values():
                axis.move(time_interval)
        in_position = all(axis.in_position for axis in self.axes.values())
        self.last_update_time = None if in_position else time
        call_at = None if in_position else SimTime(time + int(1e8))
        return DeviceUpdate(self.Outputs(flux=2.0), call_at)


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
            TcpServer(host, port, ByteFormat(b"%b\x06")),
            BeheadingInterpreter(
                JoiningInterpreter(MultiCommandInterpreter(), b""),
                header_size=8,
            ),
        )

    @RegexCommand(rb"\r?\n?$")
    async def end_of_message(self):
        return b"\r"

    @RegexCommand(rb"(?i:CID)")
    async def get_cid(self):
        """Regex bytestring command returning the value for the PMACA's card ID number.

        Note:
        602404: "Turbo PMAC2 Clipper",
        602413: "Turbo PMAC2-VME",
        603382: "Geo Brick (3U Turbo PMAC2)",
        """
        return b"603382\r"

    @RegexCommand(rb"(?i:CPU)")
    async def get_cpu(self):
        """Command reporting the PMAC's CPU type."""
        return b"DSP56321\r"

    @RegexCommand(rb"(?i:VER)")
    async def get_ver(self):
        """Command reporting the PMAC's firmware version."""
        return b"1.947  \r"

    @RegexCommand(rb"[mM]([0-9]{1,5})")
    async def get_m_var(self, mvar: int):
        """Regex bytestring command that returns the value of a specific mvar.

        Args:
            mvar (int): the mvar to be returned.
        """
        value = self.device.mvars.get(mvar, None)
        if value is None:
            self.device.mvars[mvar] = 0
        return f"{self.device.mvars[mvar]}\r".encode()

    @RegexCommand(rb"[mM]([0-9]{1,5})=([0-9]*.?[0-9]*)")
    async def set_m_var(self, mvar: int, value: float):
        """Regex bytestring command that sets the value of a specific mvar.

        Args:
            mvar (int): the mvar to be set.
            value (float): the value for the mvar to be set to.
        """
        self.device.mvars[mvar] = value
        return b""

    @RegexCommand(rb"[pP]([0-9]{1,5})")
    async def get_p_var(self, pvar: int):
        """Regex bytestring command that returns the value of a specific pvar.

        Args:
            pvar (int): the p var to be returned.
        """
        value = self.device.pvars.get(pvar, None)
        if value is None:
            self.device.pvars[pvar] = 0
        return f"{self.device.pvars[pvar]}\r".encode()

    @RegexCommand(rb"[pP]([0-9]{1,5})=([0-9]*.?[0-9]*)")
    async def set_p_var(self, pvar: int, value: float):
        """Regex bytestring command that sets the value of a specific pvar.

        Args:
            pvar (int): the pvar to be set.
            value (float): the value for the pvar to be set to.
        """
        self.device.pvars[pvar] = value
        return b""

    @RegexCommand(rb"[iI]([0-9]{1,2})")
    async def read_system_ivar(self, ivar: int):
        """Regex bytestring command that returns the value of a specific system ivar.

        Args:
            ivar (int): the ivar to read.
        """
        value = self.device.system_ivars.get(ivar, None)
        if value is None:
            self.device.system_ivars[ivar] = 0
        return f"{self.device.system_ivars[ivar]}\r".encode()

    @RegexCommand(rb"[iI]([0-9]{1,2})=\$?(\d+(?:.\d+)?)")
    async def write_system_ivar(self, ivar: int, value: float):
        """Regex bytestring command that sets the value of a specific system ivar.

        Args:
            ivar (int): the ivar to set.
            value (float): the value to set the ivar to.
        """
        self.device.system_ivars[ivar] = value
        return b""

    @RegexCommand(rb"[iI](1*[0-9])([0-9]{2})")
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

    @RegexCommand(rb"[iI](1*[0-9])([0-9]{2})=-?(\d+(?:.\d+)?)")
    async def write_axis_ivar(self, axis: int, ivar: int, value: float):
        """Regex bytestring command that sets the value of a specific axis ivar.

        Args:
            axis (int): the axis to set ivars on.
            ivar (int): the ivar to set.
            value (float): the value to set the ivar to.
        """
        self.device.axes[axis].ivars[ivar] = value
        return b""

    @RegexCommand(rb"[iI]([0-9]{4})")
    async def read_other_ivar(self, ivar: int):
        """Regex bytestring command that returns the value of a specific ivar.

        Args:
            ivar (int): the ivar to read.
        """
        value = self.device.other_ivars.get(ivar, None)
        if value is None:
            self.device.other_ivars[ivar] = 0
        return f"{self.device.other_ivars[ivar]}\r".encode()

    @RegexCommand(rb"[iI]([0-9]{4})=-?(\d+(?:\.\d+)?)")
    async def write_other_var(self, ivar: int, value: float):
        """Regex bytestring command that sets the value of a specific ivar.

        Args:
            ivar (int): the ivar to set.
            value (float): the value to set the ivar to.
        """
        self.device.other_ivars[ivar] = value
        return b""

    @RegexCommand(rb"#")
    async def get_current_axis(self):
        """Command reporting the currently addressed axis."""
        return f"{self.device.current_axis_index}\r".encode()

    @RegexCommand(rb"#(1*[0-9])")
    async def set_current_axis(self, axis: int):
        """Command setting the currently addressed axis.

        Args:
            axis (int): the new current axis.
        """
        self.device.current_axis_index = axis
        return b""

    @RegexCommand(rb"\?")
    async def get_axis_status(self):
        """Command getting the status of the currently addressed axis.

        Currently returns a dummy value of the right format.
        """
        status = self.device.current_axis.status
        return f"{status}\r".encode()

    @RegexCommand(rb"&")
    async def get_current_cs(self):
        """Command reporting the currently addressed coordinate system."""
        return f"{self.device.current_cs}".encode()

    @RegexCommand(rb"&([1-8])")
    async def set_current_cs(self, cs: int):
        """Command setting the currently addressed coordinate system.

        Args:
            cs (int): the new active coordinate system.
        """
        self.device.current_cs = cs
        return b""

    @RegexCommand(rb"\?\?")
    async def get_cs_status(self):
        """Command reporting the status of the currently addressed coordinate system.

        Currently returns a dummy value of the right format.
        """
        return b"A80020000000000000\r"

    @RegexCommand(rb"\?\?\?")
    async def get_status(self):
        """Command reporting the status of the PMAC.

        Currently returns a dummy value of the right format.
        """
        return b"000000000000\r"

    @RegexCommand(rb"%")
    async def get_cs_feedrate_override(self):
        """Command reporting the feedrate override of the current coordinate system.

        Currently returns a dummy value of the right format.
        """
        return b"100\r"

    @RegexCommand(rb"P")
    async def get_axis_position(self):
        """Command reporting the motor position of the currently addressed axis.

        Currently returns a dummy value of the right format.
        """
        position = self.device.current_axis.current_position
        return f"{position}\r".encode()

    @RegexCommand(rb"V")
    async def get_axis_velocity(self):
        """Command reporting the motor velocity of the currently addressed axis.

        Currently returns a dummy value of the right format.
        """
        velocity = self.device.current_axis.velocity
        return f"{velocity}\r".encode()

    @RegexCommand(rb"F")
    async def get_axis_follow_error(self):
        """Command reporting the motor following error of the current axis.

        Currently returns a dummy value of the right format.
        """
        follow_error = (
            self.device.current_axis.target_position
            - self.device.current_axis.current_position
        )
        return f"{follow_error}\r".encode()

    @RegexCommand(rb"HM", interrupt=True)
    async def home(self):
        """Command causing the addressed motor to perform a homing search routine."""
        self.device.current_axis.target_position = 0
        return b""

    @RegexCommand(rb"J\^(-?\d+(?:\.\d+)?)", interrupt=True)
    async def jog_relative(self, move: float):
        """Command causing the current motor to jog relative to its actual position.

        Args:
            move (float): The distance to move relative to the current position.
        """
        current_pos = self.device.current_axis.target_position
        target_pos = current_pos + move
        self.device.current_axis.target_position = target_pos
        return b""

    @RegexCommand(rb"J=(-?\d+(?:\.\d+)?)", interrupt=True)
    async def jog_specific(self, target: float):
        """Command causing the current motor to jog to a specific position.

        Args:
            target (float): The distance to move relative to the current position.
        """
        self.device.current_axis.target_position = target
        return b""

    @RegexCommand(rb"J/", interrupt=True)
    async def jog_stop(self):
        """Command causing the current motor to stop jogging."""
        self.device.current_axis.target_position = (
            self.device.current_axis.current_position
        )
        return b""

    @RegexCommand(rb"J\+", interrupt=True)
    async def jog_pos(self):
        """Command to jog indefinitely in the positive direction."""
        self.device.current_axis.target_position = 1e9
        return b""

    @RegexCommand(rb"J-", interrupt=True)
    async def jog_neg(self):
        """Command to jog indefinitely in the negative direction."""
        self.device.current_axis.target_position = -1e9
        return b""


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
