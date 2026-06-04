# tests/test_epub_processor.py
import io
import os
import tempfile
import pytest
from PIL import Image
import ebooklib
from ebooklib import epub
from epub_processor import extract_epub_data, build_epub, process_epub


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

        img_items = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
        assert len(img_items) == 2


def test_process_epub_end_to_end():
    """Full split pipeline: read EPUB, process images, write output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.epub")
        _make_test_epub(input_path, title="E2E Book", author="Tester")

        output_path = os.path.join(tmpdir, "output.epub")
        process_epub(input_path, output_path, mode="split")

        assert os.path.exists(output_path)
        book = epub.read_epub(output_path)
        title_vals = book.get_metadata("DC", "title")
        assert title_vals[0][0] == "E2E Book"

        img_items = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
        # 2 source images -> 2 originals + 2 left halves + 2 right halves = 6
        assert len(img_items) == 6


def test_process_epub_skips_corrupt_epub():
    """Corrupt EPUB file raises expected exception."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_path = os.path.join(tmpdir, "bad.epub")
        with open(bad_path, "wb") as f:
            f.write(b"not a zip file")

        output_path = os.path.join(tmpdir, "out.epub")
        import zipfile

        with pytest.raises((zipfile.BadZipFile, Exception)):
            process_epub(bad_path, output_path)
