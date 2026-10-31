from types import SimpleNamespace

import numpy as np
import pytest
import rawpy
from PIL import Image

from rasterready.core import PreparationError, Size, prepare


def test_raw_is_developed_not_preview_extracted(tmp_path, monkeypatch):
    calls = []

    class Raw:
        sizes = SimpleNamespace(raw_width=9600, raw_height=6400)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            calls.append("closed")

        def open_file(self, path):
            calls.append(("open", path))

        def unpack(self):
            calls.append("unpack")

        def postprocess(self, **kwargs):
            calls.append(kwargs)
            # Portrait output represents LibRaw having applied the orientation.
            return np.full((120, 80, 3), 128, dtype=np.uint8)

    monkeypatch.setattr(rawpy, "RawPy", Raw)
    source = tmp_path / "SONY.ARW"
    source.write_bytes(b"test stub")
    result = prepare(source, tmp_path, Size(40))
    assert (result.width, result.height) == (40, 60)
    assert "unpack" in calls
    params = next(c for c in calls if isinstance(c, dict))
    assert params["use_camera_wb"] is True
    assert params["output_color"] == rawpy.ColorSpace.sRGB
    assert "user_flip" not in params
    assert any("RAW developed" in note for note in result.notes)
    with Image.open(result.output) as image:
        assert not image.info and not image.getexif()


def test_oversized_raw_rejected_before_sensor_unpack(tmp_path, monkeypatch):
    class Raw:
        sizes = SimpleNamespace(raw_width=50000, raw_height=50000)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def open_file(self, path):
            pass

        def unpack(self):
            pytest.fail("Oversized RAW must not be unpacked")

    monkeypatch.setattr(rawpy, "RawPy", Raw)
    (tmp_path / "huge.arw").write_bytes(b"test stub")
    with pytest.raises(PreparationError, match="100 megapixel"):
        prepare(tmp_path / "huge.arw", tmp_path, Size(100))


@pytest.mark.parametrize("extension", ["arw", "ARW", "srf", "sr2"])
def test_damaged_raw_is_actionable_without_partial_png(tmp_path, extension):
    source = tmp_path / f"bad.{extension}"
    source.write_bytes(b"not RAW")
    with pytest.raises(PreparationError, match="Sony RAW"):
        prepare(source, tmp_path, Size(100))
    assert not list(tmp_path.glob("*.png"))
