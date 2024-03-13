import pathlib
from typing import TypedDict

import pydantic.v1.dataclasses
from softioc import builder
from tickit.adapters.epics import EpicsAdapter
from tickit.adapters.io import EpicsIo, TcpIo
from tickit.adapters.specifications import RegexCommand
from tickit.adapters.tcp import CommandAdapter
from tickit.core.adapter import AdapterContainer
from tickit.core.components.component import Component, ComponentConfig
from tickit.core.components.device_component import DeviceComponent
from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.utils.byte_format import ByteFormat


class SynchrotronMachineStatusDevice(Device):
    """Device to simulate the machine status records from the synchrotron.

    The signal is read via an epics adapter, and set using a tcp adapter.
    """

    class Inputs(TypedDict): ...

    class Outputs(TypedDict):
        mode: int
        user_countdown: float
        beam_energy: float

    def __init__(
        self,
        initial_mode: int,
        initial_countdown: float,
        initial_energy: float,
    ) -> None:
        """Initialise the SynchrotonMachineStatus device.

        Args:
            initial_mode (int): The inital synchrotron operation status, defaults at 0,
                or "Shutdown".
            initial_countdown (float): Initial Time countdown to the beam dump
            initial_energy (float): Inital current value of ring energy
        """
        self.synchrotron_mode = initial_mode
        self.user_countdown = initial_countdown
        self.beam_energy = initial_energy

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        """Update method that outputs machine status record values.

        The device is only altered by adapters so take no inputs and is independent of
        time.

        Args:
            time (SimTime): The current simulation time (in nanoseconds).
            inputs (State): A mapping of inputs to the device and their values.

        Returns:
            DeviceUpdate[Outputs]:
                The produced update event which contains the value of the machine
                status records.
        """
        return DeviceUpdate(
            SynchrotronMachineStatusDevice.Outputs(
                mode=self.synchrotron_mode,
                user_countdown=self.user_countdown,
                beam_energy=self.beam_energy,
            ),
            None,
        )

    def get_mode(self) -> int:
        """Return value of synchrotron mode, required for epics adapter."""
        return self.synchrotron_mode

    def get_user_countdown(self) -> float:
        """Return value of user countdown, required for epics adapter."""
        return self.user_countdown

    def get_beam_energy(self) -> float:
        """Return value of beam energy, required for epics adapter."""
        return self.beam_energy


class SynchrotronMachineStatusTCPAdapter(CommandAdapter):
    """A TCP adapter to set a SynchrotronMachineStatusDevice PV values."""

    device: SynchrotronMachineStatusDevice
    _byte_format: ByteFormat = ByteFormat(b"%b\r\n")

    def __init__(self, device: SynchrotronMachineStatusDevice) -> None:
        super().__init__()
        self.device = device

    @RegexCommand(r"mode=([0-7])", interrupt=True, format="utf-8")
    async def set_synchrotron_mode(self, value: int) -> None:
        """Regex string command to set the value of synchrotron_mode.

        Args:
            value (int): The new value of synchrotron mode in digits 0-7.
                These numbers are used by the mbbi record, which returns
                the corresponding status word on a caget.
        """
        self.device.synchrotron_mode = value

    @RegexCommand(r"UCD=(\d+\.?\d*)", interrupt=True, format="utf-8")
    async def set_user_countdown(self, value: float) -> None:
        """Regex string command to set the value of user_countdown.

        Args:
            value (int): The new value of user_countdown.
        """
        self.device.user_countdown = value

    @RegexCommand(r"BE=(\d+\.?\d*)", interrupt=True, format="utf-8")
    async def set_beam_energy(self, value: float) -> None:
        """Regex string command to set the value of beam_energy.

        Args:
            value (int): The new value of beam_energy.
        """
        self.device.beam_energy = value

    @RegexCommand(r"mode\?", format="utf-8")
    async def get_synchrotron_mode(self) -> bytes:
        """Regex string command that returns synchrotron_mode.

        Returns:
            bytes: The utf-8 encoded value of synchrotron_mode.
        """
        return str(self.device.synchrotron_mode).encode("utf-8")

    @RegexCommand(r"UCD\?", format="utf-8")
    async def get_user_countdown(self) -> bytes:
        """Regex string command that returns user_countdown.

        Returns:
            bytes: The utf-8 encoded value of user_countdown.
        """
        return str(self.device.user_countdown).encode("utf-8")

    @RegexCommand(r"BE\?", format="utf-8")
    async def get_beam_energy(self) -> bytes:
        """Regex string command that returns beam_energy.

        Returns:
            bytes: The utf-8 encoded value of beam_energy.
        """
        return str(self.device.beam_energy).encode("utf-8")


class SynchrotronMachineStatusEpicsAdapter(EpicsAdapter):
    """Epics adapter for reading device values as a PV through channel access."""

    device: SynchrotronMachineStatusDevice

    def __init__(self, device: SynchrotronMachineStatusDevice) -> None:
        super().__init__()
        self.device = device

    def on_db_load(self) -> None:
        """Link epics records with getters for device.

        The MODE record is loaded via db, the other two are created here.
        """
        self.link_input_on_interrupt(builder.mbbIn("MODE"), self.device.get_mode)
        self.link_input_on_interrupt(
            builder.aIn("USERCOUNTDN"),
            self.device.get_user_countdown,
        )
        self.link_input_on_interrupt(
            builder.aIn("BEAMENERGY"), self.device.get_beam_energy
        )


@pydantic.v1.dataclasses.dataclass
class SynchrotronMachineStatus(ComponentConfig):
    """Synchrotron Machine status component."""

    initial_mode: int = 4
    initial_countdown: float = 100000
    initial_energy: float = 3.0
    host: str = "localhost"
    port: int = 25565
    db_file: str = str(pathlib.Path(__file__).parent.absolute() / "db_files/MSTAT.db")
    ioc_name: str = "CS-CS-MSTAT-01"

    def __call__(self) -> Component:  # noqa: D102
        device = SynchrotronMachineStatusDevice(
            self.initial_mode,
            self.initial_countdown,
            self.initial_energy,
        )
        adapters = [
            AdapterContainer(
                SynchrotronMachineStatusTCPAdapter(device),
                TcpIo(
                    self.host,
                    self.port,
                ),
            ),
            AdapterContainer(
                SynchrotronMachineStatusEpicsAdapter(device),
                EpicsIo(
                    self.ioc_name,
                    self.db_file,
                ),
            ),
        ]
        return DeviceComponent(
            name=self.name,
            device=device,
            adapters=adapters,
        )
