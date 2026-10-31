import copy

import pytest

from rasterready.updates import REPOSITORY, WEEK, automatic_due, select_release, target_platform

MAC = ("macos-arm64", ("dmg",))


def release(version="1.10", target="macos-arm64", extension="dmg", **changes):
    tag = "v" + version
    name = f"RasterReady-{version}-{target}.{extension}"
    value = dict(
        tag_name=tag,
        html_url=f"{REPOSITORY}/releases/tag/{tag}",
        draft=False,
        prerelease=False,
        assets=[
            dict(
                name=name,
                state="uploaded",
                browser_download_url=f"{REPOSITORY}/releases/download/{tag}/{name}",
            )
        ],
    )
    value.update(changes)
    return value


@pytest.mark.parametrize(
    "current,status",
    [("1.9", "newer"), ("1.10", "current"), ("2.0.dev0", "current"), ("bad", "unknown")],
)
def test_version_precedence(current, status):
    result = select_release([release()], current, MAC)
    assert result.status == status
    if status == "newer":
        assert result.version == "1.10"
        assert result.url == f"{REPOSITORY}/releases/tag/v1.10"


@pytest.mark.parametrize(
    "item",
    [
        release(draft=True),
        release(prerelease=True),
        release("2.0rc1"),
        release(target="windows-x64", extension="exe"),
        release(assets=[]),
        release("2.0+local"),
    ],
)
def test_ineligible_releases_never_offer_update(item):
    assert select_release([item], "1.0", MAC).status == "unpublished"


def test_newest_compatible_stable_selected_independent_of_list_order():
    items = [
        release("1.9"),
        release("9.0", target="windows-x64", extension="exe"),
        release("1.11"),
        release("1.10"),
    ]
    assert select_release(items, "1.10", MAC).version == "1.11"
    assert select_release([release("0.1.0")], "0.1.0.dev0", MAC).status == "newer"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda item: item.update(tag_name="nonsense"),
        lambda item: item.update(html_url="https://evil.example/update"),
        lambda item: item["assets"][0].update(browser_download_url="https://evil.example/package"),
        lambda item: item["assets"][0].update(state="new"),
        lambda item: item.update(prerelease=True),
    ],
)
def test_untrusted_or_unfinished_destinations_never_offer_update(mutate):
    item = copy.deepcopy(release())
    mutate(item)
    assert select_release([item], "1.0", MAC).status != "newer"


@pytest.mark.parametrize("payload", [None, {}, [None], [release("not-a-version")]])
def test_malformed_response_cannot_claim_up_to_date(payload):
    assert select_release(payload, "1.0", MAC).status == "unknown"


def test_empty_unsupported_and_linux_package_eligibility():
    assert select_release([], "1.0", MAC).status == "unpublished"
    assert select_release([release()], "1.0", None).status == "unknown"
    linux = target_platform("linux", "x86_64")
    for extension in ("deb", "AppImage"):
        assert (
            select_release([release(target="linux-x64", extension=extension)], "1.0", linux).status
            == "newer"
        )
    assert target_platform("darwin", "x86_64") is None
    assert target_platform("darwin", "arm64") == MAC
    assert target_platform("win32", "AMD64") == ("windows-x64", ("exe",))


def test_scheduling_disablement_bad_settings_clock_change_and_restart():
    now = 10000000
    assert not automatic_due(False, None, now)
    for last in (None, "bad", 0, now + 10):
        assert automatic_due(True, last, now)
    assert not automatic_due(True, now, now)
    assert not automatic_due(True, str(now - WEEK + 1), now)
    assert automatic_due(True, str(now - WEEK), now)
