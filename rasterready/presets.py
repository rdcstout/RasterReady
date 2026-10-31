"""Sizing choices and source-backed guidance, checked 2026-10-30.

Pixel dimensions chosen by RasterReady are identified as suggestions where a
platform does not publish an applicable listing-photo size in the cited guide.
"""

from dataclasses import dataclass

from .core import Result, Size


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    size: Size | None
    guidance: str = (
        "Keeps proportions and transparency. Smaller images are not enlarged unless enabled."
    )
    source: str = ""
    flatten: bool = False
    min_short: int = 0
    min_long: int = 0
    max_bytes: int = 0

    def review(self, result: Result) -> tuple[str, ...]:
        notes = list(result.notes)
        if min(result.width, result.height) < self.min_short:
            notes.append(f"Below the platform's {self.min_short}-pixel short-side guidance.")
        if max(result.width, result.height) < self.min_long:
            notes.append(f"Below the platform's {self.min_long}-pixel long-side guidance.")
        if self.max_bytes and result.output.stat().st_size > self.max_bytes:
            notes.append(
                "PNG exceeds this preset's upload-size guidance. Choose a smaller custom size."
            )
        return tuple(notes)


_GENERAL = "RasterReady's general-purpose size suggestion; a listing pixel requirement and PNG acceptance were not verified. Check the platform uploader."
PRESETS = (
    Preset("web1024", "Web • 1024 pixels wide", Size(1024)),
    Preset("web1280", "Web • 1280 pixels wide", Size(1280)),
    Preset("web1920", "Web • 1920 pixels wide", Size(1920)),
    Preset("web2560", "Web • 2560 pixels wide", Size(2560)),
    Preset("square1600", "Square • fit within 1600 × 1600", Size(1600, 1600)),
    Preset(
        "product2000",
        "Product • 2000 × 2000, white padding",
        Size(2000, 2000, "pad"),
        "Fits the entire image on a white square without cropping. Does not remove an existing background.",
        flatten=True,
    ),
    Preset("landscape", "Landscape • fit within 1920 × 1080", Size(1920, 1080)),
    Preset("portrait", "Portrait • fit within 1500 × 2000", Size(1500, 2000)),
    Preset(
        "ebay",
        "eBay • fit within 1600 × 1600",
        Size(1600, 1600),
        "eBay recommends about 1600 × 1600. No added borders or cropping. Check photo content and listing rules.",
        "https://www.ebay.com/help/selling/listings/pictures-videos/picture-requirements?id=4148",
        min_short=500,
        max_bytes=12_000_000,
    ),
    Preset(
        "amazon",
        "Amazon • fit within 2000 × 2000",
        Size(2000, 2000),
        "PNG is accepted; Amazon prefers JPEG and over 1000 pixels on the longest side for zoom. Transparency becomes white; existing backgrounds remain. Main-image/content rules still apply.",
        "https://sellercentral.amazon.com/help/hub/reference/external/G1881",
        flatten=True,
        min_long=1001,
    ),
    Preset(
        "etsy",
        "Etsy • fit within 3000 × 3000",
        Size(3000, 3000),
        "Etsy recommends at least 2000 pixels in both dimensions. Transparency becomes white. Uploads over 1 MB may be slow or fail; this is not a stated hard limit.",
        "https://help.etsy.com/hc/en-us/articles/115015663347-Requirements-and-Best-Practices-for-Images-in-Your-Etsy-Shop",
        flatten=True,
        min_short=2000,
    ),
    Preset(
        "facebook",
        "Facebook Marketplace • general 1600 fit",
        Size(1600, 1600),
        _GENERAL,
        "https://www.facebook.com/help/561376580709359",
    ),
    Preset(
        "poshmark",
        "Poshmark • 1500 × 2000 portrait padding",
        Size(1500, 2000, "pad"),
        "Poshmark uses a 3:4 portrait layout. 1500 × 2000 is RasterReady's suggested size. White padding preserves the entire image. PNG acceptance was not verified.",
        "https://blog.poshmark.com/2026/03/25/your-guide-to-portrait-photos/",
        flatten=True,
    ),
    Preset(
        "shopify",
        "Shopify • fit within 2048 × 2048",
        Size(2048, 2048),
        "Shopify recommends 2048 × 2048; images must be under 20 MB and no more than 25 megapixels. This fit preserves the entire image.",
        "https://help.shopify.com/en/manual/products/product-media/product-media-types",
        max_bytes=19_999_999,  # Shopify specifies under 20 MB.,
    ),
    Preset(
        "walmart",
        "Walmart US • 2200 × 2200 white padding",
        Size(2200, 2200, "pad"),
        "Walmart specifies a 2200-pixel square, RGB, white background and at most 5 MB. Padding does not remove an existing background or guarantee product framing.",
        "https://marketplacelearn.walmart.com/guides/Item%20setup/Item%20content,%20imagery,%20and%20media/Product-detail-page:-Image-guidelines-&-requirements",
        flatten=True,
        max_bytes=5_000_000,
    ),
    Preset(
        "mercari",
        "Mercari • general 1600 fit",
        Size(1600, 1600),
        _GENERAL,
        "https://www.mercari.com/us/help_center/topics/listing/guides/creating-a-listing/",
    ),
    Preset(
        "offerup",
        "OfferUp • general 1600 fit",
        Size(1600, 1600),
        _GENERAL,
        "https://help.offerup.com/hc/en-us/articles/360031987592-Post-an-item-to-sell",
    ),
    Preset(
        "craigslist",
        "Craigslist • general 1600 fit",
        Size(1600, 1600),
        _GENERAL,
        "https://www.craigslist.org/about/help/posting/features/images",
    ),
    Preset(
        "depop",
        "Depop • general 1600 fit",
        Size(1600, 1600),
        _GENERAL,
        "https://depophelp.zendesk.com/hc/en-gb/articles/360032716413-How-to-list-an-item",
    ),
    Preset(
        "custom",
        "Custom",
        None,
        "Fit keeps the whole image. Crop trims the center to fill the frame. White padding adds a canvas. Height zero keeps proportions.",
    ),
)
