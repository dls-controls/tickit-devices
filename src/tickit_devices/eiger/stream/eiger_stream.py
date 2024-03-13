import logging
from queue import Queue
from typing import Any, Iterable, Mapping, TypedDict, Union

from pydantic.v1 import BaseModel
from tickit.core.typedefs import SimTime
from typing_extensions import TypedDict

from tickit_devices.eiger.data.dummy_image import Image
from tickit_devices.eiger.data.schema import (
    AcquisitionDetailsHeader,
    AcquisitionSeriesFooter,
    AcquisitionSeriesHeader,
    ImageCharacteristicsHeader,
    ImageConfigHeader,
    ImageHeader,
)
from tickit_devices.eiger.eiger_settings import EigerSettings
from tickit_devices.eiger.stream.stream_config import StreamConfig
from tickit_devices.eiger.stream.stream_status import StreamStatus

LOGGER = logging.getLogger(__name__)


_Message = Union[BaseModel, Mapping[str, Any], bytes]


class EigerStream:
    """Simulation of an Eiger stream."""

    status: StreamStatus
    config: StreamConfig
    callback_period: SimTime

    _message_buffer: Queue[_Message]

    class Inputs(TypedDict): ...

    class Outputs(TypedDict): ...

    def __init__(self, callback_period: int = int(1e9)) -> None:
        """An Eiger Stream constructor."""
        self.status = StreamStatus()
        self.config = StreamConfig()
        self.callback_period = SimTime(callback_period)

        self._message_buffer = Queue()

    def begin_series(self, settings: EigerSettings, series_id: int) -> None:
        """Send the headers marking the beginning of the acquisition series.

        Args:
            settings: Current detector configuration, a snapshot may be sent with the
                headers.
            series_id: ID for the acquisition series.
        """
        header_detail = self.config.header_detail
        header = AcquisitionSeriesHeader(
            header_detail=header_detail,
            series=series_id,
        )
        self._buffer(header)

        if header_detail != "none":
            config_header = settings.filtered(
                ["flatfield", "pixelmask" "countrate_correction_table"]
            )
            self._buffer(config_header)

            if header_detail == "all":
                x = settings.x_pixels_in_detector
                y = settings.y_pixels_in_detector

                flatfield_header = AcquisitionDetailsHeader(
                    htype="flatfield-1.0",
                    shape=(x, y),
                    type="float32",
                )
                self._buffer(flatfield_header)
                flatfield_data_blob = {"blob": "blob"}
                self._buffer(flatfield_data_blob)

                pixel_mask_header = AcquisitionDetailsHeader(
                    htype="dpixelmask-1.0",
                    shape=(x, y),
                    type="uint32",
                )
                self._buffer(pixel_mask_header)
                pixel_mask_data_blob = {"blob": "blob"}
                self._buffer(pixel_mask_data_blob)

                countrate_table_header = AcquisitionDetailsHeader(
                    htype="dcountrate_table-1.0",
                    shape=(x, y),
                    type="float32",
                )
                self._buffer(countrate_table_header)
                countrate_table_data_blob = {"blob": "blob"}
                self._buffer(countrate_table_data_blob)

    def insert_image(self, image: Image, series_id: int) -> None:
        """Send headers and an data blob for a single image.

        Args:
            image: The image with associated metadata
            series_id: ID for the acquisition series.
        """
        header = ImageHeader(
            frame=image.index,
            hash=image.hash,
            series=series_id,
        )
        characteristics_header = ImageCharacteristicsHeader(
            encoding=image.encoding,
            shape=image.shape,
            size=len(image.data),
            type=image.dtype,
        )
        config_header = ImageConfigHeader(
            real_time=0.0,
            start_time=0.0,
            stop_time=0.0,
        )

        self._buffer(header)
        self._buffer(characteristics_header)
        self._buffer(image.data)
        self._buffer(config_header)

    def end_series(self, series_id: int) -> None:
        """Send footer marking the end of an acquisition series.

        Args:
            series_id: ID of the series to end.
        """
        footer = AcquisitionSeriesFooter(series=series_id)
        self._buffer(footer)

    def consume_data(self) -> Iterable[_Message]:
        """Consume all headers and data buffered by other methods.

        Returns:
            Iterable[_Message]: Iterable of headers and data
        """
        while not self._message_buffer.empty():
            yield self._message_buffer.get()

    def _buffer(self, message: _Message) -> None:
        self._message_buffer.put_nowait(message)
