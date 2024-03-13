import asyncio
import logging
from queue import Queue
from typing import Optional

from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime
from typing_extensions import TypedDict

from tickit_devices.eiger.data.dummy_image import Image
from tickit_devices.eiger.eiger_settings import EigerSettings
from tickit_devices.eiger.filewriter.filewriter_config import FileWriterConfig
from tickit_devices.eiger.filewriter.filewriter_status import FileWriterStatus
from tickit_devices.eiger.monitor.monitor_config import MonitorConfig
from tickit_devices.eiger.monitor.monitor_status import MonitorStatus
from tickit_devices.eiger.stream.eiger_stream import EigerStream

from .eiger_status import EigerStatus, State

LOGGER = logging.getLogger("Eiger")


class EigerDevice(Device):
    """Simulation logic for the Eiger detector.

    The simulation acquires frames based on the commands called. It supports
    the following state transitions:

    NA -> IDLE
    IDLE -> READY
    READY -> IDLE
    READY -> ACQUIRING
    ACQUIRING -> READY
    ACQUIRING -> IDLE
    """

    settings: EigerSettings
    status: EigerStatus
    stream: EigerStream

    _num_frames_left: int
    _data_queue: Queue

    class Inputs(TypedDict, total=False):
        trigger: bool

    class Outputs(TypedDict): ...

    def __init__(
        self,
        settings: Optional[EigerSettings] = None,
        status: Optional[EigerStatus] = None,
        stream: Optional[EigerStream] = None,
    ) -> None:
        """Construct a new eiger.

        Args:
            settings: Eiger settings. Defaults to None.
            status: Starting status. Defaults to None.
            stream: Data stream handler. Defaults to None.
        """
        self.settings = settings or EigerSettings()
        self.status = status or EigerStatus()

        self.stream = stream or EigerStream(callback_period=SimTime(int(1e9)))

        self.filewriter_status: FileWriterStatus = FileWriterStatus()
        self.filewriter_config: FileWriterConfig = FileWriterConfig()
        self.filewriter_callback_period = SimTime(int(1e9))

        self.monitor_status: MonitorStatus = MonitorStatus()
        self.monitor_config: MonitorConfig = MonitorConfig()
        self.monitor_callback_period = SimTime(int(1e9))

        self._num_frames_left: int = 0
        self._total_frames: int = 0
        self._data_queue: Queue = Queue()
        self._series_id: int = 0

        self._finished_aquisition: Optional[asyncio.Event] = None

    @property
    def finished_aquisition(self) -> asyncio.Event:
        """Event that is set when an acqusition series is complete.

        Property ensures the event is created.
        """
        if self._finished_aquisition is None:
            self._finished_aquisition = asyncio.Event()

        return self._finished_aquisition

    async def initialize(self) -> None:
        """Initialize the detector.

        Required for all subsequent operations.
        """
        self._set_state(State.IDLE)

    async def arm(self) -> None:
        """Arm the detector.

        Required for triggering.
        """
        self._series_id += 1
        self.stream.begin_series(self.settings, self._series_id)
        self._num_frames_left = self.settings.nimages
        self._set_state(State.READY)

    async def disarm(self) -> None:
        """Disarm the detector.

        Intended for use when armed. See state diagram in class docstring.
        """
        self._set_state(State.IDLE)
        self.stream.end_series(self._series_id)

    async def trigger(self) -> None:
        """Trigger the detector.

        If the detector is in INTS mode, it will begin acquiring frames the
        next time update() is called. If it is in EXTS mode, this call will
        be ignored and acquisition will start based on the parameter to
        update().
        INTE and EXTE mode are currently not supported.
        """
        LOGGER.info("Trigger requested")
        trigger_mode = self.settings.trigger_mode

        if self._is_in_state(State.READY) and trigger_mode == "ints":
            self._begin_acqusition_mode()
        else:
            LOGGER.info(
                f"Ignoring trigger, state={self.get_state()},"
                f"trigger_mode={trigger_mode}"
            )

    async def cancel(self) -> None:
        """Cancel acquisition.

        The detector will stop acquiring frames after the next full frame is taken,
        it will then return to a READY state as though it has just been armed.
        """
        self._set_state(State.READY)
        self.stream.end_series(self._series_id)

    async def abort(self) -> None:
        """Abort acquisition.

        The detector will immediately stop acquiring frames and disarm itself.
        """
        self._set_state(State.IDLE)
        self.stream.end_series(self._series_id)

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        """Update the detector.

        Depending on the detector's current state, will begin, continue or
        clean up an acquisition series.

        Args:
            time: The current simulation time (in nanoseconds).
            inputs: A mapping of device inputs and their values.
        """
        if self._is_in_state(State.ACQUIRE):
            if self._num_frames_left > 0:
                self._acquire_frame()

                return DeviceUpdate(
                    self.Outputs(), SimTime(time + int(self.settings.frame_time * 1e9))
                )
            else:
                self.finished_aquisition.set()

                LOGGER.debug("Ending Series...")
                self._set_state(State.IDLE)
                self.stream.end_series(self._series_id)
        if inputs.get("trigger", False):
            self._begin_acqusition_mode()
            # Should have another update immediately to begin acquisition
            return DeviceUpdate(self.Outputs(), SimTime(time))

        return DeviceUpdate(self.Outputs(), None)

    def _begin_acqusition_mode(self) -> None:
        self._set_state(State.ACQUIRE)
        LOGGER.info("Now in acquiring mode")
        self.finished_aquisition.clear()

    def _acquire_frame(self) -> None:
        frame_id = self.settings.nimages - self._num_frames_left
        LOGGER.debug(f"Frame id {frame_id}")

        shape = (
            self.settings.x_pixels_in_detector,
            self.settings.y_pixels_in_detector,
        )
        image = Image.create_dummy_image(frame_id, shape)
        self.stream.insert_image(image, self._series_id)
        self._num_frames_left -= 1
        LOGGER.debug(f"Frames left: {self._num_frames_left}")

    def get_state(self) -> State:
        """Get the eiger's current state

        Returns:
            State: The state the detector is in.
                See state diagram in class docstring.
        """
        return self.status.state

    def _set_state(self, state: State) -> None:
        self.status.state = state

    def _is_in_state(self, state: State) -> bool:
        return self.get_state() is state
