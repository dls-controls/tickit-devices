import logging
import math
from enum import Enum
from typing import Any, TypedDict

import pydantic.v1.dataclasses
from pydantic.v1 import Field
from softioc import builder
from tickit.adapters.epics import EpicsAdapter
from tickit.adapters.io import EpicsIo
from tickit.core.adapter import AdapterContainer
from tickit.core.components.component import Component, ComponentConfig
from tickit.core.components.device_component import DeviceComponent
from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime


@pydantic.v1.dataclasses.dataclass
class WaveSettings:
    """
    Settings to determine the shape of the sine wave produced by a signal generator
    """

    amplitude: float = 1.0
    amplitude_offset: float = 1.0
    frequency: float = 1.0
    enabled: bool = True


class SignalGeneratorDevice(Device):
    """
    A device that can generate fake sine and boolean trigger signals, useful
    for testing triggerable devices
    """

    #: An empty typed mapping of device inputs
    class Inputs(TypedDict):
        ...

    #: A typed mapping containing the 'value' output value
    class Outputs(TypedDict):
        value: float
        gate: bool

    _wave: WaveSettings
    _gate_threshold: float

    _value: float
    _gate: bool

    def __init__(self, wave: WaveSettings, gate_threshold: float = 0.5) -> None:
        self._wave = wave
        self._gate_threshold = gate_threshold
        self._value = 0.0
        self._gate = False

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        self._value = self._compute_wave(time)
        self._gate = self._value > self._gate_threshold
        return DeviceUpdate(
            SignalGeneratorDevice.Outputs(
                value=self._value,
                gate=self._gate,
            ),
            None,
        )

    def get_amplitude(self) -> float:
        return self._wave.amplitude

    def set_amplitude(self, amplitude: float) -> None:
        self._wave.amplitude = amplitude

    def get_amplitude_offset(self) -> float:
        return self._wave.amplitude_offset

    def set_amplitude_offset(self, amplitude_offset: float) -> None:
        self._wave.amplitude_offset = amplitude_offset

    def get_frequency(self) -> float:
        return self._wave.amplitude

    def set_frequency(self, frequency: float) -> None:
        self._wave.frequency = frequency

    def get_gate_threshold(self) -> float:
        return self._gate_threshold

    def set_gate_threshold(self, gate_threshold: float) -> None:
        self._gate_threshold = gate_threshold

    def is_enabled(self) -> bool:
        return self._wave.enabled

    def set_enabled(self, enabled: bool) -> None:
        self._wave.enabled = enabled

    def get_value(self) -> float:
        return self._value

    def is_gate_open(self) -> bool:
        return self._gate

    def _compute_wave(self, time: SimTime) -> float:
        if self._wave.enabled:
            return self._sine(time)
        else:
            return 0.0

    def _sine(self, time: SimTime) -> float:
        return self._wave.amplitude_offset + (
            self._wave.amplitude * self._sinusoid(time)
        )

    def _sinusoid(self, time: SimTime) -> float:
        time_seconds = time * 1e-9
        return math.sin(2 * math.pi * self._wave.frequency * time_seconds)


class SignalGeneratorAdapter(EpicsAdapter):
    """IOC for controlling signal generator"""

    device: SignalGeneratorDevice

    def __init__(self, device: SignalGeneratorDevice) -> None:
        super().__init__()
        self.device = device

    def on_db_load(self) -> None:
        self.float_rbv(
            "Amplitude",
            self.device.get_amplitude,
            self.device.set_amplitude,
        )
        self.float_rbv(
            "Offset",
            self.device.get_amplitude_offset,
            self.device.set_amplitude_offset,
        )
        self.float_rbv(
            "Frequency",
            self.device.get_frequency,
            self.device.set_frequency,
        )
        self.float_rbv(
            "GateThreshold",
            self.device.get_gate_threshold,
            self.device.set_gate_threshold,
        )
        self.bool_rbv(
            "Enabled",
            self.device.is_enabled,
            self.device.set_enabled,
        )

        self.float_ro("Signal_RBV", self.device.get_value)
        self.bool_ro("Gate_RBV", self.device.is_gate_open)

        self.polling_interrupt(0.1)


@pydantic.v1.dataclasses.dataclass
class SignalGenerator(ComponentConfig):
    """Config for adapterless signal generator"""

    wave: WaveSettings = Field(default_factory=WaveSettings)

    def __call__(self) -> Component:  # noqa: D102
        return DeviceComponent(
            name=self.name, device=SignalGeneratorDevice(wave=self.wave)
        )


@pydantic.v1.dataclasses.dataclass
class EpicsSignalGenerator(ComponentConfig):
    """Config for signal generator with an IOC"""

    wave: WaveSettings = Field(default_factory=WaveSettings)
    ioc_name: str = "SIGNALGEN"

    def __call__(self) -> Component:  # noqa: D102
        device = SignalGeneratorDevice(wave=self.wave)
        adapters = [
            AdapterContainer(
                SignalGeneratorAdapter(device),
                EpicsIo(self.ioc_name),
            )
        ]
        return DeviceComponent(
            name=self.name,
            device=device,
            adapters=adapters,
        )