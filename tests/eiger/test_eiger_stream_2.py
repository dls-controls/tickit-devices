import datetime

import cbor2
import pytest

from tickit_devices.eiger.data.dummy_image import Image
from tickit_devices.eiger.eiger import EigerDevice
from tickit_devices.eiger.eiger_settings import EigerSettings
from tickit_devices.eiger.stream.eiger_stream_2 import EigerStream2


@pytest.fixture
def stream() -> EigerStream2:
    return EigerStream2()


@pytest.fixture
def eiger() -> EigerDevice:
    return EigerDevice()


TEST_SERIES_ID = 1

EIGER_SETTINGS_HEADER = EigerSettings().filtered(
    ["flatfield", "pixelmask" "countrate_correction_table"]
)
X_SIZE = EIGER_SETTINGS_HEADER["x_pixels_in_detector"]
Y_SIZE = EIGER_SETTINGS_HEADER["y_pixels_in_detector"]

BASIC_START_MESSAGE = {
    "type": "start",
    "series_id": 1,
    "series_unique_id": "01H95H3ZJ0B256900H4DV38G24",
    "arm_date": datetime.datetime(
        2023,
        8,
        31,
        12,
        9,
        45,
        24000,
        tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)),
    ),
    "beam_center_x": 2049.2682222222224,
    "beam_center_y": 2157.8508000000006,
    "channels": ["threshold_1"],
    "count_time": 0.1,
    "countrate_correction_enabled": True,
    "detector_description": "Simulated Eiger X 16M Detector",
    "detector_serial_number": "EIGERSIM001",
    "detector_translation": [0.15369511666666666, 0.16183881000000003, -0.2893],
    "flatfield_enabled": True,
    "frame_time": 0.12,
    "goniometer": {
        "chi": {"increment": 0.0, "start": 0.0},
        "kappa": {"increment": 0.0, "start": 0.0},
        "omega": {"increment": 0.0, "start": 0.0},
        "phi": {"increment": 0.0, "start": 0.0},
        "two_theta": {"increment": 0.0, "start": 0.0},
    },
    "image_size_x": 4148,
    "image_size_y": 4362,
    "incident_energy": 4020.5,
    "incident_wavelength": 1.0,
    "number_of_images": 1,
    "pixel_mask_enabled": False,
    "pixel_size_x": 0.01,
    "pixel_size_y": 0.01,
    "saturation_value": 1000,
    "sensor_material": "Silicon",
    "sensor_thickness": 0.01,
    "threshold_energy": {
        "threshold_1": 6349.949919757628,
        "threshold_2": 17779.859775321358,
    },
    "virtual_pixel_interpolation_enabled": True,
}


# This does not include 'image_id' or 'data' as these are tested separately
IMAGE_MESSAGE = {
    "type": "image",
    "series_id": 1,
    "series_unique_id": "01H93H861TK4FMT4H5CT49PCN5",
    "real_time": [500000000, 50000000],
    "series_date": datetime.datetime(
        2023,
        8,
        30,
        17,
        33,
        41,
        934000,
        tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)),
    ),
    "start_time": [0, 50000000],
    "stop_time": [500000000, 50000000],
}


END_MESSAGE = {
    "type": "end",
    "series_id": 1,
    "series_unique_id": "01H93H861TK4FMT4H5CT49PCN5",
}


@pytest.mark.parametrize(
    "header_detail",
    [("none"), ("basic")],
)
def test_begin_series_message_basic(stream: EigerStream2, header_detail: str) -> None:
    settings = EigerSettings()

    stream.begin_series(settings, TEST_SERIES_ID, header_detail)
    message = cbor2.loads(list(stream.consume_data())[0])

    assert message == BASIC_START_MESSAGE
    assert not any(
        f in message
        for f in ["flatfield", "pixel_mask", "countrate_correction_lookup_table"]
    )


def test_begin_series_message_all(stream: EigerStream2) -> None:
    settings = EigerSettings()

    stream.begin_series(settings, TEST_SERIES_ID, "all")
    message = cbor2.loads(list(stream.consume_data())[0])

    assert all(
        f in message
        for f in ["flatfield", "pixel_mask", "countrate_correction_lookup_table"]
    )


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
