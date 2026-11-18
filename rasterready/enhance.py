"""Local Photo Workbench adjustments for normalized RGB and RGBA images."""

from dataclasses import dataclass

from PIL import Image, ImageFilter


@dataclass(frozen=True)
class Adjustments:
    noise: int = 0
    sharpness: int = 0
    exposure: float = 0
    warmth: int = 0
    rotation: int = 0
    crop: tuple[int, int] | None = None
    scale: int = 1
    center: tuple[float, float] = (0.5, 0.5)
    zoom: float = 1

    def apply(self, image, *, preview=False, max_pixels=50_000_000):
        if self.rotation:
            image = image.rotate(-90 * self.rotation, expand=True)
        if self.crop or self.zoom > 1:
            width, height = image.size
            x, y = self.crop or image.size
            crop_width = max(1, min(width, height * x // y))
            crop_height = max(1, min(height, width * y // x))
            output_size = (crop_width, crop_height)
            crop_width = max(1, round(crop_width / self.zoom))
            crop_height = max(1, round(crop_height / self.zoom))
            left = round((width - crop_width) * self.center[0])
            top = round((height - crop_height) * self.center[1])
            image = image.crop((left, top, left + crop_width, top + crop_height))
            if self.zoom > 1:
                image = image.resize(output_size, Image.Resampling.LANCZOS)

        if self.noise or self.sharpness or self.exposure or self.warmth:
            alpha = image.getchannel("A") if image.mode == "RGBA" else None
            image = image.convert("RGB")
            if self.noise:
                image = _denoise(image, self.noise, alpha)
            if self.sharpness:
                image = image.filter(ImageFilter.UnsharpMask(1.2, self.sharpness * 2, 0))
            if self.exposure or self.warmth:
                gain = 2**self.exposure
                warmth = 0.3 * self.warmth
                lut = [
                    max(0, min(255, round(value * gain + shift)))
                    for shift in (warmth, 0, -warmth)
                    for value in range(256)
                ]
                image = image.point(lut)
            if alpha is not None:
                image.putalpha(alpha)

        if self.scale != 1 and not preview:
            width, height = (dimension * self.scale for dimension in image.size)
            if width > 20000 or height > 20000 or width * height > max_pixels:
                raise ValueError("Upscaling exceeds the output limit. Choose a smaller scale.")
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        return image


def _denoise(image, strength, alpha):
    # Bound float working memory to one stripe. Transparent neighbors have less
    # influence so colors hidden outside a cutout don't bleed into its edge.
    import numpy as np

    source = np.asarray(image)
    opacity = np.asarray(alpha) if alpha is not None else None
    height, width, _ = source.shape
    output = np.empty_like(source)
    columns = np.arange(width)
    blend = strength / 100
    threshold = 400 + 35 * strength
    stripe = max(1, min(128, 500_000 // width))
    for start in range(0, height, stripe):
        end = min(start + stripe, height)
        rows = np.arange(start, end)
        center = source[start:end].astype(np.float32)
        sums = np.zeros_like(center)
        total = np.zeros(center.shape[:2], dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy = np.clip(rows + dy, 0, height - 1)[:, None]
                xx = np.clip(columns + dx, 0, width - 1)
                neighbor = source[yy, xx].astype(np.float32)
                weight = np.exp(-np.square(neighbor - center).sum(axis=2) / threshold)
                if opacity is not None and (dx or dy):
                    weight *= opacity[yy, xx] / 255
                sums += neighbor * weight[:, :, None]
                total += weight
        output[start:end] = np.rint(center * (1 - blend) + sums / total[:, :, None] * blend)
    return Image.fromarray(output)
