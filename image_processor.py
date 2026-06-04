import io

from PIL import Image
from PIL import ImageChops


def split_image(image: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Split image horizontally at the midline.

    Returns (top_half, bottom_half).
    When height is odd, top half gets the extra pixel.
    """
    w, h = image.size
    mid = (h + 1) // 2
    top = image.crop((0, 0, w, mid))
    bottom = image.crop((0, mid, w, h))
    return top, bottom


def rotate_cw(image: Image.Image) -> Image.Image:
    """Rotate image 90 degrees clockwise."""
    return image.rotate(-90, expand=True)


def scale_to_fill(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Scale proportionally to completely fill target_size, center-crop overflow."""
    tw, th = target_size
    iw, ih = image.size
    scale = max(tw / iw, th / ih)
    new_w = round(iw * scale)
    new_h = round(ih * scale)
    scaled = image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return scaled.crop((left, top, left + tw, top + th))


def trim_white_border(image: Image.Image, threshold: int = 240) -> Image.Image:
    """Trim white/near-white borders from an image.

    Pixels with all RGB channels >= threshold are considered border.
    Returns the cropped image, or the original if no border is found.
    """
    if image.mode == "RGBA":
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.split()[3])
        rgb = bg
    else:
        rgb = image.convert("RGB")

    white = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, white)
    gray = diff.convert("L")

    # Pixels where diff > (255 - threshold) are non-white content
    limit = 255 - threshold
    mask = gray.point(lambda p: 255 if p > limit else 0)

    bbox = mask.getbbox()
    if bbox is None:
        return image
    return image.crop(bbox)


def process_image(image_bytes: bytes, quality: int = 95) -> list[bytes]:
    """Process a double-page-spread image into page images.

    Returns:
        list of bytes -- length 2 (top page, bottom page) for normal images,
        length 1 for skipped images (too small, corrupt, or unsupported).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return [image_bytes]

    w, h = img.size
    if min(w, h) < 10:
        return [image_bytes]

    original_format = img.format or "JPEG"
    top_half, bottom_half = split_image(img)

    results = []
    for half in (top_half, bottom_half):
        rotated = rotate_cw(half)
        trimmed = trim_white_border(rotated)
        filled = scale_to_fill(trimmed, (w, h))
        if original_format == "JPEG" and filled.mode == "RGBA":
            filled = filled.convert("RGB")
        buf = io.BytesIO()
        save_kwargs = {"format": original_format}
        if original_format == "JPEG":
            save_kwargs["quality"] = quality
        filled.save(buf, **save_kwargs)
        results.append(buf.getvalue())

    return results
