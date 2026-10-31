"""Stable GitHub release eligibility. Never downloads or installs a package."""

import platform
import sys
from dataclasses import dataclass
from urllib.parse import quote

from packaging.version import InvalidVersion, Version

REPOSITORY = "https://github.com/rdcstout/RasterReady"
API_URL = "https://api.github.com/repos/rdcstout/RasterReady/releases?per_page=100"
WEEK = 7 * 24 * 60 * 60
MAX_RESPONSE = 2 * 1024 * 1024


@dataclass(frozen=True)
class Update:
    status: str
    version: str = ""
    url: str = ""


def target_platform(system=None, machine=None):
    system = sys.platform if system is None else system
    machine = (platform.machine() if machine is None else machine).lower()
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64", ("dmg",)
    if system == "win32" and machine in {"amd64", "x86_64"}:
        return "windows-x64", ("exe",)
    if system.startswith("linux") and machine in {"amd64", "x86_64"}:
        return "linux-x64", ("AppImage", "deb")
    return None


def select_release(releases, current, target):
    """Only published stable releases with a package for this OS/CPU qualify."""
    try:
        installed = Version(current)
    except InvalidVersion:
        return Update("unknown")
    if target is None or not isinstance(releases, list):
        return Update("unknown")
    candidates = []
    malformed = False
    for release in releases:
        if not isinstance(release, dict):
            return Update("unknown")
        if release.get("draft") is not False or release.get("prerelease") is not False:
            continue
        tag = release.get("tag_name")
        if not isinstance(tag, str):
            malformed = True
            continue
        try:
            version = Version(tag.removeprefix("v"))
        except InvalidVersion:
            malformed = True
            continue
        if version.is_prerelease or version.is_devrelease or version.local is not None:
            continue
        page = f"{REPOSITORY}/releases/tag/{quote(tag, safe='')}"
        if release.get("html_url") != page:
            malformed = True
            continue
        assets = release.get("assets")
        if not isinstance(assets, list):
            malformed = True
            continue
        platform_name, extensions = target
        for extension in extensions:
            name = f"RasterReady-{version}-{platform_name}.{extension}"
            expected = f"{REPOSITORY}/releases/download/{quote(tag, safe='')}/{name}"
            if any(
                isinstance(a, dict)
                and a.get("name") == name
                and a.get("state") == "uploaded"
                and a.get("browser_download_url") == expected
                for a in assets
            ):
                candidates.append((version, page))
                break
    if candidates:
        newest, page = max(candidates)
        if newest > installed:
            return Update("newer", str(newest), page)
        return Update("unknown" if malformed else "current")
    return Update("unknown" if malformed else "unpublished")


def automatic_due(enabled, last_attempt, now):
    if not enabled:
        return False
    try:
        last = float(last_attempt)
    except (TypeError, ValueError):
        return True
    # A clock correction must not suppress checks indefinitely.
    return not 0 < last <= now or now - last >= WEEK
