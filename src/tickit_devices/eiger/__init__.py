import logging

import pydantic.v1.dataclasses
from tickit.adapters.io import HttpIo, ZeroMqPushIo
from tickit.core.adapter import AdapterContainer
from tickit.core.components.component import Component, ComponentConfig
from tickit.core.components.device_component import DeviceComponent

from tickit_devices.eiger.eiger import EigerDevice
from tickit_devices.eiger.eiger_adapters import EigerRESTAdapter, EigerZMQAdapter
from tickit_devices.eiger.stream.stream_config import CBOR_STREAM, LEGACY_STREAM


@pydantic.v1.dataclasses.dataclass
class Eiger(ComponentConfig):
    """Eiger simulation with HTTP adapter."""

    host: str = "0.0.0.0"
    port: int = 8081
    stream_host: str = "127.0.0.1"
    stream_legacy_port: int = 9999
    stream_cbor_port: int = 31001

    def __call__(self) -> Component:  # noqa: D102
        logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
        device = EigerDevice()
        adapters = [
            AdapterContainer(
                EigerRESTAdapter(device),
                HttpIo(
                    self.host,
                    self.port,
                ),
            ),
            AdapterContainer(
                EigerZMQAdapter(device.streams[LEGACY_STREAM]),
                ZeroMqPushIo(
                    self.stream_host,
                    self.stream_legacy_port,
                ),
            ),
            AdapterContainer(
                EigerZMQAdapter(device.streams[CBOR_STREAM]),
                ZeroMqPushIo(
                    self.stream_host,
                    self.stream_cbor_port,
                ),
            ),
        ]
        return DeviceComponent(
            name=self.name,
            device=device,
            adapters=adapters,
        )
