from typing import Any, List, Mapping, Union

import pytest
from pydantic.v1 import BaseModel

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
from tickit_devices.eiger.stream.eiger_stream import EigerStream


@pytest.fixture
def stream() -> EigerStream:
    return EigerStream()


TEST_SERIES_ID = 1

MINIMAL_HEADER = [
    AcquisitionSeriesHeader(
        header_detail="none",
        series=TEST_SERIES_ID,
    )
]

EIGER_SETTINGS_HEADER = EigerSettings().filtered(
    ["flatfield", "pixelmask" "countrate_correction_table"]
)
X_SIZE = EIGER_SETTINGS_HEADER["x_pixels_in_detector"]
Y_SIZE = EIGER_SETTINGS_HEADER["y_pixels_in_detector"]

BASIC_HEADERS = [
    AcquisitionSeriesHeader(
        header_detail="basic",
        series=TEST_SERIES_ID,
    ),
    EIGER_SETTINGS_HEADER,
]

ALL_HEADERS = [
    AcquisitionSeriesHeader(
        header_detail="all",
        series=TEST_SERIES_ID,
    ),
    EIGER_SETTINGS_HEADER,
    AcquisitionDetailsHeader(
        htype="flatfield-1.0",
        shape=(X_SIZE, Y_SIZE),
        type="float32",
    ),
    {"blob": "blob"},
    AcquisitionDetailsHeader(
        htype="dpixelmask-1.0",
        shape=(X_SIZE, Y_SIZE),
        type="uint32",
    ),
    {"blob": "blob"},
    AcquisitionDetailsHeader(
        htype="dcountrate_table-1.0",
        shape=(X_SIZE, Y_SIZE),
        type="float32",
    ),
    {"blob": "blob"},
]


END_SERIES_FOOTER = [AcquisitionSeriesFooter(series=TEST_SERIES_ID)]


@pytest.mark.parametrize(
    "header_detail,expected_headers",
    [
        ("none", MINIMAL_HEADER),
        ("basic", BASIC_HEADERS),
        ("all", ALL_HEADERS),
    ],
)
def test_begin_series_produces_correct_headers(
    stream: EigerStream,
    header_detail: str,
    expected_headers: List[Union[BaseModel, bytes, Mapping[str, Any]]],
) -> None:
    settings = EigerSettings()
    stream.begin_series(settings, TEST_SERIES_ID, header_detail)
    blobs = list(stream.consume_data())
    assert blobs == expected_headers


@pytest.mark.parametrize("number_of_times", [1, 2])
def test_insert_image_produces_correct_headers_and_blobs(
    stream: EigerStream, number_of_times: int
) -> None:
    for i in range(number_of_times):
        image = Image.create_dummy_image(i, (X_SIZE, Y_SIZE))
        stream.insert_image(image, TEST_SERIES_ID)
        blobs = list(stream.consume_data())
        assert blobs == expected_image_blobs(image)


def test_end_series_produces_correct_headers(
    stream: EigerStream,
) -> None:
    stream.end_series(TEST_SERIES_ID)
    blobs = list(stream.consume_data())
    assert blobs == END_SERIES_FOOTER


def test_data_buffered(stream: EigerStream) -> None:
    settings = EigerSettings()
    stream.begin_series(settings, TEST_SERIES_ID, "all")
    image = Image.create_dummy_image(0, (X_SIZE, Y_SIZE))
    stream.insert_image(image, TEST_SERIES_ID)
    stream.end_series(TEST_SERIES_ID)
    blobs = list(stream.consume_data())
    assert blobs == ALL_HEADERS + expected_image_blobs(image) + END_SERIES_FOOTER


def expected_image_blobs(image: Image) -> List[Union[bytes, BaseModel]]:
    return [
        ImageHeader(
            frame=image.index,
            hash=image.hash,
            series=TEST_SERIES_ID,
        ),
        ImageCharacteristicsHeader(
            encoding=image.encoding,
            shape=image.shape,
            size=len(image.data),
            type=image.dtype,
        ),
        image.data,
        ImageConfigHeader(
            real_time=0,
            start_time=0,
            stop_time=0,
        ),
    ]
