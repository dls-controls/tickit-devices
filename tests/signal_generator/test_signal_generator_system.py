import asyncio
from dataclasses import dataclass
from typing import Any, List

import aioca
import numpy as np
import pytest

PV_PREFIX = "SIGNALGEN"
AMPLITUDE = f"{PV_PREFIX}:Amplitude"
AMPLITUDE_RBV = f"{AMPLITUDE}_RBV"
OFFSET = f"{PV_PREFIX}:Offset"
OFFSET_RBV = f"{OFFSET}_RBV"
FREQUENCY = f"{PV_PREFIX}:Frequency"
FREQUENCY_RBV = f"{FREQUENCY}_RBV"
GATE_THRESHOLD = f"{PV_PREFIX}:GateThreshold"
GATE_THRESHOLD_RBV = f"{GATE_THRESHOLD}_RBV"
ENABLED = f"{PV_PREFIX}:Enabled"
ENABLED_RBV = f"{ENABLED}_RBV"
SIGNAL_RBV = f"{PV_PREFIX}:Signal_RBV"
GATE_RBV = f"{PV_PREFIX}:Gate_RBV"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tickit_process",
    ["examples/configs/signal-generator/signal-generator.yaml"],
    indirect=True,
)
async def test_signal_generator_system(tickit_process):
    await set_and_test(AMPLITUDE, AMPLITUDE_RBV, 1.0, 2.0)
    await set_and_test(OFFSET, OFFSET_RBV, 1.0, 2.0)
    await set_and_test(FREQUENCY, FREQUENCY, 1.0, 2.0)
    await set_and_test(GATE_THRESHOLD, GATE_THRESHOLD_RBV, 0.5, 0.25)
    await set_and_test(ENABLED, ENABLED_RBV, True, False)
    await check_signal_and_gate(0.25)


async def set_and_test(pv: str, rbv: str, expected_initial_value: Any, new_value: Any):
    initial_value = await aioca.caget(rbv)
    await aioca.caput(pv, new_value, wait=True)
    await asyncio.sleep(1.0)
    actual_demand_value, actual_new_value = await asyncio.gather(
        *[aioca.caget(pv), aioca.caget(rbv)]
    )

    assert initial_value == expected_initial_value, (
        f"Initially caget({pv}) was {initial_value}, expected {expected_initial_value}",
    )
    assert (
        actual_demand_value == new_value
    ), f"After caput({pv}, {new_value}), {pv} was actually {actual_new_value}"
    assert (
        actual_new_value == new_value
    ), f"After caput({pv}, {new_value}), {rbv} was actually {actual_new_value}"


async def check_signal_and_gate(threshold: float):
    for _ in range(30):
        signal, gate = await asyncio.gather(
            *[aioca.caget(SIGNAL_RBV), aioca.caget(GATE_RBV)]
        )
        should_gate_be_open = signal >= threshold
        assert should_gate_be_open == gate
        await asyncio.sleep(0.1)
