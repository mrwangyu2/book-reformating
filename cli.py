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
        description="Reformat EPUB comic images: split double-pages or stretch to target resolution.",
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
        "-m", "--mode", choices=["split", "drag"], default="drag",
        help="Processing mode: split (double-page split + rotate) or drag (stretch to fill screen). Default: drag.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print detailed processing log.",
    )
    parser.add_argument(
        "--keep-original", action="store_true",
        help="In split mode, keep the original double-page image alongside the split halves.",
    )
    parser.add_argument(
        "--target-width", type=int, default=1072,
        help="Target screen width in pixels for drag mode (default: 1072).",
    )
    parser.add_argument(
        "--target-height", type=int, default=1448,
        help="Target screen height in pixels for drag mode (default: 1448).",
    )
    parser.add_argument(
        "--preset", choices=["480x800", "528x792", "1072x1448"], default="1072x1448",
        help="Target resolution preset for drag mode (default: 1072x1448).",
    )
    args = parser.parse_args(argv)

    # Apply preset default, then explicit args override
    if args.preset == "480x800":
        if "--target-width" not in (argv or sys.argv):
            args.target_width = 480
        if "--target-height" not in (argv or sys.argv):
            args.target_height = 800
    elif args.preset == "528x792":
        if "--target-width" not in (argv or sys.argv):
            args.target_width = 528
        if "--target-height" not in (argv or sys.argv):
            args.target_height = 792

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
            process_epub(epub_path, output_path, mode=args.mode,
                         quality=args.quality,
                         keep_original=args.keep_original,
                         target_width=args.target_width,
                         target_height=args.target_height)
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
