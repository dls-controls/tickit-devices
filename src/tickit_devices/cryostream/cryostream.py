import asyncio
import struct
from typing import AsyncIterable, TypedDict

from tickit.adapters.specifications import RegexCommand
from tickit.adapters.tcp import CommandAdapter
from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime

from tickit_devices.cryostream.base import CryostreamBase
from tickit_devices.cryostream.states import PhaseIds

_EXTENDED_STATUS = ">BBHHHBBHHHHHBBBBBBHHBBBBBBBBHH"


class CryostreamDevice(Device, CryostreamBase):
    """A Cryostream device, used for cooling of samples using cold gas."""

    #: An empty typed mapping of device inputs
    class Inputs(TypedDict): ...

    #: A typed mapping containing the 'temperature' output value
    class Outputs(TypedDict):
        temperature: float

    def __init__(self) -> None:
        """A Cryostream constructor sets up initial internal values."""
        super().__init__()
        self.phase_id: int = PhaseIds.HOLD.value
        self.callback_period: SimTime = SimTime(int(1e9))

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        """The update method which changes the output temperature according to set
        modes.

        Returns:
            DeviceUpdate[Outputs]:
                The produced update event which contains the value of the output
                temperature, and requests callback if temperature should continue to
                change.
        """
        if self.phase_id in (PhaseIds.RAMP.value, PhaseIds.COOL.value):
            self.gas_temp = self.update_temperature(time)
            return DeviceUpdate(
                self.Outputs(temperature=self.gas_temp),
                SimTime(time + self.callback_period),
            )
        if self.phase_id == PhaseIds.PLAT.value:
            self.phase_id = PhaseIds.HOLD.value
            return DeviceUpdate(
                self.Outputs(temperature=self.gas_temp),
                SimTime(time + int(self.plat_duration * 1e10)),
            )
        return DeviceUpdate(self.Outputs(temperature=self.gas_temp), None)


class CryostreamAdapter(CommandAdapter):
    """A Cryostream TCP adapter which sends regular status packets and can set modes."""

    device: CryostreamDevice

    def __init__(self, device: CryostreamDevice) -> None:
        super().__init__()
        self.device = device

    async def on_connect(self) -> AsyncIterable[bytes]:
        """A method which continiously yields status packets.

        Returns:
            AsyncIterable[bytes]: An asyncronous iterable of packed Cryostream status
                packets.
        """
        while True:
            await asyncio.sleep(2.0)
            await self.device.set_status_format(1)
            status = await self.device.get_status(1)
            yield status.pack()

    @RegexCommand(b"\\x02\\x0a", interrupt=True)
    async def restart(self) -> None:
        """A regex bytes command which restarts the Cryostream."""
        await self.device.restart()

    @RegexCommand(b"\\x02\\x0d", interrupt=True)
    async def hold(self) -> None:
        """A regex bytes command which holds the current temperature."""
        await self.device.hold()

    @RegexCommand(b"\\x02\\x10", interrupt=True)
    async def purge(self) -> None:
        """A regex bytes command which purges (immediately raise to 300K)."""
        await self.device.purge()

    @RegexCommand(b"\\x02\\x11", interrupt=True)
    async def pause(self) -> None:
        """A regex bytes command which pauses."""
        await self.device.pause()

    @RegexCommand(b"\\x02\\x12", interrupt=True)
    async def resume(self) -> None:
        """A regex bytes command which resumes the last command."""
        await self.device.resume()

    @RegexCommand(b"\\x02\\x13", interrupt=True)
    async def stop(self) -> None:
        """A regex bytes command which stops gas flow."""
        await self.device.stop()

    @RegexCommand(b"\\x03\\x14([\\x00\\x01])", interrupt=True)
    async def turbo(self, turbo_on: bytes) -> None:
        """A regex bytes command which enables / disables turbo mode.

        Args:
            turbo_on (bytes): The desired turbo mode, where 0 denotes off and 1 denotes
                on.
        """
        turbo_on = struct.unpack(">B", turbo_on)[0]
        await self.device.turbo(turbo_on)  # type: ignore

    # Todo set status format not interrupt
    @RegexCommand(b"\\x03\\x28([\\x00\\x01])", interrupt=False)
    async def set_status_format(self, status_format: bytes) -> None:
        """A regex bytes command which sets the status packet format.

        Args:
            status_format (bytes): The status packet format, where 0 denotes a standard
                status packet and 1 denotes an extended status packet.
        """
        status_format = struct.unpack(">B", status_format)[0]
        await self.device.set_status_format(status_format)  # type: ignore

    @RegexCommand(b"\\x04\\x0c(.{2})", interrupt=True)
    async def plat(self, duration: bytes) -> None:
        """A regex bytes command which maintains temperature for a set amount of time.

        Args:
            duration (bytes): The duration for which the temperature should be held.
        """
        duration = struct.unpack(">H", duration)[0]
        await self.device.plat(duration)  # type: ignore

    @RegexCommand(b"\\x04\\x0f(.{2})", interrupt=True)
    async def end(self, ramp_rate: bytes) -> None:
        """A regex bytes command which brings the gas temperature to 300 K at ramp rate.

        Args:
            ramp_rate (bytes): The rate at which the temperature should change.
        """
        ramp_rate = struct.unpack(">H", ramp_rate)[0]
        await self.device.end(ramp_rate)  # type: ignore

    @RegexCommand(b"\\x04\\x0e(.{2})", interrupt=True)
    async def cool(self, target_temp: bytes) -> None:
        """A regex bytes command which makes decreases temperature to a set value.

        Args:
            target_temp (bytes): The target temperature.
        """
        target_temp = struct.unpack(">H", target_temp)[0]
        await self.device.cool(target_temp)  # type: ignore

    @RegexCommand(b"\\x06\\x0b(.{2,4})", interrupt=True)
    async def ramp(self, values: bytes) -> None:
        """Change gas temperature to a set value at a controlled rate.

        Args:
            values (bytes): The rate at which the temperature should change and the
                target temperature.
        """
        ramp_rate, target_temp = struct.unpack(">HH", values)
        await self.device.ramp(ramp_rate, target_temp)  # type: ignore
