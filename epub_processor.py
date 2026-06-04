# epub_processor.py
import os
from xml.etree import ElementTree

import ebooklib
from ebooklib import epub

from image_processor import process_image, trim_white_border


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
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        image_items[item.file_name] = item.get_content()
        image_items[os.path.basename(item.file_name)] = item.get_content()

    images = []
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None:
            continue

        if item.get_type() == ebooklib.ITEM_IMAGE:
            images.append((item.file_name, item.get_content()))
        elif item.get_type() == ebooklib.ITEM_DOCUMENT:
            try:
                content = item.get_content().decode("utf-8")
                root = ElementTree.fromstring(content)
                for img_el in root.iterfind(".//x:img", ns):
                    src = img_el.get("src", "")
                    image_bytes = image_items.get(src) or image_items.get(os.path.basename(src))
                    if image_bytes is not None:
                        images.append((src, image_bytes))
            except Exception:
                continue

    return metadata, images


def build_epub(metadata: dict, processed_images: list[tuple[str, bytes, str]],
               output_path: str) -> None:
    """Build a new EPUB from processed images.

    Args:
        metadata: dict with 'title' and 'author'.
        processed_images: list of (file_name, image_bytes, media_type) in page order.
        output_path: path to write the output EPUB file.
    """
    book = epub.EpubBook()
    book.set_identifier(f"reformat-{os.path.basename(output_path)}")
    book.set_title(metadata.get("title", ""))
    if metadata.get("author"):
        book.add_author(metadata["author"])

    spine = []
    toc = []

    for i, (file_name, img_bytes, media_type) in enumerate(processed_images):
        epub_img = epub.EpubImage()
        epub_img.file_name = file_name
        epub_img.media_type = media_type
        epub_img.content = img_bytes
        book.add_item(epub_img)

        page_content = (
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            "<head>"
            f"<title>Page {i + 1}</title>"
            "</head>"
            '<body style="margin:0;padding:0;width:100%;height:100%">'
            '<style>'
            '@page{margin:0;padding:0}'
            'html,body{margin:0;padding:0;width:100%;height:100%}'
            'img{display:block;width:100%;height:100%}'
            '</style>'
            f'<img src="{file_name}"/>'
            "</body>"
            "</html>"
        )
        page = epub.EpubItem()
        page.id = f"page_{i:04d}"
        page.file_name = f"page_{i:04d}.xhtml"
        page.media_type = "application/xhtml+xml"
        page.content = page_content.encode("utf-8")
        book.add_item(page)
        spine.append(page)
        toc.append(page)

    book.spine = spine
    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(output_path, book)


def process_epub_drag(input_path: str, output_path: str, quality: int = 95,
                     target_width: int = 1072, target_height: int = 1448) -> None:
    """Process EPUB by replacing images in-place within the ZIP structure.

    Preserves the original EPUB layout, HTML, CSS, and metadata.
    Trims white borders, then stretches images to target size.
    """
    import zipfile
    import io
    from PIL import Image

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with zipfile.ZipFile(input_path, "r") as zin:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)

                if item.filename.startswith("image/") and item.filename.endswith(".jpg"):
                    # Process page images (skip cover)
                    if "cover" in item.filename.lower():
                        zout.writestr(item, data)
                        continue

                    img = Image.open(io.BytesIO(data))
                    if min(img.size) < 10:
                        zout.writestr(item, data)
                        continue

                    trimmed = trim_white_border(img)
                    filled = trimmed.resize((target_width, target_height), Image.LANCZOS)
                    if filled.mode == "RGBA":
                        filled = filled.convert("RGB")
                    if filled.mode not in ("RGB", "L"):
                        filled = filled.convert("RGB")

                    buf = io.BytesIO()
                    filled.save(buf, format="JPEG", quality=quality)
                    new_data = buf.getvalue()
                    zout.writestr(item, new_data)
                else:
                    zout.writestr(item, data)


def process_epub(input_path: str, output_path: str, mode: str = "drag",
                 quality: int = 95, keep_original: bool = False,
                 target_width: int = 1072, target_height: int = 1448) -> None:
    """Read EPUB from input_path, process images, write to output_path."""
    if mode == "drag":
        process_epub_drag(input_path, output_path, quality=quality,
                         target_width=target_width, target_height=target_height)
        return

    # split mode
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
