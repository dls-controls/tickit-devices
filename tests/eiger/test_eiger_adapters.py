from pytest_mock import MockerFixture

from tickit_devices.eiger.eiger_adapters import EigerZMQAdapter


def test_after_update(mocker: MockerFixture) -> None:
    test_data = [b"data", b"some more data"]

    # Mock consume_data to return with data the first time and nothing the second time
    # Patch consume_data to return with data the first time and nothing the second time
    device_mock = mocker.MagicMock()
    device_mock.stream.consume_data.side_effect = [test_data, []]

    zmq_adapter = EigerZMQAdapter(device_mock)
    add_mock = mocker.patch.object(zmq_adapter, "add_message_to_stream")

    # Test after_update only calls add_message_to_stream with non-empty data
    # First after_update should only call add_message_to_stream with non-empty data
    zmq_adapter.after_update()
    add_mock.assert_called_once_with(test_data)
    add_mock.reset_mock()
    zmq_adapter.after_update()
    add_mock.assert_not_called()
