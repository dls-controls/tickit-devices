from dataclasses import dataclass
from typing import List

import pytest
from tickit.core.typedefs import SimTime

from tickit_devices.signal_generator.signal_generator import (
    SignalGeneratorDevice,
    WaveSettings,
)


@pytest.fixture
def signal_generator() -> SignalGeneratorDevice:
    config = WaveSettings()
    return SignalGeneratorDevice(config)


TIMES = [
    SimTime(0),
    SimTime(0.25e9),
    SimTime(0.5e9),
    SimTime(0.75e9),
    SimTime(1e9),
    SimTime(1.25e9),
]

EXPECTED_SINE_VALUES = [
    1.0,
    2.0,
    1.0,
    0.0,
    1.0,
    2.0,
]

EXPECTED_GATE_STATES = [
    True,
    True,
    True,
    False,
    True,
    True,
]

EXPECTED_OUTPUTS = [
    SignalGeneratorDevice.Outputs(value=1.0, gate=True),
    SignalGeneratorDevice.Outputs(value=2.0, gate=True),
    SignalGeneratorDevice.Outputs(value=1.0, gate=True),
    SignalGeneratorDevice.Outputs(value=0.0, gate=False),
    SignalGeneratorDevice.Outputs(value=1.0, gate=True),
    SignalGeneratorDevice.Outputs(value=2.0, gate=True),
]


def test_signal_generator_produces_sine_wave(
    signal_generator: SignalGeneratorDevice,
):
    sine_values = []
    for sim_time in TIMES:
        signal_generator.update(sim_time, {})
        sine_values.append(signal_generator.get_value())
    assert sine_values == pytest.approx(EXPECTED_SINE_VALUES)


def test_signal_generator_can_be_disabled(
    signal_generator: SignalGeneratorDevice,
):
    sine_values = []
    signal_generator.set_enabled(False)
    for sim_time in TIMES:
        signal_generator.update(sim_time, {})
        sine_values.append(signal_generator.get_value())
    assert sine_values == [0.0] * 6


def test_signal_generator_trips_gate(
    signal_generator: SignalGeneratorDevice,
):
    gate_states = []
    for sim_time in TIMES:
        signal_generator.update(sim_time, {})
        gate_states.append(signal_generator.is_gate_open())
    assert gate_states == EXPECTED_GATE_STATES


def test_signal_generator_produces_outputs(
    signal_generator: SignalGeneratorDevice,
):
    outputs = []
    for sim_time, expected_output in zip(TIMES, outputs):
        output = signal_generator.update(sim_time, {})
        assert output["gate"] == expected_output["gate"]
        assert output["value"] == pytest.approx(expected_output["value"])


def test_config_passes(signal_generator: SignalGeneratorDevice):
    default_wave_config = WaveSettings()
    signal_generator.get_amplitude() == default_wave_config.amplitude
    signal_generator.get_amplitude_offset() == default_wave_config.amplitude_offset
    signal_generator.get_frequency() == default_wave_config.frequency
    signal_generator.get_gate_threshold() == 0.5
