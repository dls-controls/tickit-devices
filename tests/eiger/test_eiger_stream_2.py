import datetime

import cbor2
import pytest

from tickit_devices.eiger.data.dummy_image import Image
from tickit_devices.eiger.eiger import EigerDevice
from tickit_devices.eiger.eiger_settings import EigerSettings
from tickit_devices.eiger.stream.eiger_stream_2 import EigerStream2, STREAM_SETTINGS_MAP
import json


@pytest.fixture
def stream() -> EigerStream2:
    return EigerStream2()


@pytest.fixture
def eiger() -> EigerDevice:
    return EigerDevice()


TEST_SERIES_ID = 15614

EIGER_SETTINGS_HEADER = EigerSettings().filtered(
    ["flatfield", "pixelmask" "countrate_correction_table"]
)
X_SIZE = EIGER_SETTINGS_HEADER["x_pixels_in_detector"]
Y_SIZE = EIGER_SETTINGS_HEADER["y_pixels_in_detector"]

ALL_FIELDS = ["flatfield", "pixel_mask", "countrate_correction_lookup_table"]

BASIC_START_MESSAGE = {
    "type": "start",
    "series_id": 15614,
    "series_unique_id": "01HBV3JPF9T4ZDPADX6EMK6XMZ",
    "arm_date": datetime.datetime(
        2023,
        10,
        3,
        17,
        47,
        48,
        329000,
        tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)),
    ),
    "beam_center_x": 2049.3840906675064,
    "beam_center_y": 2163.621048575148,
    "channels": ["threshold_1"],
    "count_time": 0.004317472232502031,
    "countrate_correction_lookup_table": b'\x00\x00\x00\x00',
    "countrate_correction_enabled": True,
    "detector_description": "Dectris EIGER2 Si 16M",
    "detector_serial_number": "E-32-0117",
    "detector_translation": [
        0.15370380680006296,
        0.1622715786431361,
        -0.23715919962215962,
    ],
    "flatfield": {"threshold_1": b'\x00\x00\x00\x00'},
    "flatfield_enabled": True,
    "frame_time": 0.004317572232502031,
    "goniometer": {
        "chi": {"increment": 0.0, "start": 30.0},
        "omega": {"increment": 0.1, "start": 0.0},
        "phi": {"increment": 0.0, "start": 0.0},
    },
    "image_size_x": 4148,
    "image_size_y": 4362,
    "incident_energy": 13500.299829398293,
    "incident_wavelength": 0.918381073013,
    "number_of_images": 1,
    "pixel_mask": {"threshold_1": b'\x00\x00\x00\x00'},
    "pixel_mask_enabled": True,
    "pixel_size_x": 7.5e-05,
    "pixel_size_y": 7.5e-05,
    "saturation_value": 21517,
    "sensor_material": "Si",
    "sensor_thickness": 0.00045,
    "threshold_energy": {
        "threshold_1": 6750.149914699146,
        "threshold_2": 18900.41976115761,
    },
    "virtual_pixel_interpolation_enabled": True,
}


# This does not include 'image_id' or 'data' as these are tested separately
IMAGE_MESSAGE = {
    "type": "image",
    "series_id": 15614,
    "series_unique_id": "01HBV3JPF9T4ZDPADX6EMK6XMZ",
    "real_time": [215873, 50000000],
    "series_date": datetime.datetime(
        2023,
        10,
        3,
        17,
        47,
        49,
        434000,
        tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)),
    ),
    "start_time": [0, 50000000],
    "stop_time": [215873, 50000000],
}


END_MESSAGE = {
    "type": "end",
    "series_id": 15614,
    "series_unique_id": "01HBV3JPF9T4ZDPADX6EMK6XMZ",
}


@pytest.mark.parametrize(
    "header_detail",
    [("none"), ("basic")],
)
def test_begin_series_message_basic(stream: EigerStream2, header_detail: str) -> None:
    settings = EigerSettings()

    stream.begin_series(settings, TEST_SERIES_ID, header_detail)
    message = cbor2.loads(list(stream.consume_data())[0])
    for axis, start_value in BASIC_START_MESSAGE["goniometer"].items():
        assert start_value == message["goniometer"][axis]
    message.pop("goniometer")
    reduced_start_message = BASIC_START_MESSAGE.copy()
    reduced_start_message.pop("goniometer")
    for f in ALL_FIELDS:
        reduced_start_message.pop(f)
    assert message == reduced_start_message
    assert not any(
        f in message
        for f in ALL_FIELDS
    )


def test_begin_series_message_all(stream: EigerStream2) -> None:
    # raise NotImplementedError("not sure whats going wrong here")
    settings = EigerSettings()

    stream.begin_series(settings, TEST_SERIES_ID, "all")
    # actually the line above hangs now
    message = cbor2.loads(list(stream.consume_data())[0])
    for axis, start_value in BASIC_START_MESSAGE["goniometer"].items():
        assert start_value == message["goniometer"][axis]
    message.pop("goniometer")
    reduced_start_message = BASIC_START_MESSAGE.copy()
    reduced_start_message.pop("goniometer")
    # the ALL_FIELDS entries get set to default value, overwriting initial message
    for f in ALL_FIELDS:
        assert f in message
        message.pop(f)
        reduced_start_message.pop(f)
    assert message == reduced_start_message


def test_insert_image_produces_correct_message(stream: EigerStream2) -> None:
    for i in range(2):
        image = Image.create_dummy_image(i, (X_SIZE, Y_SIZE))

        stream.insert_image(image, TEST_SERIES_ID)
        message = cbor2.loads(list(stream.consume_data())[0])

        # Image data is too big to compare - just sanity check size
        assert message["data"]["threshold_1"].value[0] == [Y_SIZE, X_SIZE]
        del message["data"]

        # Check image_id and remove it to compare against generic expected message
        assert message["image_id"] == i
        del message["image_id"]

        assert message == IMAGE_MESSAGE


def test_end_series_produces_correct_message(stream: EigerStream2) -> None:
    stream.end_series(TEST_SERIES_ID)
    message = cbor2.loads(list(stream.consume_data())[0])

    assert message == END_MESSAGE


def test_data_buffered(stream: EigerStream2) -> None:
    settings = EigerSettings()
    image = Image.create_dummy_image(0, (X_SIZE, Y_SIZE))

    stream.begin_series(settings, TEST_SERIES_ID, "basic")
    stream.insert_image(image, TEST_SERIES_ID)
    stream.insert_image(image, TEST_SERIES_ID)
    stream.insert_image(image, TEST_SERIES_ID)
    stream.end_series(TEST_SERIES_ID)

    messages = list(cbor2.loads(b) for b in stream.consume_data())

    assert [m["type"] for m in messages] == ["start", "image", "image", "image", "end"]
