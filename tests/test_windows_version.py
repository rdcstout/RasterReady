import sys

import pytest

from tools.windows_version import details


@pytest.mark.parametrize("version", ["0.1.0.dev0", "0.1.0a2", "0.1.0rc1"])
def test_windows_prerelease_is_labeled(version):
    result = details(version)
    assert result["numeric"] == (0, 1, 0, 0)
    assert result["flags"] == 2
    assert result["strings"]["ProductVersion"] == version
    assert result["strings"]["FileVersion"] == version


def test_windows_stable_version_and_upper_boundary():
    result = details("65535.2.3.4")
    assert result["numeric"] == (65535, 2, 3, 4)
    assert result["flags"] == 0
    assert result["strings"]["OriginalFilename"] == "RasterReady.exe"


@pytest.mark.parametrize("version", ["65536.0.0", "1.2.3.4.5", "1!1.0", "1.0+local"])
def test_windows_version_cannot_silently_overflow_or_discard_components(version):
    with pytest.raises(ValueError):
        details(version)


@pytest.mark.skipif(
    sys.platform != "win32", reason="Uses the native PyInstaller version serializer"
)
def test_windows_resource_binary_roundtrip():
    from PyInstaller.utils.win32.versioninfo import VSVersionInfo

    from tools.windows_version import resource

    original = resource("0.1.0.dev0")
    binary = original.toRaw()
    parsed = VSVersionInfo()
    parsed.fromRaw(binary)
    assert parsed.toRaw() == binary
    assert parsed.ffi.fileFlags == 2
    assert parsed.ffi.fileVersionMS == 1
    assert parsed.ffi.fileVersionLS == 0
