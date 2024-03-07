from typing import Any, Dict, Iterable, Tuple, Union

from pydantic.v1 import BaseModel
from zmq import Frame

Json = Dict[str, Any]
Sendable = Union[bytes, Frame, memoryview]
MultipartMessage = Iterable[Sendable]

DEFAULT_HEADER_TYPE = "dheader-1.0"


class AcquisitionSeriesHeader(BaseModel):
    """Sent before a series of images (and associated headers)."""

    header_detail: str
    series: int
    htype: str = DEFAULT_HEADER_TYPE


class AcquisitionSeriesFooter(BaseModel):
    """Sent at the end of a series of images (and associated headers)."""

    series: int
    htype: str = "dseries_end-1.0"


class AcquisitionDetailsHeader(BaseModel):
    """Describes an additional dataset sent at the beginning of a series.

    Used when header_detail is set to all in AcquisitionSeriesHeader.
    """

    htype: str = DEFAULT_HEADER_TYPE
    shape: Tuple[int, int]
    type: str


class ImageHeader(BaseModel):
    """Sent before a detector image blob.

    Metadata about the acquisition operation.
    """

    frame: int
    hash: str
    series: int
    htype: str = "dimage-1.0"


class ImageCharacteristicsHeader(BaseModel):
    """Sent before a detector image blob.

    Metadata about the image.
    """

    encoding: str
    shape: Tuple[int, int]
    size: int
    type: str
    htype: str = "dimage_d-1.0"


class ImageConfigHeader(BaseModel):
    """Sent before a detector image blob.

    Describes the metrics on the image acquisition. Time values are ints given in ns.
    """

    real_time: int
    start_time: int
    stop_time: int
    htype: str = "dconfig-1.0"
