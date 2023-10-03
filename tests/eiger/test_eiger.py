import itertools
from unittest.mock import ANY

import pytest
from mock import MagicMock, Mock
from tickit.core.typedefs import SimTime

from tickit_devices.eiger.eiger import EigerDevice
from tickit_devices.eiger.eiger_status import State
from tickit_devices.eiger.stream.eiger_stream import EigerStream


@pytest.fixture
def mock_stream() -> EigerStream:
    return MagicMock(EigerStream)


@pytest.fixture
def eiger(mock_stream: EigerStream) -> EigerDevice:
    return EigerDevice(stream=mock_stream)


def test_starting_state_is_na(eiger: EigerDevice):
    assert_in_state(eiger, State.NA)


@pytest.mark.asyncio
async def test_initialize(eiger: EigerDevice):
    await eiger.initialize()
    assert_in_state(eiger, State.IDLE)


@pytest.mark.asyncio
async def test_arm(eiger: EigerDevice):
    await eiger.initialize()
    await eiger.arm()
    assert_in_state(eiger, State.READY)


@pytest.mark.asyncio
async def test_disarm(eiger: EigerDevice):
    await eiger.initialize()
    await eiger.arm()
    await eiger.disarm()
    assert_in_state(eiger, State.IDLE)


@pytest.mark.asyncio
async def test_trigger_in_ints_mode_sets_acquire(eiger: EigerDevice):
    await eiger.initialize()
    eiger.settings.trigger_mode = "ints"
    await eiger.arm()
    assert_in_state(eiger, State.READY)
    await eiger.trigger()
    assert_in_state(eiger, State.ACQUIRE)


@pytest.mark.asyncio
async def test_trigger_in_ints_mode_while_not_armed_is_ignored(
    eiger: EigerDevice,
):
    await eiger.initialize()
    eiger.settings.trigger_mode = "ints"
    await eiger.trigger()
    assert_in_state(eiger, State.IDLE)


@pytest.mark.asyncio
async def test_trigger_in_exts_mode_is_ignored(eiger: EigerDevice):
    await eiger.initialize()
    eiger.settings.trigger_mode = "exts"
    await eiger.arm()
    assert_in_state(eiger, State.READY)
    await eiger.trigger()
    eiger.update(SimTime(0.0), {})
    assert_in_state(eiger, State.READY)


@pytest.mark.asyncio
async def test_update_in_exts_mode_is_ignored(eiger: EigerDevice):
    await eiger.initialize()
    eiger.settings.trigger_mode = "exts"
    await eiger.arm()
    assert_in_state(eiger, State.READY)
    eiger.update(SimTime(0.0), {})
    assert_in_state(eiger, State.READY)


@pytest.mark.asyncio
async def test_trigger_in_exts_mode_while_not_armed_is_ignored(
    eiger: EigerDevice,
):
    await eiger.initialize()
    eiger.settings.trigger_mode = "exts"
    await eiger.trigger()
    assert_in_state(eiger, State.IDLE)


@pytest.mark.asyncio
async def test_cancel(eiger: EigerDevice):
    await eiger.cancel()
    assert_in_state(eiger, State.READY)


@pytest.mark.asyncio
async def test_abort(eiger: EigerDevice):
    await eiger.abort()
    assert_in_state(eiger, State.IDLE)


@pytest.mark.asyncio
async def test_armed_eiger_starts_series(eiger: EigerDevice, mock_stream: Mock):
    await eiger.initialize()
    eiger.settings.trigger_mode = "ints"
    await eiger.arm()
    mock_stream.begin_series.assert_called_once_with(eiger.settings, 1, "basic")


@pytest.mark.asyncio
async def test_disarmed_eiger_starts_and_ends_series(
    eiger: EigerDevice, mock_stream: Mock
):
    await eiger.initialize()
    eiger.settings.trigger_mode = "ints"
    await eiger.arm()
    await eiger.disarm()
    mock_stream.begin_series.assert_called_once_with(eiger.settings, 1, "basic")
    mock_stream.end_series.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_cancelled_eiger_starts_and_ends_series(
    eiger: EigerDevice, mock_stream: Mock
):
    await eiger.initialize()
    eiger.settings.trigger_mode = "ints"
    await eiger.arm()
    await eiger.cancel()
    mock_stream.begin_series.assert_called_once_with(eiger.settings, 1, "basic")
    mock_stream.end_series.assert_called_once_with(1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "num_frames,num_series", list(itertools.product([0, 1, 2, 10], [1, 2, 3]))
)
async def test_acquire_frames_in_ints_mode(
    eiger: EigerDevice,
    mock_stream: Mock,
    num_frames: int,
    num_series: int,
):
    for series in range(1, num_series + 1):
        await eiger.initialize()
        eiger.settings.trigger_mode = "ints"
        eiger.settings.nimages = num_frames
        await eiger.arm()
        await eiger.trigger()

        # Extra update cleans up state
        for i in range(num_frames):
            update = eiger.update(SimTime(i), {})
            assert update.call_at == SimTime(i + int(0.12 * 1e9))

        update = eiger.update(SimTime(0.0), {})
        assert update.call_at is None

        mock_stream.begin_series.assert_called_with(eiger.settings, series, "basic")
        assert mock_stream.begin_series.call_count == series
        if num_frames > 0:
            mock_stream.insert_image.assert_called_with(ANY, series)
        assert mock_stream.insert_image.call_count == series * num_frames
        mock_stream.end_series.assert_called_with(series)
        assert mock_stream.end_series.call_count == series

        assert_in_state(eiger, State.IDLE)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "num_frames,num_series", list(itertools.product([0, 1, 2, 10], [1, 2, 3]))
)
async def test_acquire_frames_in_exts_mode(
    eiger: EigerDevice,
    mock_stream: Mock,
    num_frames: int,
    num_series: int,
):
    for series in range(1, num_series + 1):
        await eiger.initialize()
        eiger.settings.trigger_mode = "exts"
        eiger.settings.nimages = num_frames
        await eiger.arm()

        # Trigger detector
        update = eiger.update(SimTime(0.0), {"trigger": True})
        assert update.call_at == 0.0

        # Extra update cleans up state
        for i in range(num_frames):
            update = eiger.update(SimTime(i), {})
            assert update.call_at == SimTime(i + int(0.12 * 1e9))

        update = eiger.update(SimTime(0.0), {})
        assert update.call_at is None

        mock_stream.begin_series.assert_called_with(eiger.settings, series, "basic")
        assert mock_stream.begin_series.call_count == series
        if num_frames > 0:
            mock_stream.insert_image.assert_called_with(ANY, series)
        assert mock_stream.insert_image.call_count == series * num_frames
        mock_stream.end_series.assert_called_with(series)
        assert mock_stream.end_series.call_count == series

        assert_in_state(eiger, State.IDLE)


@pytest.mark.asyncio
@pytest.mark.parametrize("num_series", [1, 2, 3])
async def test_abort_mid_acquisition(
    eiger: EigerDevice,
    mock_stream: Mock,
    num_series: int,
):
    for series in range(1, num_series + 1):
        await eiger.initialize()
        eiger.settings.trigger_mode = "ints"
        eiger.settings.nimages = 3
        await eiger.arm()
        await eiger.trigger()

        eiger.update(SimTime(0.0), {})
        eiger.update(SimTime(0.0), {})

        await eiger.abort()

        eiger.update(SimTime(0.0), {})

        mock_stream.end_series.assert_called_with(series)
        assert_in_state(eiger, State.IDLE)


def assert_in_state(eiger: EigerDevice, state: State) -> None:
    assert state is eiger.get_state()
