import pathlib
from typing import Optional, TypedDict

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


class SynchrotronCurrentDevice(Device):
    """Device to simulate the ring current signal value from the synchrotron.

    This SynchrotronCurrentDevice simulates only a single signal that can be read,
    the beam current.The real world pv for this current is SR-DI-DCCT-01:SIGNAL.

    The signal is read via and epics adapter, and set using a tcp adapter.
    """

    #: An empty typed mapping of device inputs
    class Inputs(TypedDict): ...

    #: A typed mapping containing the current output value
    class Outputs(TypedDict):
        current: float

    def __init__(
        self,
        initial_current: Optional[float],
        callback_period: int = int(1e9),
        countdown: float = 600.0,
        fill_time: float = 15.0,
        target_current: float = 300.0,
        minimum_current: float = 270.0,
    ) -> None:
        """Initialise the SynchrotonCurrent device.

        Args:
            initial_current (Optional[float]): The inital beam current. Defaults to
                300mA.
            callback_period: (int): The number of nanoseconds it will wait
                between calls
            countdown (float): Length of time in seconds to deplete
                charge from target_current to minimum_current.
            fill_time (float): Length of time in seconds to increase charge
                charge from target_current to minimum_current.
            target_current (float): The current the synchrotron should be topped up to.
            minimum_current (float): The current the synchrotron can fall to before
                being topped up.

        """
        self.target_current = target_current
        self.minimum_current = minimum_current
        self.beam_current = initial_current if initial_current else self.target_current
        self.callback_period = callback_period

        self.topup_fill = False

        # it should take 600 seconds to go from target_current 270, 15 seconds to fill
        self.loss_increment = (self.minimum_current - self.target_current) / countdown
        self.fill_increment = (self.target_current - self.minimum_current) / fill_time

        self.last_update_time = None

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        """Update method that just outputs beam current.

        The device is only altered by adapters so take no inputs.
        The current is lost at a rate of ~0.02mA per second, during the topup
        phase it gains ~2mA per second

        Args:
            time (SimTime): The current simulation time (in nanoseconds).
            inputs (State): A mapping of inputs to the device and their values.

        Returns:
            DeviceUpdate[Outputs]:
                The produced update event which contains the value of the beam current.
        """
        # check to see if topup fill should be activated/deactivated
        if self.topup_fill:
            self.topup_fill = self.beam_current < self.target_current
        else:
            self.topup_fill = self.beam_current <= self.minimum_current

        period = self.callback_period * 1e-9
        if self.last_update_time:
            period = time - self.last_update_time

        self.beam_current += (
            self.topup_fill * self.fill_increment  # if we're refilling
            + (not self.topup_fill) * self.loss_increment  # if we're not refilling
        ) * float(period)

        self.last_time = time
        call_at = SimTime(time + self.callback_period)
        return DeviceUpdate(
            SynchrotronCurrentDevice.Outputs(current=self.beam_current), call_at
        )

    def get_current(self) -> float:
        """Beam current getter for the epics adapter."""
        return self.beam_current


class SynchrotronCurrentTCPAdapter(CommandAdapter):
    """A TCP adapter to set a SynchrotronCurrentDevice PV values."""

    device: SynchrotronCurrentDevice
    _byte_format: ByteFormat = ByteFormat(b"%b\r\n")

    def __init__(self, device: SynchrotronCurrentDevice) -> None:
        super().__init__()
        self.device = device

    @RegexCommand(r"C=(\d+\.?\d*)", interrupt=True, format="utf-8")
    async def set_beam_current(self, value: float) -> None:
        """Regex string command that sets the value of beam_current.

        Args:
            value (int): The new value of beam_current.
        """
        self.device.beam_current = value

    @RegexCommand(r"C\?", format="utf-8")
    async def get_beam_current(self) -> bytes:
        """Regex string command that returns the utf-8 encoded value of beam_current.

        Returns:
            bytes: The utf-8 encoded value of beam_current.
        """
        return str(self.device.beam_current).encode("utf-8")


class SynchrotronCurrentEpicsAdapter(EpicsAdapter):
    """Epics adapter for reading device current as a PV through channel access."""

    device: SynchrotronCurrentDevice

    def __init__(self, device: SynchrotronCurrentDevice) -> None:
        super().__init__()
        self.device = device

    def on_db_load(self) -> None:
        """Link loaded in record with getter for device."""
        self.link_input_on_interrupt(builder.aIn("SIGNAL"), self.device.get_current)


@pydantic.v1.dataclasses.dataclass
class SynchrotronCurrent(ComponentConfig):
    """Synchrotron current component."""

    initial_current: Optional[float]
    callback_period: int = int(1e9)
    host: str = "localhost"
    port: int = 25565
    db_file: str = str(pathlib.Path(__file__).parent.absolute() / "db_files/DCCT.db")
    ioc_name: str = "SR-DI-DCCT-01"

    def __call__(self) -> Component:  # noqa: D102
        device = SynchrotronCurrentDevice(
            self.initial_current,
            callback_period=self.callback_period,
        )
        adapters = [
            AdapterContainer(
                SynchrotronCurrentTCPAdapter(device),
                TcpIo(
                    self.host,
                    self.port,
                ),
            ),
            AdapterContainer(
                SynchrotronCurrentEpicsAdapter(device),
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
