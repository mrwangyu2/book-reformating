import io

from PIL import Image
from image_processor import split_image, rotate_cw, scale_to_fill, process_image


def test_split_image_even_width():
    """200x100 image: top half red, bottom half blue. Verify split at midline."""
    img = Image.new("RGB", (200, 100))
    for x in range(200):
        for y in range(100):
            img.putpixel((x, y), (255, 0, 0) if y < 50 else (0, 0, 255))

    top, bottom = split_image(img)

    assert top.size == (200, 50)
    assert bottom.size == (200, 50)
    assert top.getpixel((0, 0)) == (255, 0, 0)
    assert top.getpixel((100, 49)) == (255, 0, 0)
    assert bottom.getpixel((0, 0)) == (0, 0, 255)
    assert bottom.getpixel((100, 49)) == (0, 0, 255)


def test_split_image_odd_width_left_larger():
    """201x100 image: top half gets the extra pixel per spec."""
    img = Image.new("RGB", (200, 101))
    for x in range(200):
        for y in range(101):
            img.putpixel((x, y), (255, 0, 0) if y < 51 else (0, 0, 255))

    top, bottom = split_image(img)

    assert top.size == (200, 51)
    assert bottom.size == (200, 50)
    assert top.getpixel((0, 0)) == (255, 0, 0)
    assert bottom.getpixel((0, 0)) == (0, 0, 255)


def test_rotate_cw():
    """Top-left pixel moves to top-right; size swaps dimensions."""
    img = Image.new("RGB", (10, 20))
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((9, 19), (0, 0, 255))

    rotated = rotate_cw(img)

    assert rotated.size == (20, 10)
    assert rotated.getpixel((19, 0)) == (255, 0, 0)
    assert rotated.getpixel((0, 9)) == (0, 0, 255)



def test_scale_to_fill_exact_match():
    """Image already at target size: no change."""
    img = Image.new("RGB", (100, 50), (128, 128, 128))
    result = scale_to_fill(img, (100, 50))
    assert result.size == (100, 50)


def test_scale_to_fill_wider_crops_sides():
    """200x50 -> 100x50: scale=1.0, crop 50px from each side."""
    img = Image.new("RGB", (200, 50))
    for x in range(200):
        for y in range(50):
            val = (0, 255, 0) if 50 <= x < 150 else (255, 0, 0)
            img.putpixel((x, y), val)
    result = scale_to_fill(img, (100, 50))
    assert result.size == (100, 50)
    assert result.getpixel((0, 0)) == (0, 255, 0)
    assert result.getpixel((50, 25)) == (0, 255, 0)


def test_scale_to_fill_taller_crops_top_bottom():
    """100x200 -> 100x50: scale=1.0, crop 75px from top/bottom."""
    img = Image.new("RGB", (100, 200))
    for x in range(100):
        for y in range(200):
            val = (0, 255, 0) if 75 <= y < 125 else (255, 0, 0)
            img.putpixel((x, y), val)
    result = scale_to_fill(img, (100, 50))
    assert result.size == (100, 50)
    assert result.getpixel((0, 0)) == (0, 255, 0)


def test_scale_to_fill_upscales():
    """50x25 -> 100x100: scale=4 (100/25), upscale then center-crop."""
    img = Image.new("RGB", (50, 25), (0, 255, 0))
    result = scale_to_fill(img, (100, 100))
    assert result.size == (100, 100)
    assert result.getpixel((50, 50)) == (0, 255, 0)


def test_scale_to_fill_tall_to_wide():
    """100x300 tall -> 300x100 wide: scale=3.0 (300/100), scaled to 300x900, vertical center-crop."""
    img = Image.new("RGB", (100, 300))
    for x in range(100):
        for y in range(300):
            val = (0, 255, 0) if 100 <= y < 200 else (255, 0, 0)
            img.putpixel((x, y), val)
    result = scale_to_fill(img, (300, 100))
    assert result.size == (300, 100)
    assert result.getpixel((150, 50)) == (0, 255, 0)
    # Verify edges are not black (no negative crop)
    assert result.getpixel((0, 0)) != (0, 0, 0)
    assert result.getpixel((299, 99)) != (0, 0, 0)


def test_process_image_splits_spread_into_two():
    """200x100 JPEG -> two 200x100 JPEG pages (top/bottom split)."""
    img = Image.new("RGB", (200, 100))
    for x in range(200):
        for y in range(100):
            img.putpixel((x, y), (255, 0, 0) if y < 50 else (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    results = process_image(buf.getvalue())

    assert len(results) == 2
    top_img = Image.open(io.BytesIO(results[0]))
    bot_img = Image.open(io.BytesIO(results[1]))
    assert top_img.size == (200, 100)
    assert bot_img.size == (200, 100)
    assert top_img.format == "JPEG"
    assert bot_img.format == "JPEG"


def test_process_image_preserves_png_rgba():
    """PNG RGBA -> PNG RGBA output."""
    img = Image.new("RGBA", (200, 100), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    results = process_image(buf.getvalue())

    assert len(results) == 2
    top_img = Image.open(io.BytesIO(results[0]))
    assert top_img.format == "PNG"
    assert top_img.mode == "RGBA"


def test_process_image_tiny_skipped():
    """Width 8px (< 10): returned as single page, unmodified."""
    img = Image.new("RGB", (8, 100), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    data = buf.getvalue()

    results = process_image(data)

    assert len(results) == 1
    assert results[0] == data


def test_process_image_corrupt_bytes_skipped():
    """Garbage bytes: returned as single page, unmodified."""
    results = process_image(b"not-a-valid-image")
    assert len(results) == 1
    assert results[0] == b"not-a-valid-image"
