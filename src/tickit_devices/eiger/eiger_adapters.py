import logging

from aiohttp import web
from apischema import serialize
from tickit.adapters.http import HttpAdapter
from tickit.adapters.specifications import HttpEndpoint
from tickit.adapters.zmq import ZeroMqPushAdapter

from tickit_devices.eiger.eiger import EigerDevice
from tickit_devices.eiger.eiger_schema import SequenceComplete, Value, construct_value
from tickit_devices.eiger.eiger_status import State
from tickit_devices.eiger.stream.eiger_stream import EigerStream
from tickit_devices.eiger.stream.eiger_stream_2 import EigerStream2

API_VERSION = "1.8.0"
DETECTOR_API = f"detector/api/{API_VERSION}"
STREAM_API = f"stream/api/{API_VERSION}"
MONITOR_API = "monitor/api/1.8.0"
FILEWRITER_API = "filewriter/api/1.8.0"

LOGGER = logging.getLogger("EigerAdapter")


class EigerRESTAdapter(HttpAdapter):
    """An Eiger adapter which parses the commands sent to the HTTP server."""

    device: EigerDevice

    def __init__(self, device: EigerDevice) -> None:
        self.device = device

    @HttpEndpoint.get(f"/{DETECTOR_API}" + "/config/{parameter_name}")
    async def get_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting configuration variables from the Eiger.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["parameter_name"]

        if hasattr(self.device.settings, param):
            return web.json_response(construct_value(self.device.settings, param))
        else:
            return web.json_response(status=404)

    @HttpEndpoint.put(f"/{DETECTOR_API}" + "/config/{parameter_name}")
    async def put_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for setting configuration variables for the Eiger.

        Args:
            request (web.Request): The request object that takes the given parameter
            and value.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["parameter_name"]

        response = await request.json()

        if self.device.get_state() is not State.IDLE:
            LOGGER.warning("Eiger not initialized or is currently running.")
            return web.json_response(serialize([]))
        elif (
            hasattr(self.device.settings, param)
            and self.device.get_state() is State.IDLE
        ):
            attr = response["value"]

            LOGGER.debug(f"Changing to {str(attr)} for {str(param)}")

            self.device.settings[param] = attr

            LOGGER.debug("Set " + str(param) + " to " + str(attr))
            return web.json_response(serialize([param]))
        else:
            LOGGER.debug("Eiger has no config variable: " + str(param))
            return web.json_response(status=404)

    @HttpEndpoint.get(f"/{DETECTOR_API}" + "/status/{status_param}")
    async def get_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting the status of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["status_param"]

        if hasattr(self.device.status, param):
            data = construct_value(self.device.status, param)

        else:
            return web.json_response(status=404)

        return web.json_response(data)

    @HttpEndpoint.get(f"/{DETECTOR_API}" + "/status/board_000/{status_param}")
    async def get_board_000_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting the status of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        return await self.get_status(request)

    @HttpEndpoint.get(f"/{DETECTOR_API}" + "/status/builder/{status_param}")
    async def get_builder_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting the status of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        return await self.get_status(request)

    @HttpEndpoint.put(f"/{DETECTOR_API}" + "/command/initialize", interrupt=True)
    async def initialize_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'initialize' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.initialize()

        LOGGER.debug("Initializing Eiger...")
        return web.json_response(serialize(SequenceComplete(1)))

    @HttpEndpoint.put(f"/{DETECTOR_API}" + "/command/arm", interrupt=True)
    async def arm_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'arm' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.arm()

        LOGGER.debug("Arming Eiger...")
        return web.json_response(serialize(SequenceComplete(2)))

    @HttpEndpoint.put(f"/{DETECTOR_API}" + "/command/disarm", interrupt=True)
    async def disarm_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'disarm' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.disarm()

        LOGGER.debug("Disarming Eiger...")
        return web.json_response(serialize(SequenceComplete(3)))

    @HttpEndpoint.put(f"/{DETECTOR_API}" + "/command/trigger", interrupt=False)
    async def trigger_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'trigger' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        LOGGER.debug("Triggering Eiger")
        await self.device.trigger()

        await self.interrupt()
        await self.device.finished_aquisition.wait()

        return web.json_response(serialize(SequenceComplete(4)))

    @HttpEndpoint.put(f"/{DETECTOR_API}" + "/command/cancel", interrupt=True)
    async def cancel_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'cancel' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.cancel()

        LOGGER.debug("Cancelling Eiger...")
        return web.json_response(serialize(SequenceComplete(5)))

    @HttpEndpoint.put(f"/{DETECTOR_API}" + "/command/abort", interrupt=True)
    async def abort_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'abort' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.abort()

        LOGGER.debug("Aborting Eiger...")
        return web.json_response(serialize(SequenceComplete(6)))

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

        if hasattr(self.device.stream_status, param):
            return web.json_response(construct_value(self.device.stream_status, param))
        else:
            return web.json_response(status=404)

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

        if hasattr(self.device.stream_config, param):
            return web.json_response(construct_value(self.device.stream_config, param))
        else:
            return web.json_response(status=404)

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

        if hasattr(self.device.stream_config, param):
            attr = response["value"]

            LOGGER.debug(f"Changing to {attr} for {param}")

            self.device.stream_config[param] = attr

            LOGGER.debug("Set " + str(param) + " to " + str(attr))
            return web.json_response(serialize([param]))
        else:
            LOGGER.debug("Eiger has no config variable: " + str(param))
            return web.json_response(status=404)

    @HttpEndpoint.get(f"/{MONITOR_API}" + "/config/{param}")
    async def get_monitor_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting config values from the Monitor.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        if hasattr(self.device.monitor_config, param):
            return web.json_response(construct_value(self.device.monitor_config, param))
        else:
            return web.json_response(status=404)

    @HttpEndpoint.put(f"/{MONITOR_API}" + "/config/{param}")
    async def put_monitor_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for setting config values for the Monitor.

        Args:
            request (web.Request): The request object that takes the given parameter
            and value.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        response = await request.json()

        if hasattr(self.device.monitor_config, param):
            attr = response["value"]

            LOGGER.debug(f"Changing to {attr} for {param}")

            self.device.monitor_config[param] = attr

            LOGGER.debug("Set " + str(param) + " to " + str(attr))
            return web.json_response(serialize([param]))
        else:
            LOGGER.debug("Eiger has no config variable: " + str(param))
            return web.json_response(status=404)

    @HttpEndpoint.get(f"/{MONITOR_API}" + "/status/{param}")
    async def get_monitor_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting status values from the Monitor.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        if hasattr(self.device.monitor_status, param):
            return web.json_response(construct_value(self.device.monitor_status, param))
        else:
            return web.json_response(status=404)

    @HttpEndpoint.get(f"/{FILEWRITER_API}" + "/config/{param}")
    async def get_filewriter_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting config values from the Filewriter.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        if hasattr(self.device.filewriter_config, param):
            return web.json_response(
                construct_value(self.device.filewriter_config, param)
            )
        else:
            return web.json_response(status=404)

    @HttpEndpoint.put(f"/{FILEWRITER_API}" + "/config/{param}")
    async def put_filewriter_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for setting config values for the Filewriter.

        Args:
            request (web.Request): The request object that takes the given parameter
            and value.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        response = await request.json()

        if hasattr(self.device.filewriter_config, param):
            attr = response["value"]

            LOGGER.debug(f"Changing to {attr} for {param}")

            self.device.filewriter_config[param] = attr

            LOGGER.debug("Set " + str(param) + " to " + str(attr))
            return web.json_response(serialize([param]))
        else:
            LOGGER.debug("Eiger has no config variable: " + str(param))
            return web.json_response(status=404)

    @HttpEndpoint.get(f"/{FILEWRITER_API}" + "/status/{param}")
    async def get_filewriter_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting status values from the Filewriter.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        if hasattr(self.device.filewriter_status, param):
            return web.json_response(
                construct_value(self.device.filewriter_status, param)
            )
        else:
            return web.json_response(status=404)


class EigerZMQAdapter(ZeroMqPushAdapter):
    """An Eiger adapter which parses the data to send along a ZeroMQStream."""

    device: EigerDevice

    def __init__(self, stream: EigerStream | EigerStream2) -> None:
        super().__init__()
        self.stream = stream

    def after_update(self) -> None:
        """Updates IOC values immediately following a device update."""
        if buffered_data := list(self.stream.consume_data()):
            self.add_message_to_stream(buffered_data)
