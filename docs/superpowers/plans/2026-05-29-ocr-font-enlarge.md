# OCR Font Enlargement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OCR-based font enlargement mode to the EPUB reformatting CLI using PaddleOCR.

**Architecture:** New `ocr_processor.py` module handles the OCR pipeline (detect → convert → erase → render). `cli.py` and `epub_processor.py` gain a `--mode` parameter to route between the existing split algorithm and the new OCR algorithm.

**Tech Stack:** PaddleOCR, PIL/Pillow, zhconv

---

### Task 1: Install system dependencies and update pyproject.toml

**Files:**
- Modify: `pyproject.toml`
- Shell: install Chinese font

- [ ] **Step 1: Install Chinese font**

```bash
sudo apt-get install -y fonts-wqy-zenhei
```

Verify: `fc-list :lang=zh | head -3` should show WQY Zen Hei fonts.

- [ ] **Step 2: Update pyproject.toml dependencies**

Edit `pyproject.toml` — add `paddlepaddle`, `paddleocr`, and `zhconv` to the `dependencies` list:

```toml
[project]
name = "epub-reformat"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "ebooklib>=0.18",
    "Pillow>=10.0",
    "paddlepaddle>=3.0.0",
    "paddleocr>=2.9.0",
    "zhconv>=1.4.0",
]
```

- [ ] **Step 3: Install new dependencies in venv**

```bash
source venv/bin/activate && pip install paddlepaddle paddleocr zhconv
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add paddleocr, zhconv dependencies for OCR mode"
```

---

### Task 2: Create ocr_processor.py — font finding and skeleton

**Files:**
- Create: `ocr_processor.py`

- [ ] **Step 1: Write ocr_processor.py skeleton**

```python
"""OCR-based text enlargement for comic page images."""
import io
import os

from PIL import Image, ImageDraw, ImageFont


def _find_chinese_font() -> str:
    """Find a Chinese-capable TrueType font on the system.

    Returns path to the font file, or raises FileNotFoundError.
    """
    search_paths = [
        "/usr/share/fonts",
        os.path.expanduser("~/.fonts"),
        "/usr/local/share/fonts",
    ]
    candidates = []
    for root in search_paths:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                lower = fn.lower()
                if lower.endswith((".ttf", ".ttc", ".otf")):
                    candidates.append(os.path.join(dirpath, fn))

    # Prefer CJK / Chinese fonts
    cjk_keywords = ["wqy", "wenquan", "noto", "cjk", "hans", "chinese",
                    "simhei", "simsun", "songti", "heiti", "ming", "kai"]
    for kw in cjk_keywords:
        for path in candidates:
            if kw in os.path.basename(path).lower():
                return path

    # Fallback: try any candidate that supports Chinese glyphs
    for path in candidates:
        try:
            font = ImageFont.truetype(path, 20)
            if font.getmask("中文"):
                return path
        except Exception:
            continue

    raise FileNotFoundError(
        "No Chinese font found. Install a Chinese font package, e.g.: "
        "sudo apt-get install fonts-wqy-zenhei"
    )


def process_image_ocr(image_bytes: bytes, font_scale: float = 1.5,
                      quality: int = 95) -> list[bytes]:
    """Placeholder — returns original image for now."""
    return [image_bytes]
```

- [ ] **Step 2: Verify it imports without error**

```bash
source venv/bin/activate && python3 -c "from ocr_processor import process_image_ocr, _find_chinese_font; print(_find_chinese_font())"
```

Expected: prints a font path like `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`

- [ ] **Step 3: Commit**

```bash
git add ocr_processor.py
git commit -m "feat: add ocr_processor skeleton with font finding"
```

---

### Task 3: Implement PaddleOCR text detection

**Files:**
- Modify: `ocr_processor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ocr_processor.py`:

```python
import io
from PIL import Image, ImageDraw, ImageFont
from ocr_processor import _detect_text, _find_chinese_font


def _make_text_image(text, font_size, image_size=(400, 200)):
    """Create a white image with black Chinese text."""
    img = Image.new("RGB", image_size, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_path = _find_chinese_font()
    font = ImageFont.truetype(font_path, font_size)
    draw.text((10, 10), text, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_detect_text_finds_chinese():
    img_bytes = _make_text_image("你好世界", font_size=30)
    results = _detect_text(img_bytes)
    assert len(results) > 0
    texts = [r[0] for r in results]
    assert any("你好" in t or "世界" in t for t in texts)


def test_detect_text_empty_image():
    img = Image.new("RGB", (200, 100), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    results = _detect_text(buf.getvalue())
    assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py -v
```

Expected: FAIL — `_detect_text` not defined.

- [ ] **Step 3: Implement `_detect_text`**

Add to `ocr_processor.py` (after the font function, before `process_image_ocr`):

```python
from paddleocr import PaddleOCR

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(lang="ch")
    return _ocr


def _detect_text(image_bytes: bytes) -> list[tuple[str, tuple, float]]:
    """Run PaddleOCR on an image.

    Returns:
        list of (text, bbox, confidence) tuples.
        bbox is (x1, y1, x2, y2) in pixel coordinates.
    """
    img = Image.open(io.BytesIO(image_bytes))
    if min(img.size) < 10:
        return []

    ocr = _get_ocr()
    raw = ocr.ocr(image_bytes, cls=False)

    results = []
    if raw and raw[0]:
        for item in raw[0]:
            bbox_points = item[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            text = item[1][0]
            confidence = item[1][1]
            xs = [p[0] for p in bbox_points]
            ys = [p[1] for p in bbox_points]
            bbox = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
            results.append((text, bbox, confidence))
    return results
```

- [ ] **Step 4: Run test to verify it passes**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py::test_detect_text_finds_chinese tests/test_ocr_processor.py::test_detect_text_empty_image -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ocr_processor.py tests/test_ocr_processor.py
git commit -m "feat: add PaddleOCR text detection with tests"
```

---

### Task 4: Implement zhconv traditional-to-simplified conversion

**Files:**
- Modify: `ocr_processor.py`
- Modify: `tests/test_ocr_processor.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ocr_processor.py`:

```python
from ocr_processor import _convert_to_simplified


def test_convert_traditional_to_simplified():
    results = [
        ("軟體工程師", (10, 10, 100, 30), 0.9),
        ("你好世界", (10, 50, 100, 70), 0.95),
    ]
    converted = _convert_to_simplified(results)
    assert converted[0][0] == "软件工程师"
    assert converted[1][0] == "你好世界"


def test_convert_already_simplified_is_noop():
    results = [("简体中文", (10, 10, 100, 30), 0.9)]
    converted = _convert_to_simplified(results)
    assert converted[0][0] == "简体中文"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py::test_convert_traditional_to_simplified -v
```

Expected: FAIL

- [ ] **Step 3: Implement `_convert_to_simplified`**

Add to `ocr_processor.py`:

```python
import zhconv


def _convert_to_simplified(
    detections: list[tuple[str, tuple, float]]
) -> list[tuple[str, tuple, float]]:
    """Convert traditional Chinese text to simplified Chinese."""
    result = []
    for text, bbox, conf in detections:
        simplified = zhconv.convert(text, "zh-cn")
        result.append((simplified, bbox, conf))
    return result
```

- [ ] **Step 4: Run both conversion tests**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py::test_convert_traditional_to_simplified tests/test_ocr_processor.py::test_convert_already_simplified_is_noop -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ocr_processor.py tests/test_ocr_processor.py
git commit -m "feat: add zhconv traditional-to-simplified conversion"
```

---

### Task 5: Implement text erasure

**Files:**
- Modify: `ocr_processor.py`
- Modify: `tests/test_ocr_processor.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ocr_processor.py`:

```python
from ocr_processor import _erase_text


def test_erase_text_fills_bbox_region():
    img = Image.new("RGB", (200, 100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((50, 20, 150, 40), fill=(0, 0, 0))
    draw.text((55, 22), "test", fill=(255, 255, 255))

    bboxes = [(50, 20, 150, 40)]
    result = _erase_text(img, bboxes)

    # After erasure, bbox center should no longer be pure black
    center_pixel = result.getpixel((100, 30))
    assert center_pixel != (0, 0, 0)
    # Should be close to white (surrounding pixel color)
    assert center_pixel[0] > 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py::test_erase_text_fills_bbox_region -v
```

Expected: FAIL

- [ ] **Step 3: Implement `_erase_text`**

Add to `ocr_processor.py`:

```python
def _erase_text(image: Image.Image,
                bboxes: list[tuple[int, int, int, int]]) -> Image.Image:
    """Erase text by filling each bbox with surrounding pixel color.

    Returns a new image (the original is not modified).
    """
    img = image.copy()
    for (x1, y1, x2, y2) in bboxes:
        # Expand by 2px to get surrounding pixels
        ex1 = max(0, x1 - 2)
        ey1 = max(0, y1 - 2)
        ex2 = min(img.width, x2 + 2)
        ey2 = min(img.height, y2 + 2)

        # Sample pixels from the border region
        samples = []
        for x in range(ex1, ex2):
            if 0 <= x < img.width:
                if ey1 >= 0:
                    samples.append(img.getpixel((x, ey1)))
                if ey2 < img.height:
                    samples.append(img.getpixel((x, ey2 - 1)))
        for y in range(ey1, ey2):
            if 0 <= y < img.height:
                if ex1 >= 0:
                    samples.append(img.getpixel((ex1, y)))
                if ex2 < img.width:
                    samples.append(img.getpixel((ex2 - 1, y)))

        if not samples:
            fill_color = (255, 255, 255)
        else:
            n = len(samples)
            r = sum(s[0] for s in samples) // n
            g = sum(s[1] for s in samples) // n
            b = sum(s[2] for s in samples) // n
            fill_color = (r, g, b)

        # Fill bbox with 1px margin
        fill_x1 = max(0, x1 - 1)
        fill_y1 = max(0, y1 - 1)
        fill_x2 = min(img.width, x2 + 1)
        fill_y2 = min(img.height, y2 + 1)
        for px in range(fill_x1, fill_x2):
            for py in range(fill_y1, fill_y2):
                img.putpixel((px, py), fill_color)
    return img
```

- [ ] **Step 4: Run test to verify it passes**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py::test_erase_text_fills_bbox_region -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ocr_processor.py tests/test_ocr_processor.py
git commit -m "feat: add text region erasure with surrounding pixel fill"
```

---

### Task 6: Implement text re-rendering with larger font

**Files:**
- Modify: `ocr_processor.py`
- Modify: `tests/test_ocr_processor.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ocr_processor.py`:

```python
from ocr_processor import _render_text


def test_render_text_larger_than_original():
    img = Image.new("RGB", (400, 200), (255, 255, 255))
    font_path = _find_chinese_font()
    detections = [("你好", (10, 10, 60, 40), 0.9)]

    result = _render_text(img, detections, font_path, font_scale=2.0)

    # The rendered image should have dark pixels in the text region
    # (we can't easily verify exact font size, but we verify it didn't crash
    #  and that pixels changed in the expected region)
    assert result.size == img.size
    # Check that some non-white pixels exist in the text area
    text_region = result.crop((10, 10, 120, 80))
    pixels = list(text_region.getdata())
    has_dark = any(p[0] < 200 for p in pixels)
    assert has_dark, "Rendered text should have dark pixels"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py::test_render_text_larger_than_original -v
```

Expected: FAIL

- [ ] **Step 3: Implement `_render_text`**

Add to `ocr_processor.py`:

```python
def _render_text(image: Image.Image,
                 detections: list[tuple[str, tuple, float]],
                 font_path: str,
                 font_scale: float) -> Image.Image:
    """Render detected text at a larger font size onto the image.

    Returns a new image.
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)

    for text, (x1, y1, x2, y2), _confidence in detections:
        bbox_h = y2 - y1
        new_size = max(6, round(bbox_h * font_scale))
        try:
            font = ImageFont.truetype(font_path, new_size)
        except Exception:
            continue

        # Determine text color from original image pixels inside bbox
        color_samples = []
        for px in range(max(0, x1), min(image.width, x2), 3):
            for py in range(max(0, y1), min(image.height, y2), 3):
                color_samples.append(image.getpixel((px, py)))
        if color_samples:
            # Use the darkest sampled color (text is typically dark)
            color_samples.sort(key=lambda c: sum(c[:3]))
            text_color = color_samples[0]
        else:
            text_color = (0, 0, 0)

        # Calculate position: center text in original bbox, allow overflow
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
        except Exception:
            continue

        # Center in bbox
        tx = x1 + (x2 - x1 - text_w) // 2
        ty = y1 + (y2 - y1 - text_h) // 2

        # Clamp to image bounds
        tx = max(0, tx)
        ty = max(0, ty)

        draw.text((tx, ty), text, fill=text_color, font=font)

    return img
```

- [ ] **Step 4: Run test to verify it passes**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py::test_render_text_larger_than_original -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ocr_processor.py tests/test_ocr_processor.py
git commit -m "feat: add text re-rendering with scaled font size"
```

---

### Task 7: Wire up process_image_ocr entry point

**Files:**
- Modify: `ocr_processor.py`
- Modify: `tests/test_ocr_processor.py`

- [ ] **Step 1: Write the failing integration test for process_image_ocr**

Add to `tests/test_ocr_processor.py`:

```python
from ocr_processor import process_image_ocr


def test_process_image_ocr_returns_two_images():
    img_bytes = _make_text_image("镖人漫画对话", font_size=30)
    results = process_image_ocr(img_bytes, font_scale=1.5)
    assert len(results) == 2
    # Both should be valid JPEG
    for buf in results:
        img = Image.open(io.BytesIO(buf))
        assert img.size == (400, 200)


def test_process_image_ocr_no_text_returns_original():
    img = Image.new("RGB", (200, 100), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    results = process_image_ocr(buf.getvalue())
    assert len(results) == 1
    assert results[0] == buf.getvalue()


def test_process_image_ocr_corrupt_image():
    results = process_image_ocr(b"not an image")
    assert len(results) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py::test_process_image_ocr_returns_two_images -v
```

Expected: FAIL — current placeholder always returns length 1

- [ ] **Step 3: Replace `process_image_ocr` placeholder**

Replace the placeholder function in `ocr_processor.py`:

```python
CONFIDENCE_THRESHOLD = 0.5


def process_image_ocr(image_bytes: bytes, font_scale: float = 1.5,
                      quality: int = 95) -> list[bytes]:
    """Process a single page image with OCR font enlargement.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, etc.).
        font_scale: Multiplier for detected font size.
        quality: JPEG save quality.

    Returns:
        list of bytes — length 2 (original, ocr_processed) when text detected,
        length 1 (original only) when no text or error.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return [image_bytes]

    if min(img.size) < 10:
        return [image_bytes]

    original_format = img.format or "JPEG"

    # Detect text
    detections = _detect_text(image_bytes)
    detections = [d for d in detections if d[2] >= CONFIDENCE_THRESHOLD]

    if not detections:
        return [image_bytes]

    # Convert traditional to simplified
    detections = _convert_to_simplified(detections)

    # Erase original text
    bboxes = [d[1] for d in detections]
    erased = _erase_text(img, bboxes)

    # Find font
    try:
        font_path = _find_chinese_font()
    except FileNotFoundError:
        return [image_bytes]

    # Re-render with larger font
    rendered = _render_text(erased, detections, font_path, font_scale)

    if original_format == "JPEG" and rendered.mode == "RGBA":
        rendered = rendered.convert("RGB")

    buf = io.BytesIO()
    save_kwargs = {"format": original_format}
    if original_format == "JPEG":
        save_kwargs["quality"] = quality
    rendered.save(buf, **save_kwargs)

    return [image_bytes, buf.getvalue()]
```

- [ ] **Step 4: Run all OCR processor tests**

```bash
source venv/bin/activate && python3 -m pytest tests/test_ocr_processor.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add ocr_processor.py tests/test_ocr_processor.py
git commit -m "feat: wire up process_image_ocr entry point with full pipeline"
```

---

### Task 8: Add CLI parameters and epub_processor routing

**Files:**
- Modify: `cli.py`
- Modify: `epub_processor.py`

- [ ] **Step 1: Add --mode and --font-scale to CLI**

Edit `cli.py` — add new arguments after the `--quality` argument:

```python
    parser.add_argument(
        "-m", "--mode", choices=["split", "ocr"], default="split",
        help="Processing mode: split (double-page split) or ocr (font enlargement). "
             "Default: split.",
    )
    parser.add_argument(
        "--font-scale", type=float, default=1.5,
        help="Font size multiplier for OCR mode (default: 1.5).",
    )
```

And update the `process_epub` call in the main loop to pass the new params:

```python
            process_epub(epub_path, output_path, mode=args.mode,
                         quality=args.quality, font_scale=args.font_scale)
```

- [ ] **Step 2: Update epub_processor.py to route modes**

Edit `epub_processor.py` — update imports and `process_epub` signature:

At the top, add the OCR import:

```python
from ocr_processor import process_image_ocr
```

Update `process_epub` signature and body:

```python
def process_epub(input_path: str, output_path: str, mode: str = "split",
                 quality: int = 95, font_scale: float = 1.5) -> None:
    """Read EPUB from input_path, process images, write to output_path."""
    metadata, source_images = extract_epub_data(input_path)

    processed_images = []
    for file_name, img_bytes in source_images:
        base_name = os.path.basename(file_name)
        ext = os.path.splitext(base_name)[1].lower()
        media_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        media_type = media_map.get(ext, "image/jpeg")

        if mode == "ocr":
            results = process_image_ocr(img_bytes, font_scale=font_scale,
                                        quality=quality)
            if len(results) == 1:
                processed_images.append((base_name, results[0], media_type))
            else:
                processed_images.append((base_name, results[0], media_type))
                base, ext_part = os.path.splitext(base_name)
                processed_images.append(
                    (f"{base}_OCR{ext_part}", results[1], media_type))
        else:
            results = process_image(img_bytes, quality=quality)
            if len(results) == 1:
                processed_images.append((base_name, results[0], media_type))
            else:
                processed_images.append((base_name, img_bytes, media_type))
                base, ext_part = os.path.splitext(base_name)
                processed_images.append(
                    (f"{base}_T{ext_part}", results[0], media_type))
                processed_images.append(
                    (f"{base}_B{ext_part}", results[1], media_type))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    build_epub(metadata, processed_images, output_path)
```

- [ ] **Step 3: Verify CLI --help shows new options**

```bash
source venv/bin/activate && python3 cli.py --help
```

Expected: output shows `--mode`, `--font-scale` options

- [ ] **Step 4: Run existing tests to verify no regression**

```bash
source venv/bin/activate && python3 -m pytest tests/test_epub_processor.py tests/test_integration.py -v
```

Expected: ALL PASS (split mode is default, existing behavior unchanged)

- [ ] **Step 5: Commit**

```bash
git add cli.py epub_processor.py
git commit -m "feat: add --mode and --font-scale CLI options with OCR routing"
```

---

### Task 9: Add OCR integration test

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Add OCR mode integration test**

Add to `tests/test_integration.py`:

```python
def test_full_pipeline_ocr_mode():
    """CLI processes one EPUB in OCR mode: 1 text image -> 1 original + 1 OCR."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir = os.path.join(tmpdir, "input")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(input_dir)

        # Create an image with Chinese text rendered on it
        font_path = None
        for root, _dirs, files in os.walk("/usr/share/fonts"):
            for fn in files:
                if fn.lower().endswith((".ttf", ".ttc", ".otf")):
                    path = os.path.join(root, fn)
                    try:
                        f = ImageFont.truetype(path, 20)
                        if f.getmask("中"):
                            font_path = path
                            break
                    except Exception:
                        continue
            if font_path:
                break

        if font_path is None:
            pytest.skip("No Chinese font available for test")

        img = Image.new("RGB", (400, 200), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(font_path, 24)
        draw.text((10, 10), "软件工程师测试", fill=(0, 0, 0), font=font)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        _make_epub_with_images(
            os.path.join(input_dir, "book.epub"),
            title="OCR Test",
            author="Test",
            raw_images=[("img_000.jpg", img_bytes)],
        )

        exit_code = main(["-i", input_dir, "-o", output_dir, "--mode", "ocr"])

        assert exit_code == 0
        output_epub = os.path.join(output_dir, "book.epub")
        assert os.path.exists(output_epub)

        book = epub.read_epub(output_epub)
        img_items = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
        # 1 source image -> 1 original + 1 OCR = 2
        assert len(img_items) == 2

        for img_item in img_items:
            result = Image.open(io.BytesIO(img_item.get_content()))
            assert result.size == (400, 200)


def _make_epub_with_images(path, title, author, raw_images):
    """Create an EPUB with pre-made image bytes (no auto-generation).

    raw_images: list of (file_name, image_bytes)
    """
    book = epub.EpubBook()
    book.set_identifier(f"int-{title}")
    book.set_title(title)
    book.add_author(author)

    for file_name, img_bytes in raw_images:
        epub_img = epub.EpubImage()
        epub_img.file_name = file_name
        epub_img.media_type = "image/jpeg"
        epub_img.content = img_bytes
        book.add_item(epub_img)

        page = epub.EpubHtml(
            title=file_name,
            file_name=file_name.replace(".jpg", ".xhtml"),
            content=f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page</title></head><body><img src="{file_name}"/></body></html>'.encode(),
        )
        book.add_item(page)
        book.spine.append(page)

    book.toc = book.spine[:]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(path, book)
```

Also add the missing imports at the top of `tests/test_integration.py`:
```python
import os

from PIL import Image, ImageDraw, ImageFont
```

(Note: `os` and `Image` are already imported; just add `ImageDraw, ImageFont` and ensure `import tempfile` and `import pytest` are present.)

- [ ] **Step 2: Run the integration test**

```bash
source venv/bin/activate && python3 -m pytest tests/test_integration.py::test_full_pipeline_ocr_mode -v
```

Expected: PASS

- [ ] **Step 3: Run all tests**

```bash
source venv/bin/activate && python3 -m pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add OCR mode integration test"
```

---

### Task 10: End-to-end verification with real EPUB

**Files:**
- None (manual verification)

- [ ] **Step 1: Run the CLI in OCR mode on the test input**

```bash
source venv/bin/activate && python3 cli.py -i ./input/ -o ./output_ocr/ --mode ocr --font-scale 1.5 -v
```

- [ ] **Step 2: Verify output EPUB structure**

```bash
source venv/bin/activate && python3 -c "
import io
from PIL import Image
import ebooklib
from ebooklib import epub

book = epub.read_epub('./output_ocr/[鏢人]話001-007.epub')
img_items = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
print(f'Total images: {len(img_items)}')

ocr_count = sum(1 for i in img_items if '_OCR' in i.file_name)
orig_count = sum(1 for i in img_items if '_OCR' not in i.file_name)
print(f'Originals: {orig_count}, OCR processed: {ocr_count}')

# Check a sample OCR image
for item in img_items:
    if '_OCR' in item.file_name:
        img = Image.open(io.BytesIO(item.get_content()))
        print(f'{item.file_name}: {img.size} ({img.mode})')
        break
"
```

Expected: OCR-processed images exist, same dimensions as originals.

- [ ] **Step 3: Clean up test output**

```bash
rm -rf ./output_ocr/
```
