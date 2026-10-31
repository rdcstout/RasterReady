"""Native build selection must follow the installed compiler and fail clearly."""

import json
from types import SimpleNamespace

import pytest

from tools import build_heic_windows as builder


@pytest.mark.parametrize(
    ("key", "version", "generator"),
    [
        ("ProgramFiles(x86)", "17.14.1", "Visual Studio 17 2022"),
        ("ProgramFiles(x86)", "18.0.2", "Visual Studio 18 2026"),
        ("PROGRAMFILES(X86)", "18.0.2", "Visual Studio 18 2026"),
    ],
)
def test_selects_installed_cpp_instance(tmp_path, monkeypatch, key, version, generator):
    locator = tmp_path / "Microsoft Visual Studio/Installer/vswhere.exe"
    locator.parent.mkdir(parents=True)
    locator.touch()
    installation = tmp_path / "Compiler with spaces"
    installation.mkdir()

    def locate(arguments, **kwargs):
        assert "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" in arguments
        assert arguments[0] == str(locator)
        assert kwargs["check"] is True
        return SimpleNamespace(
            stdout=json.dumps(
                [{"installationVersion": version, "installationPath": str(installation)}]
            )
        )

    monkeypatch.setattr(builder.subprocess, "run", locate)
    assert builder.visual_studio({key: str(tmp_path)}) == (
        generator,
        installation,
    )


@pytest.mark.parametrize("instances", [[], [{"installationVersion": "19.0"}]])
def test_refuses_missing_or_unsupported_toolchain(tmp_path, monkeypatch, instances):
    locator = tmp_path / "Microsoft Visual Studio/Installer/vswhere.exe"
    locator.parent.mkdir(parents=True)
    locator.touch()
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(instances)),
    )
    with pytest.raises(SystemExit, match="No installed|Unsupported Visual Studio"):
        builder.visual_studio({"ProgramFiles(x86)": str(tmp_path)})


def test_missing_locator_fails_before_running_a_compiler(tmp_path):
    with pytest.raises(SystemExit, match="vswhere.exe is missing"):
        builder.visual_studio({"ProgramFiles(x86)": str(tmp_path)})
