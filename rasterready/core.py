"""Image conversion with fresh pixels and exclusive output creation."""

import re
import stat
import unicodedata
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pillow_heif
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

pillow_heif.register_heif_opener()
MAX_INPUT_PIXELS = 100_000_000
Image.MAX_IMAGE_PIXELS = MAX_INPUT_PIXELS
MAX_PIXELS = 50_000_000
MAX_SOURCE_BYTES = 1024 * 1024 * 1024
SONY_RAW_EXTENSIONS = {".arw", ".sr2", ".srf"}
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"{prefix}{digit}" for prefix in ("COM", "LPT") for digit in "123456789¹²³"),
}


def _name_bytes(name: str) -> int:
    # Leave room on filesystems that count UTF-8 bytes, including decomposed accents.
    return max(len(unicodedata.normalize(form, name).encode("utf-8")) for form in ("NFC", "NFD"))


def _reserved(name: str) -> bool:
    return name.split(".")[0].rstrip(" ").upper() in _RESERVED


def _output_stem(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\ud800-\udfff]', "_", name).strip(" .") or "image"
    if _reserved(name):
        name = "image_" + name
    name = name[:120]
    while _name_bytes(name) > 180:
        name = name[:-1]
    return name.rstrip(" .") or "image"


class PreparationError(ValueError):
    """A problem the user can act on."""


@dataclass(frozen=True)
class Size:
    width: int
    height: int | None = None
    mode: str = "fit"

    def validate(self):
        if self.mode not in {"fit", "crop", "pad"}:
            raise PreparationError("Choose fit, crop or pad.")
        if not 1 <= self.width <= 20000 or (
            self.height is not None and not 1 <= self.height <= 20000
        ):
            raise PreparationError("Dimensions must be between 1 and 20,000 pixels.")
        if self.mode != "fit" and self.height is None:
            raise PreparationError("Crop and pad require both dimensions.")
        if self.height and self.width * self.height > MAX_PIXELS:
            raise PreparationError("The output exceeds the 50 megapixel limit.")


@dataclass(frozen=True)
class Result:
    output: Path
    width: int
    height: int
    notes: tuple[str, ...]


def validate_project(name: str) -> str:
    name = name.strip()
    if not name or name in {".", ".."} or len(name) > 100:
        raise PreparationError("Enter a project name of 1–100 characters.")
    if re.search(r'[<>:"/\\|?*\x00-\x1f\ud800-\udfff]', name) or name.endswith((".", " ")):
        raise PreparationError(
            "Use a project name without slashes, control characters or punctuation reserved by Windows."
        )
    if _name_bytes(name) > 200:
        raise PreparationError("That project name is too long. Shorten it and try again.")
    if _reserved(name):
        raise PreparationError("That project name is reserved by Windows.")
    return name


def project_folder(downloads: Path, name: str) -> Path:
    name = validate_project(name)
    downloads = downloads.expanduser().resolve(strict=True)
    if not downloads.is_dir():
        raise PreparationError("The Downloads location is not a folder.")
    output = downloads / name
    if output.is_symlink():
        raise PreparationError("The project folder is a shortcut. Choose another project name.")
    output.mkdir(exist_ok=True)
    if not output.is_dir():
        raise PreparationError("A file already has that project name.")
    return output


def _resize(image: Image.Image, size: Size, enlarge: bool) -> Image.Image:
    if size.height is None:
        width = size.width if enlarge else min(image.width, size.width)
        height = max(1, round(image.height * width / image.width))
        if width * height > MAX_PIXELS or height > 20000:
            raise PreparationError("The resized image would be too tall. Choose a bounding box.")
        return image.resize((width, height), Image.Resampling.LANCZOS)
    bounds = (size.width, size.height)
    if size.mode == "crop":
        if not enlarge and (image.width < size.width or image.height < size.height):
            raise PreparationError(
                "This image is too small for that crop. Enable enlargement or choose a smaller size."
            )
        return ImageOps.fit(image, bounds, Image.Resampling.LANCZOS)
    ratio = min(size.width / image.width, size.height / image.height)
    if not enlarge:
        ratio = min(1, ratio)
    fitted = image.resize(
        (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
        Image.Resampling.LANCZOS,
    )
    if size.mode == "fit":
        return fitted
    canvas = Image.new("RGBA", bounds, (255, 255, 255, 255))
    canvas.alpha_composite(
        fitted.convert("RGBA"),
        ((size.width - fitted.width) // 2, (size.height - fitted.height) // 2),
    )
    return canvas


def _web_grayscale(image: Image.Image) -> Image.Image:
    if image.mode in {"I", "F"}:
        raise PreparationError(
            "This 32-bit image needs tone mapping. Export an 8-bit or 16-bit image first."
        )
    if image.mode not in {"I;16", "I;16L", "I;16B", "I;16N"}:
        return image
    # Pillow's direct 16-bit -> RGB conversion clips values above 255.
    # Map the complete unsigned 16-bit range before color conversion.
    gray = image.convert("I").point(lambda value: value / 257 + 0.5).convert("L")
    gray.info = image.info.copy()
    if "transparency" in image.info:
        import numpy as np

        # Compare the original sample, not the rounded 8-bit shade: distinct
        # 16-bit values may map to the same gray while only one is transparent.
        opacity = (np.asarray(image) != image.info["transparency"]).astype(np.uint8) * 255
        gray.putalpha(Image.fromarray(opacity))
        gray.info.pop("transparency", None)
    return gray


def _open_source(source: Path, notes: list[str]) -> Image.Image:
    if source.suffix.lower() not in SONY_RAW_EXTENSIONS:
        return Image.open(source)
    # Lazy import keeps normal web-image startup free of NumPy/LibRaw work.
    import rawpy

    try:
        with rawpy.RawPy() as raw:
            # Read dimensions before unpacking the sensor data.
            raw.open_file(str(source))
            sizes = raw.sizes
            if sizes.raw_width < 1 or sizes.raw_height < 1:
                raise PreparationError("The Sony RAW file has invalid image dimensions.")
            if sizes.raw_width * sizes.raw_height > MAX_INPUT_PIXELS:
                raise PreparationError("This RAW image exceeds the 100 megapixel input limit.")
            raw.unpack()
            # Real sensor development, not extract_thumb(). LibRaw applies the
            # camera's orientation by default. Output uses sRGB primaries/gamma.
            pixels = raw.postprocess(
                use_camera_wb=True,
                use_auto_wb=False,
                output_color=rawpy.ColorSpace.sRGB,
                output_bps=8,
                gamma=(2.4, 12.92),
            )
            image = Image.fromarray(pixels)
        notes.append(
            "RAW developed with camera white balance; in-camera picture styles are not applied."
        )
        return image
    except rawpy.LibRawFileUnsupportedError as exc:
        raise PreparationError(
            "This Sony RAW camera or recording mode is not supported by the bundled decoder."
        ) from exc
    except rawpy.LibRawError as exc:
        raise PreparationError(
            "The Sony RAW file could not be decoded. It may be damaged or incomplete."
        ) from exc


def prepare(
    source: Path, destination: Path, size: Size, enlarge: bool = False, flatten: bool = False
) -> Result:
    size.validate()
    source = Path(source)
    notes = []
    try:
        source_info = source.stat()
        if not stat.S_ISREG(source_info.st_mode):
            raise PreparationError("Choose a regular image file, not a folder or device.")
        if source_info.st_size > MAX_SOURCE_BYTES:
            raise PreparationError("This file is too large. The input limit is 1 GiB per image.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with _open_source(source, notes) as original:
                if original.width * original.height > MAX_INPUT_PIXELS:
                    raise PreparationError("This image exceeds the 100 megapixel input limit.")
                # Detect a second frame without scanning every GIF/TIFF page.
                try:
                    original.seek(1)
                except EOFError:
                    pass
                else:
                    notes.append("Only the first frame/page was exported.")
                original.seek(0)
                image = _web_grayscale(ImageOps.exif_transpose(original))
                # LAB's A band is color, not alpha. Indexed/RGB PNG transparency
                # must be expanded before LittleCMS can accept the pixel mode.
                alpha = (
                    image.mode in {"RGBA", "RGBa", "LA", "La", "PA"} or "transparency" in image.info
                )
                mode = "RGBA" if alpha else "RGB"
                profile = image.info.get("icc_profile")
                if profile:
                    try:
                        if image.mode in {"P", "PA", "RGBa", "La"} or "transparency" in image.info:
                            image = image.convert("LA" if image.mode == "La" else mode)
                        opacity = image.getchannel("A") if alpha else None
                        if alpha:
                            image = image.convert("L" if image.mode == "LA" else "RGB")
                        image = ImageCms.profileToProfile(
                            image,
                            ImageCms.ImageCmsProfile(BytesIO(profile)),
                            ImageCms.createProfile("sRGB"),
                            outputMode="RGB",
                        )
                        if opacity is not None:
                            image.putalpha(opacity)
                    except (ImageCms.PyCMSError, OSError, ValueError) as exc:
                        raise PreparationError(
                            "The embedded color profile could not be converted safely."
                        ) from exc
                elif image.mode == "CMYK":
                    notes.append("No CMYK color profile; colors were approximated.")
                image = _resize(image.convert(mode), size, enlarge)
                if flatten:
                    background = Image.new("RGBA", image.size, "white")
                    background.alpha_composite(image.convert("RGBA"))
                    image = background.convert("RGB")
                # A fresh pixel buffer prevents EXIF, ICC, comments and PNG text from being copied.
                clean = Image.frombytes(image.mode, image.size, image.tobytes())
        stem = _output_stem(source.stem)
        for number in range(10000):
            suffix = f" ({number + 1})" if number else ""
            output = destination / f"{stem}{suffix}.png"
            try:
                handle = output.open("xb")
            except FileExistsError:
                continue
            try:
                with handle:
                    clean.save(handle, format="PNG", optimize=True)
            except BaseException:
                output.unlink(missing_ok=True)
                raise
            return Result(output, clean.width, clean.height, tuple(notes))
        raise PreparationError("Too many files share that name. Choose another project.")
    except PreparationError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise PreparationError("This image exceeds the image safety limit.") from exc
    except UnidentifiedImageError as exc:
        raise PreparationError(
            "Unsupported or damaged image. Try JPEG, PNG, HEIC, AVIF, WebP, TIFF or BMP."
        ) from exc
    except (OSError, ValueError) as exc:
        raise PreparationError(f"Could not prepare this image: {exc}") from exc
