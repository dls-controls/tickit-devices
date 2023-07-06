import json
import logging
from queue import Queue
from typing import Any, Iterable, Mapping, TypedDict, Union

from aiohttp import web
from apischema import serialize
from pydantic import BaseModel, parse_obj_as
from tickit.adapters.interpreters.endpoints.http_endpoint import HttpEndpoint
from tickit.core.typedefs import SimTime
from typing_extensions import TypedDict
from zmq import Frame

from tickit_devices.eiger.data.dummy_image import Image
from tickit_devices.eiger.data.schema import (
    AcquisitionDetailsHeader,
    AcquisitionSeriesFooter,
    AcquisitionSeriesHeader,
    ImageCharacteristicsHeader,
    ImageConfigHeader,
    ImageHeader,
)
from tickit_devices.eiger.eiger_schema import construct_value
from tickit_devices.eiger.eiger_settings import EigerSettings
from tickit_devices.eiger.stream.stream_config import StreamConfig
from tickit_devices.eiger.stream.stream_status import StreamStatus

LOGGER = logging.getLogger(__name__)
STREAM_API = "stream/api/1.8.0"

_Sendable = Union[bytes, Frame, memoryview]
_Message = Union[_Sendable, str, Mapping[str, Any], BaseModel]


class EigerStream:
    """Simulation of an Eiger stream."""

    stream_status: StreamStatus
    stream_config: StreamConfig
    stream_callback_period: SimTime

    _message_buffer: Queue[_Sendable]

    #: An empty typed mapping of input values
    Inputs: TypedDict = TypedDict("Inputs", {})
    #: A typed mapping containing the 'value' output value
    Outputs: TypedDict = TypedDict("Outputs", {})

    def __init__(self, callback_period: int = int(1e9)) -> None:
        """An Eiger Stream constructor."""
        self.stream_status = StreamStatus()
        self.stream_config = StreamConfig()
        self.stream_callback_period = SimTime(callback_period)

        self._message_buffer = Queue()

    def begin_series(self, settings: EigerSettings, series_id: int) -> None:
        header_detail = self.stream_config.header_detail
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
        footer = AcquisitionSeriesFooter(series=series_id)
        self._buffer(footer)

    def consume_data(self) -> Iterable[_Sendable]:
        while not self._message_buffer.empty():
            yield self._message_buffer.get()

    def _buffer(self, message: _Message) -> None:
        serialized = self._serialize(message)
        self._message_buffer.put_nowait(serialized)

    def _serialize(self, message: _Message) -> _Sendable:
        if isinstance(message, BaseModel):
            return self._serialize(message.dict())
        elif isinstance(message, dict) or isinstance(message, str):
            return self._serialize(json.dumps(message).encode("utf_8"))
        elif isinstance(message, bytes):
            return message
        else:
            raise TypeError(f"Message: {message} is not serializable")


class EigerStreamAdapter:
    """An adapter for the Stream."""

    device: EigerStream

    @HttpEndpoint.get(f"/{STREAM_API}" + "/status/{param}")
    async def get_stream_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting status values from the Stream.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        data = construct_value(self.device.stream.stream_status, param)

        return web.json_response(data)

    @HttpEndpoint.get(f"/{STREAM_API}" + "/config/{param}")
    async def get_stream_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting config values from the Stream.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        data = construct_value(self.device.stream.stream_config, param)

        return web.json_response(data)

    @HttpEndpoint.put(f"/{STREAM_API}" + "/config/{param}")
    async def put_stream_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for setting config values for the Stream.

        Args:
            request (web.Request): The request object that takes the given parameter
            and value.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        response = await request.json()

        if hasattr(self.device.stream.stream_config, param):
            attr = response["value"]

            LOGGER.debug(f"Changing to {attr} for {param}")

            self.device.stream.stream_config[param] = attr

            LOGGER.debug("Set " + str(param) + " to " + str(attr))
            return web.json_response(serialize([param]))
        else:
            LOGGER.debug("Eiger has no config variable: " + str(param))
            return web.json_response(serialize([]))
