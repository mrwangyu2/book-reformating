# EPUB Image Split Reformat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that batch-processes EPUB files by splitting double-page spread images vertically, rotating each half 90° clockwise, and scaling to fill original dimensions.

**Architecture:** Three modules — `image_processor.py` (pure Pillow image ops, no EPUB knowledge), `epub_processor.py` (ebooklib-based EPUB read/write, calls image_processor), `cli.py` (argparse entry point, calls epub_processor).

**Tech Stack:** Python >=3.10, ebooklib, Pillow, pytest, argparse (stdlib)

**Key design decisions:**
- `process_image(bytes)` returns `list[bytes]` — length 2 for processed (left page, right page), length 1 for skipped (too small/corrupt). Caller checks length.
- All images in EPUB are assumed to be double-page spreads. Split every image.
- A fresh EPUB is generated from processed images; only title and author metadata are preserved from the original.

---

### Task 1: Project setup

**Files:**
- Create: `pyproject.toml`
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "epub-reformat"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "ebooklib>=0.18",
    "Pillow>=10.0",
]

[project.scripts]
epub-reformat = "cli:main"

[project.optional-dependencies]
dev = ["pytest>=8.0"]
```

- [ ] **Step 2: Create test package init**

```bash
mkdir -p tests && touch tests/__init__.py
```

- [ ] **Step 3: Install dependencies**

```bash
cd /data/develop/book_reformating && pip install -e ".[dev]"
```

Expected: ebooklib, Pillow, pytest installed successfully.

- [ ] **Step 4: Verify pytest works**

```bash
pytest tests/ -v
```

Expected: exit code 5 ("no tests collected"), not a crash.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/__init__.py
git commit -m "chore: initialize project with pyproject.toml"
```

---

### Task 2: image_processor — split_image

**Files:**
- Create: `image_processor.py`
- Create: `tests/test_image_processor.py`

- [ ] **Step 1: Write failing tests for split_image**

```python
# tests/test_image_processor.py
from PIL import Image
from image_processor import split_image


def test_split_image_even_width():
    """200x100 image: left half red, right half blue. Verify split at midline."""
    img = Image.new("RGB", (200, 100))
    for x in range(200):
        for y in range(100):
            img.putpixel((x, y), (255, 0, 0) if x < 100 else (0, 0, 255))

    left, right = split_image(img)

    assert left.size == (100, 100)
    assert right.size == (100, 100)
    assert left.getpixel((0, 0)) == (255, 0, 0)
    assert left.getpixel((99, 50)) == (255, 0, 0)
    assert right.getpixel((0, 0)) == (0, 0, 255)
    assert right.getpixel((99, 50)) == (0, 0, 255)


def test_split_image_odd_width_left_larger():
    """201x100 image: left half gets the extra pixel per spec."""
    img = Image.new("RGB", (201, 100))
    for x in range(201):
        for y in range(100):
            img.putpixel((x, y), (255, 0, 0) if x < 101 else (0, 0, 255))

    left, right = split_image(img)

    assert left.size == (101, 100)
    assert right.size == (100, 100)
    assert left.getpixel((0, 0)) == (255, 0, 0)
    assert right.getpixel((0, 0)) == (0, 0, 255)
```

- [ ] **Step 2: Run test, verify failure**

```bash
pytest tests/test_image_processor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'image_processor'`

- [ ] **Step 3: Implement split_image**

```python
# image_processor.py
from PIL import Image


def split_image(image: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Split image vertically at the midline.

    Returns (left_half, right_half).
    When width is odd, left side gets the extra pixel.
    """
    w, h = image.size
    mid = (w + 1) // 2
    left = image.crop((0, 0, mid, h))
    right = image.crop((mid, 0, w, h))
    return left, right
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_image_processor.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add image_processor.py tests/test_image_processor.py
git commit -m "feat: add split_image to split images at vertical midline"
```

---

### Task 3: image_processor — rotate_cw

**Files:**
- Modify: `image_processor.py`
- Modify: `tests/test_image_processor.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_image_processor.py, after existing imports
from image_processor import rotate_cw


def test_rotate_cw():
    """Top-left pixel moves to top-right; size swaps dimensions."""
    img = Image.new("RGB", (10, 20))
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((9, 19), (0, 0, 255))

    rotated = rotate_cw(img)

    assert rotated.size == (20, 10)
    assert rotated.getpixel((19, 0)) == (255, 0, 0)
    assert rotated.getpixel((0, 9)) == (0, 0, 255)
```

- [ ] **Step 2: Run test, verify failure**

```bash
pytest tests/test_image_processor.py::test_rotate_cw -v
```

Expected: FAIL — `ImportError: cannot import name 'rotate_cw'`

- [ ] **Step 3: Implement rotate_cw**

```python
# Add to image_processor.py
def rotate_cw(image: Image.Image) -> Image.Image:
    """Rotate image 90 degrees clockwise."""
    return image.rotate(-90, expand=True)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_image_processor.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add image_processor.py tests/test_image_processor.py
git commit -m "feat: add rotate_cw for 90-degree clockwise rotation"
```

---

### Task 4: image_processor — scale_to_fill

**Files:**
- Modify: `image_processor.py`
- Modify: `tests/test_image_processor.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_image_processor.py
from image_processor import scale_to_fill


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
```

- [ ] **Step 2: Run tests, verify failure**

```bash
pytest tests/test_image_processor.py -k "scale_to_fill" -v
```

Expected: FAIL — `ImportError: cannot import name 'scale_to_fill'`

- [ ] **Step 3: Implement scale_to_fill**

```python
# Add to image_processor.py
def scale_to_fill(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Scale proportionally to completely fill target_size, center-crop overflow."""
    tw, th = target_size
    iw, ih = image.size
    scale = max(tw / iw, th / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    scaled = image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return scaled.crop((left, top, left + tw, top + th))
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_image_processor.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add image_processor.py tests/test_image_processor.py
git commit -m "feat: add scale_to_fill for proportional fill with center crop"
```

---

### Task 5: image_processor — process_image pipeline

**Files:**
- Modify: `image_processor.py`
- Modify: `tests/test_image_processor.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_image_processor.py
import io
from image_processor import process_image


def test_process_image_splits_spread_into_two():
    """200x100 JPEG -> two 200x100 JPEG pages."""
    img = Image.new("RGB", (200, 100))
    for x in range(200):
        for y in range(100):
            img.putpixel((x, y), (255, 0, 0) if x < 100 else (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    results = process_image(buf.getvalue())

    assert len(results) == 2
    left_img = Image.open(io.BytesIO(results[0]))
    right_img = Image.open(io.BytesIO(results[1]))
    assert left_img.size == (200, 100)
    assert right_img.size == (200, 100)
    assert left_img.format == "JPEG"
    assert right_img.format == "JPEG"


def test_process_image_preserves_png_rgba():
    """PNG RGBA -> PNG RGBA output."""
    img = Image.new("RGBA", (200, 100), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    results = process_image(buf.getvalue())

    assert len(results) == 2
    left_img = Image.open(io.BytesIO(results[0]))
    assert left_img.format == "PNG"
    assert left_img.mode == "RGBA"


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
```

- [ ] **Step 2: Run tests, verify failure**

```bash
pytest tests/test_image_processor.py -k "process_image" -v
```

Expected: FAIL — `ImportError: cannot import name 'process_image'`

- [ ] **Step 3: Implement process_image**

```python
# Add to top of image_processor.py
import io


# Add to end of image_processor.py
def process_image(image_bytes: bytes) -> list[bytes]:
    """Process a double-page-spread image into page images.

    Returns:
        list of bytes — length 2 (left page, right page) for normal images,
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
    left_half, right_half = split_image(img)

    results = []
    for half in (left_half, right_half):
        rotated = rotate_cw(half)
        filled = scale_to_fill(rotated, (w, h))
        if original_format == "JPEG" and filled.mode == "RGBA":
            filled = filled.convert("RGB")
        buf = io.BytesIO()
        filled.save(buf, format=original_format)
        results.append(buf.getvalue())

    return results
```

- [ ] **Step 4: Run all tests, verify pass**

```bash
pytest tests/test_image_processor.py -v
```

Expected: 11 passed

- [ ] **Step 5: Run python to verify the module imports cleanly**

```bash
python -c "from image_processor import split_image, rotate_cw, scale_to_fill, process_image; print('OK')"
```

Expected: OK

- [ ] **Step 6: Commit**

```bash
git add image_processor.py tests/test_image_processor.py
git commit -m "feat: add process_image pipeline (split + rotate + fill)"
```

---

### Task 6: epub_processor — extract EPUB metadata and images

**Files:**
- Create: `epub_processor.py`
- Create: `tests/test_epub_processor.py`

- [ ] **Step 1: Write helper and failing tests**

```python
# tests/test_epub_processor.py
import io
import os
import tempfile
from PIL import Image
from ebooklib import epub
from epub_processor import extract_epub_data


def _make_test_epub(path, title="Test Book", author="Test Author"):
    """Create a minimal EPUB with two image pages (XHTML wrapping JPEG)."""
    book = epub.EpubBook()
    book.set_identifier("test-001")
    book.set_title(title)
    book.add_author(author)

    for i in range(2):
        color = (255, 0, 0) if i == 0 else (0, 0, 255)
        img = Image.new("RGB", (200, 100), color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        epub_img = epub.EpubImage()
        epub_img.file_name = f"img_{i:03d}.jpg"
        epub_img.media_type = "image/jpeg"
        epub_img.content = img_bytes
        book.add_item(epub_img)

        page = epub.EpubHtml(
            title=f"Page {i + 1}",
            file_name=f"page_{i:03d}.xhtml",
            content=f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page {i + 1}</title></head><body><img src="img_{i:03d}.jpg"/></body></html>'.encode(),
        )
        book.add_item(page)
        book.spine.append(page)

    book.toc = book.spine[:]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(path, book)


def test_extract_epub_data_metadata():
    """Extract title and author."""
    with tempfile.TemporaryDirectory() as tmpdir:
        epub_path = os.path.join(tmpdir, "test.epub")
        _make_test_epub(epub_path, title="My Book", author="Me")

        metadata, images = extract_epub_data(epub_path)

        assert metadata["title"] == "My Book"
        assert metadata["author"] == "Me"


def test_extract_epub_data_images_in_spine_order():
    """Images extracted in spine order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        epub_path = os.path.join(tmpdir, "test.epub")
        _make_test_epub(epub_path)

        metadata, images = extract_epub_data(epub_path)

        assert len(images) == 2
        assert images[0][0] == "img_000.jpg"
        assert images[1][0] == "img_001.jpg"
        assert len(images[0][1]) > 0
        assert len(images[1][1]) > 0


def test_extract_epub_data_missing_metadata():
    """EPUB without author: author defaults to empty string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        epub_path = os.path.join(tmpdir, "noauthor.epub")
        book = epub.EpubBook()
        book.set_identifier("x")
        book.set_title("Only Title")
        book.spine = []
        book.toc = []
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        epub.write_epub(epub_path, book)

        metadata, images = extract_epub_data(epub_path)

        assert metadata["title"] == "Only Title"
        assert metadata["author"] == ""
        assert images == []
```

- [ ] **Step 2: Run tests, verify failure**

```bash
pytest tests/test_epub_processor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'epub_processor'`

- [ ] **Step 3: Implement extract_epub_data**

```python
# epub_processor.py
from xml.etree import ElementTree

from ebooklib import epub


def extract_epub_data(epub_path: str) -> tuple[dict, list[tuple[str, bytes]]]:
    """Extract metadata and spine-ordered images from an EPUB.

    Returns:
        metadata: dict with 'title' and 'author' keys.
        images: list of (file_name, image_bytes) tuples in spine order.
    """
    book = epub.read_epub(epub_path)

    title_vals = book.get_metadata("DC", "title")
    title = title_vals[0][0] if title_vals else ""
    creator_vals = book.get_metadata("DC", "creator")
    author = creator_vals[0][0] if creator_vals else ""

    metadata = {"title": title, "author": author}

    image_items = {}
    for item in book.get_items_of_type(epub.ITEM_IMAGE):
        image_items[item.file_name] = item.get_content()

    images = []
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None:
            continue

        if item.get_type() == epub.ITEM_IMAGE:
            images.append((item.file_name, item.get_content()))
        elif item.get_type() == epub.ITEM_DOCUMENT:
            try:
                content = item.get_content().decode("utf-8")
                root = ElementTree.fromstring(content)
                for img_el in root.iterfind(".//x:img", ns):
                    src = img_el.get("src", "")
                    if src in image_items:
                        images.append((src, image_items[src]))
            except Exception:
                continue

    return metadata, images
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_epub_processor.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add epub_processor.py tests/test_epub_processor.py
git commit -m "feat: add extract_epub_data for metadata and image extraction"
```

---

### Task 7: epub_processor — build_epub and process_epub

**Files:**
- Modify: `epub_processor.py`
- Modify: `tests/test_epub_processor.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_epub_processor.py
from epub_processor import build_epub, process_epub


def test_build_epub_creates_valid_epub():
    """Build an EPUB from processed images and verify it can be re-read."""
    with tempfile.TemporaryDirectory() as tmpdir:
        img1 = Image.new("RGB", (200, 100), (255, 0, 0))
        buf1 = io.BytesIO()
        img1.save(buf1, format="JPEG")
        img2 = Image.new("RGB", (200, 100), (0, 0, 255))
        buf2 = io.BytesIO()
        img2.save(buf2, format="JPEG")

        processed_images = [
            ("page_001.jpg", buf1.getvalue(), "image/jpeg"),
            ("page_002.jpg", buf2.getvalue(), "image/jpeg"),
        ]

        output_path = os.path.join(tmpdir, "out.epub")
        build_epub(
            metadata={"title": "Test", "author": "Me"},
            processed_images=processed_images,
            output_path=output_path,
        )

        book = epub.read_epub(output_path)
        title_vals = book.get_metadata("DC", "title")
        assert title_vals[0][0] == "Test"
        creator_vals = book.get_metadata("DC", "creator")
        assert creator_vals[0][0] == "Me"

        img_items = list(book.get_items_of_type(epub.ITEM_IMAGE))
        assert len(img_items) == 2


def test_process_epub_end_to_end():
    """Full pipeline: read EPUB, process images, write output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.epub")
        _make_test_epub(input_path, title="E2E Book", author="Tester")

        output_path = os.path.join(tmpdir, "output.epub")
        process_epub(input_path, output_path)

        assert os.path.exists(output_path)
        book = epub.read_epub(output_path)
        title_vals = book.get_metadata("DC", "title")
        assert title_vals[0][0] == "E2E Book"

        img_items = list(book.get_items_of_type(epub.ITEM_IMAGE))
        assert len(img_items) == 4


def test_process_epub_skips_corrupt_epub():
    """Corrupt EPUB file raises expected exception."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_path = os.path.join(tmpdir, "bad.epub")
        with open(bad_path, "wb") as f:
            f.write(b"not a zip file")

        output_path = os.path.join(tmpdir, "out.epub")
        import zipfile

        try:
            process_epub(bad_path, output_path)
        except (zipfile.BadZipFile, Exception):
            pass
```

- [ ] **Step 2: Run tests, verify failure**

```bash
pytest tests/test_epub_processor.py -k "build_epub or process_epub" -v
```

Expected: FAIL — `ImportError: cannot import name 'build_epub'`

- [ ] **Step 3: Implement build_epub and process_epub**

```python
# Add to epub_processor.py, after extract_epub_data
import os

from ebooklib import epub as epub_lib

from image_processor import process_image


def build_epub(metadata: dict, processed_images: list[tuple[str, bytes, str]],
               output_path: str) -> None:
    """Build a new EPUB from processed images.

    Args:
        metadata: dict with 'title' and 'author'.
        processed_images: list of (file_name, image_bytes, media_type) in page order.
        output_path: path to write the output EPUB file.
    """
    book = epub_lib.EpubBook()
    book.set_identifier(f"reformat-{os.path.basename(output_path)}")
    book.set_title(metadata.get("title", ""))
    if metadata.get("author"):
        book.add_author(metadata["author"])

    spine = []
    toc = []

    for i, (file_name, img_bytes, media_type) in enumerate(processed_images):
        epub_img = epub_lib.EpubImage()
        epub_img.file_name = file_name
        epub_img.media_type = media_type
        epub_img.content = img_bytes
        book.add_item(epub_img)

        page_content = (
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            "<head>"
            f"<title>Page {i + 1}</title>"
            "<style>"
            "html,body{margin:0;padding:0;width:100%;height:100%;}"
            "img{width:100%;height:100%;object-fit:contain;}"
            "</style>"
            "</head>"
            f'<body><img src="{file_name}"/></body>'
            "</html>"
        )
        page = epub_lib.EpubHtml(
            title=f"Page {i + 1}",
            file_name=f"page_{i:04d}.xhtml",
            content=page_content.encode("utf-8"),
        )
        book.add_item(page)
        spine.append(page)
        toc.append(page)

    book.spine = spine
    book.toc = toc
    book.add_item(epub_lib.EpubNcx())
    book.add_item(epub_lib.EpubNav())

    epub_lib.write_epub(output_path, book)


def process_epub(input_path: str, output_path: str, quality: int = 95) -> None:
    """Read EPUB from input_path, process images, write to output_path."""
    metadata, source_images = extract_epub_data(input_path)

    processed_images = []
    for file_name, img_bytes in source_images:
        ext = os.path.splitext(file_name)[1].lower()
        media_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        media_type = media_map.get(ext, "image/jpeg")

        results = process_image(img_bytes)

        if len(results) == 1:
            processed_images.append((file_name, results[0], media_type))
        else:
            base, ext_part = os.path.splitext(file_name)
            processed_images.append((f"{base}_L{ext_part}", results[0], media_type))
            processed_images.append((f"{base}_R{ext_part}", results[1], media_type))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    build_epub(metadata, processed_images, output_path)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_epub_processor.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add epub_processor.py tests/test_epub_processor.py
git commit -m "feat: add build_epub and process_epub for end-to-end conversion"
```

---

### Task 8: CLI entry point

**Files:**
- Create: `cli.py`

- [ ] **Step 1: Implement CLI module**

```python
# cli.py
import argparse
import glob
import os
import sys

from epub_processor import process_epub


def main(argv=None):
    """Entry point for the epub-reformat CLI."""
    parser = argparse.ArgumentParser(
        prog="epub-reformat",
        description="Split double-page EPUB images into single pages rotated for landscape reading.",
    )
    parser.add_argument(
        "-i", "--input-dir", required=True,
        help="Directory containing .epub files to process.",
    )
    parser.add_argument(
        "-o", "--output-dir", required=True,
        help="Directory to write processed .epub files.",
    )
    parser.add_argument(
        "-q", "--quality", type=int, default=95,
        help="JPEG output quality (1-100, default: 95).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print detailed processing log.",
    )
    args = parser.parse_args(argv)

    input_dir = args.input_dir
    output_dir = args.output_dir

    if not os.path.isdir(input_dir):
        print(f"Error: input directory does not exist: {input_dir}", file=sys.stderr)
        return 1

    epub_files = sorted(glob.glob(os.path.join(input_dir, "*.epub")))
    if not epub_files:
        print(f"No .epub files found in: {input_dir}")
        return 0

    os.makedirs(output_dir, exist_ok=True)

    success_count = 0
    fail_count = 0

    for epub_path in epub_files:
        filename = os.path.basename(epub_path)
        output_path = os.path.join(output_dir, filename)
        try:
            if args.verbose:
                print(f"Processing: {filename}")
            process_epub(epub_path, output_path, quality=args.quality)
            success_count += 1
            if args.verbose:
                print(f"  -> {output_path}")
        except Exception as e:
            fail_count += 1
            print(f"Warning: failed to process '{filename}': {e}", file=sys.stderr)

    if args.verbose:
        print(f"Done: {success_count} succeeded, {fail_count} failed")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify CLI module is importable**

```bash
python -c "from cli import main; print('CLI module OK')"
```

Expected: CLI module OK

- [ ] **Step 3: Test CLI --help**

```bash
python cli.py --help
```

Expected: argparse help text with -i, -o, -q, -v options.

- [ ] **Step 4: Test CLI with missing input directory**

```bash
python cli.py -i /nonexistent -o /tmp
```

Expected: error message to stderr, exit code 1.

- [ ] **Step 5: Test CLI with empty directory**

```bash
mkdir -p /tmp/empty_epub_dir
python cli.py -i /tmp/empty_epub_dir -o /tmp/out; echo "exit: $?"
```

Expected: "No .epub files found" to stdout, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add cli.py
git commit -m "feat: add CLI entry point with argparse"
```

---

### Task 9: Integration test — full pipeline

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import io
import os
import tempfile

from PIL import Image
from ebooklib import epub

from cli import main


def _make_epub(path, title, author, images_config):
    """Create an EPUB with specified images.

    images_config: list of (color_tuple, width, height) for each spread image.
    """
    book = epub.EpubBook()
    book.set_identifier(f"int-{title}")
    book.set_title(title)
    book.add_author(author)

    for i, (color, w, h) in enumerate(images_config):
        img = Image.new("RGB", (w, h), color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        epub_img = epub.EpubImage()
        epub_img.file_name = f"img_{i:03d}.jpg"
        epub_img.media_type = "image/jpeg"
        epub_img.content = buf.getvalue()
        book.add_item(epub_img)

        page = epub.EpubHtml(
            title=f"Page {i + 1}",
            file_name=f"page_{i:03d}.xhtml",
            content=f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page {i + 1}</title></head><body><img src="img_{i:03d}.jpg"/></body></html>'.encode(),
        )
        book.add_item(page)
        book.spine.append(page)

    book.toc = book.spine[:]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(path, book)


def test_full_pipeline_single_epub():
    """CLI processes one EPUB: 1 spread -> 2 pages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir = os.path.join(tmpdir, "input")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(input_dir)

        _make_epub(
            os.path.join(input_dir, "book.epub"),
            title="Pipeline Test",
            author="Test Author",
            images_config=[((255, 0, 0), 200, 100)],
        )

        exit_code = main(["-i", input_dir, "-o", output_dir])

        assert exit_code == 0
        output_epub = os.path.join(output_dir, "book.epub")
        assert os.path.exists(output_epub)

        book = epub.read_epub(output_epub)
        title_vals = book.get_metadata("DC", "title")
        assert title_vals[0][0] == "Pipeline Test"

        img_items = list(book.get_items_of_type(epub.ITEM_IMAGE))
        assert len(img_items) == 2

        for img_item in img_items:
            result = Image.open(io.BytesIO(img_item.get_content()))
            assert result.size == (200, 100)


def test_full_pipeline_two_epubs():
    """CLI processes two EPUBs in one directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir = os.path.join(tmpdir, "input")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(input_dir)

        _make_epub(os.path.join(input_dir, "book1.epub"), "Book 1", "A", [((255, 0, 0), 200, 100)])
        _make_epub(os.path.join(input_dir, "book2.epub"), "Book 2", "B", [((0, 0, 255), 300, 150)])

        exit_code = main(["-i", input_dir, "-o", output_dir, "-v"])

        assert exit_code == 0
        assert os.path.exists(os.path.join(output_dir, "book1.epub"))
        assert os.path.exists(os.path.join(output_dir, "book2.epub"))


def test_full_pipeline_corrupt_epub_not_fatal():
    """A corrupt EPUB is skipped; valid ones still processed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir = os.path.join(tmpdir, "input")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(input_dir)

        _make_epub(os.path.join(input_dir, "good.epub"), "Good", "A", [((255, 0, 0), 200, 100)])
        with open(os.path.join(input_dir, "bad.epub"), "wb") as f:
            f.write(b"corrupt data not a zip")

        exit_code = main(["-i", input_dir, "-o", output_dir])

        assert exit_code == 1
        assert os.path.exists(os.path.join(output_dir, "good.epub"))
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/test_integration.py -v
```

Expected: 3 passed

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ -v
```

Expected: 20 passed (11 image_processor + 6 epub_processor + 3 integration)

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for full CLI pipeline"
```
