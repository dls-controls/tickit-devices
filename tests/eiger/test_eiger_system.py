import aiohttp
import pytest

DETECTOR_URL = "http://localhost:8081/detector/api/1.8.0/"
FILE_WRITER_URL = "http://localhost:8081/filewriter/api/1.8.0/"
MONITOR_URL = "http://localhost:8081/monitor/api/1.8.0/"
STREAM_URL = "http://localhost:8081/stream/api/1.8.0/"
REQUEST_TIMEOUT = 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tickit_task", ["examples/configs/eiger/eiger.yaml"], indirect=True
)
async def test_eiger_system(tickit_task):
    commands = {
        "initialize": {"sequence id": 1},
        "disarm": {"sequence id": 3},
        "cancel": {"sequence id": 5},
        "abort": {"sequence id": 6},
    }

    headers = {"content-type": "application/json"}

    async def get_status(status, expected):
        async with session.get(
            DETECTOR_URL + f"status/{status}",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert expected == (await response.json())["value"]

    async with aiohttp.ClientSession() as session:
        await get_status(status="state", expected="na")

        # Test setting config var before Eiger set up
        async with session.put(
            DETECTOR_URL + "config/element",
            headers=headers,
            json={"value": "test"},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert (await response.json()) == []

        # Test each command
        for key, value in commands.items():
            async with session.put(
                DETECTOR_URL + f"command/{key}",
                timeout=REQUEST_TIMEOUT,
            ) as response:
                assert value == (await response.json())

        # Check status
        await get_status(status="board_000/th0_temp", expected=24.5)
        await get_status(status="builder/dcu_buffer_free", expected=0.5)

        # Test Eiger in IDLE state
        await get_status(status="state", expected="idle")

        # Test settings/getting config
        async with session.get(
            DETECTOR_URL + "config/element",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert (await response.json())["value"] == "Co"

        async with session.put(
            DETECTOR_URL + "config/element",
            headers=headers,
            json={"value": "Li"},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert (await response.json()) == ["element"]

        async with session.get(
            DETECTOR_URL + "config/photon_energy",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert 54.3 == (await response.json())["value"]

        async with session.get(
            FILE_WRITER_URL + "config/mode",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert "enabled" == (await response.json())["value"]

        async with session.put(
            FILE_WRITER_URL + "config/mode",
            headers=headers,
            json={"value": "enabled"},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert ["mode"] == (await response.json())

        # Test filewriter, monitor and stream endpoints
        async with session.get(
            FILE_WRITER_URL + "status/state",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert "ready" == (await response.json())["value"]

        async with session.get(
            MONITOR_URL + "config/mode",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert "enabled" == (await response.json())["value"]

        async with session.put(
            MONITOR_URL + "config/mode",
            headers=headers,
            json={"value": "enabled"},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert ["mode"] == (await response.json())

        async with session.get(
            MONITOR_URL + "status/error",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert [] == (await response.json())["value"]

        async with session.get(
            STREAM_URL + "config/mode",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert "enabled" == (await response.json())["value"]

        async with session.put(
            STREAM_URL + "config/mode",
            headers=headers,
            json={"value": "enabled"},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert ["mode"] == (await response.json())

        # Test acquisition in ints mode
        async with session.put(
            DETECTOR_URL + "config/trigger_mode",
            headers=headers,
            json={"value": "ints"},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert ["trigger_mode"] == (await response.json())

        async with session.get(
            STREAM_URL + "status/state",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert "ready" == (await response.json())["value"]

        assert get_status(status="state", expected="idle")

        async with session.put(
            DETECTOR_URL + "command/arm",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert {"sequence id": 2} == (await response.json())

        assert get_status(status="state", expected="ready")

        async with session.put(
            DETECTOR_URL + "command/trigger",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert {"sequence id": 4} == (await response.json())

        # Test we get a 404 for a non-existent URI
        async with session.get(
            DETECTOR_URL + "status/doesnt_exist",
            timeout=REQUEST_TIMEOUT,
        ) as response:
            assert response.status == 404
