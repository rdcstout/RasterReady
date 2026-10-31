from PIL import Image

from rasterready.core import Result, Size, prepare
from rasterready.presets import PRESETS, Preset


def test_marketplace_and_web_choices_have_unique_keys():
    keys = [p.key for p in PRESETS]
    assert len(keys) == len(set(keys))
    assert {
        "ebay",
        "amazon",
        "etsy",
        "facebook",
        "poshmark",
        "shopify",
        "walmart",
        "mercari",
        "offerup",
        "craigslist",
        "depop",
        "web1024",
        "web1920",
        "custom",
    } <= set(keys)
    for preset in PRESETS:
        if preset.size:
            preset.size.validate()


def test_etsy_flattens_transparency_and_warns_about_small_source(tmp_path):
    source = tmp_path / "transparent.png"
    Image.new("RGBA", (100, 50), (255, 0, 0, 0)).save(source)
    etsy = next(p for p in PRESETS if p.key == "etsy")
    result = prepare(source, tmp_path, etsy.size, flatten=etsy.flatten)
    with Image.open(result.output) as output:
        assert output.mode == "RGB"
        assert output.getpixel((0, 0)) == (255, 255, 255)
    assert any("2000" in note for note in etsy.review(result))


def test_walmart_suggests_actual_square_without_cropping(tmp_path):
    source = tmp_path / "product.png"
    Image.new("RGB", (80, 40), "red").save(source)
    walmart = next(p for p in PRESETS if p.key == "walmart")
    result = prepare(source, tmp_path, walmart.size, flatten=walmart.flatten)
    with Image.open(result.output) as output:
        assert output.size == (2200, 2200)
        assert output.mode == "RGB"
        assert output.getpixel((0, 0)) == (255, 255, 255)
        assert output.getpixel((1100, 1100)) == (255, 0, 0)


def test_general_suggestions_do_not_claim_official_sizes():
    for key in ("facebook", "mercari", "offerup", "craigslist", "depop"):
        preset = next(p for p in PRESETS if p.key == key)
        assert "not verified" in preset.guidance


def test_upload_size_limit_is_inclusive_unless_preset_expresses_strict_limit(tmp_path):
    output = tmp_path / "result.png"
    output.write_bytes(b"x" * 64)
    preset = Preset("test", "Test", Size(10), max_bytes=64)
    result = Result(output, 10, 10, ())
    assert not preset.review(result)
    output.write_bytes(b"x" * 65)
    assert any("exceeds" in note for note in preset.review(result))
    assert next(p for p in PRESETS if p.key == "shopify").max_bytes == 19_999_999
    assert next(p for p in PRESETS if p.key == "walmart").max_bytes == 5_000_000
