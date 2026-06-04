# tests/test_integration.py
import io
import os
import tempfile

import pytest
from PIL import Image
import ebooklib
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


def test_full_pipeline_single_epub_split():
    """CLI split mode: 1 spread -> 1 original + 2 halves = 3 images."""
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

        exit_code = main(["-i", input_dir, "-o", output_dir, "-m", "split"])

        assert exit_code == 0
        output_epub = os.path.join(output_dir, "book.epub")
        assert os.path.exists(output_epub)

        book = epub.read_epub(output_epub)
        title_vals = book.get_metadata("DC", "title")
        assert title_vals[0][0] == "Pipeline Test"

        img_items = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
        # 1 spread image -> 1 original + 1 left + 1 right = 3
        assert len(img_items) == 3

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

        exit_code = main(["-i", input_dir, "-o", output_dir, "-m", "split", "-v"])

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

        exit_code = main(["-i", input_dir, "-o", output_dir, "-m", "split"])

        # Exit code 1 due to one failure
        assert exit_code == 1
        # Good EPUB should still be processed
        assert os.path.exists(os.path.join(output_dir, "good.epub"))


def test_drag_mode_pipeline():
    """CLI drag mode: stretches images to target size."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir = os.path.join(tmpdir, "input")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(input_dir)

        _make_epub(
            os.path.join(input_dir, "book.epub"),
            title="Drag Test",
            author="Test Author",
            images_config=[((255, 0, 0), 400, 600)],
        )

        exit_code = main(["-i", input_dir, "-o", output_dir, "-m", "drag",
                          "--target-width", "480", "--target-height", "800"])

        assert exit_code == 0
        output_epub = os.path.join(output_dir, "book.epub")
        assert os.path.exists(output_epub)

        # Re-open and verify images are stretched
        import zipfile
        with zipfile.ZipFile(output_epub, "r") as zf:
            img_names = [n for n in zf.namelist() if n.endswith(".jpg")]
            assert len(img_names) >= 1
            for name in img_names:
                with zf.open(name) as f:
                    result = Image.open(io.BytesIO(f.read()))
                    assert result.size == (480, 800)
