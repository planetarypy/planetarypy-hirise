"""Tests for the detached-label module (no network required)."""

import pvl
import pytest

from planetarypy_hirise.label import _find_image_object

# Decoy-laden snippet: LINE_PROJECTION_OFFSET must NOT satisfy the search,
# and the real calibration sits nested two objects deep, as in RDR labels.
SNIPPET = """\
PDS_VERSION_ID = PDS3
OBJECT = IMAGE_MAP_PROJECTION
    LINE_PROJECTION_OFFSET = -127217.5
    SAMPLE_PROJECTION_OFFSET = -507082.5
END_OBJECT = IMAGE_MAP_PROJECTION
OBJECT = UNCOMPRESSED_FILE
    OBJECT = IMAGE
        SCALING_FACTOR = 1.14920397871365e-05
        OFFSET = 0.015762468278443
    END_OBJECT = IMAGE
END_OBJECT = UNCOMPRESSED_FILE
END
"""


def test_find_image_object_skips_projection_decoys():
    label = pvl.loads(SNIPPET)
    img = _find_image_object(label)
    assert img is not None
    assert float(img["SCALING_FACTOR"]) == pytest.approx(1.14920397871365e-05)
    assert float(img["OFFSET"]) == pytest.approx(0.015762468278443)


def test_find_image_object_none_when_absent():
    label = pvl.loads("PDS_VERSION_ID = PDS3\nEND\n")
    assert _find_image_object(label) is None
