# epub-reformat

Reformat EPUB comic/manga images for e-reader screens. Two modes: split double-page spreads into single pages, or stretch images to fill a target resolution.

## Installation

```bash
pip install -e .
```

Requires Python >= 3.10. Dependencies: `ebooklib`, `Pillow`.

## Usage

```bash
python cli.py -i <input_dir> -o <output_dir> -m <mode> [options]
```

### Modes

**`drag`** (default) — Stretch every page image to fill a target screen resolution. Preserves original EPUB structure (ZIP-level replacement, no rebuild). Skips cover images.

```bash
python cli.py -i ~/comics/in -o ~/comics/out -m drag --preset 480x800
```

**`split`** — Split double-page spreads in half, rotate each half 90° clockwise, trim white borders, and scale to fill the original dimensions.

```bash
python cli.py -i ~/comics/in -o ~/comics/out -m split
```

### Options

| Option | Default | Description |
|---|---|---|
| `-i`, `--input-dir` | *(required)* | Directory containing `.epub` files |
| `-o`, `--output-dir` | *(required)* | Directory for processed `.epub` files |
| `-m`, `--mode` | `drag` | `split` or `drag` |
| `-q`, `--quality` | `95` | JPEG output quality (1–100) |
| `-v`, `--verbose` | off | Print per-file processing log |
| `--preset` | `1072x1448` | Target resolution preset: `480x800`, `528x792`, `1072x1448` |
| `--target-width` | `1072` | Custom target width (overrides preset) |
| `--target-height` | `1448` | Custom target height (overrides preset) |
| `--keep-original` | off | In split mode, keep the original double-page image |

## Examples

Stretch a folder of EPUBs to fit a 4.3-inch 220PPI e-reader screen:

```bash
python cli.py -i "E:\manga\input" -o "E:\manga\480x800" -m drag --preset 480x800 -v
```

Split all double-page spreads into single pages:

```bash
python cli.py -i ./input -o ./output -m split -v
```

Custom target resolution:

```bash
python cli.py -i ./input -o ./output -m drag --target-width 600 --target-height 900
```

## How it works

- **drag mode**: Opens EPUB as ZIP, reads each `image/*.jpg`, trims white borders, resizes to target dimensions, writes back. All other files (HTML, CSS, OPF, NCX) pass through unchanged.
- **split mode**: Reads EPUB via `ebooklib`, splits each page image horizontally at the midline, rotates each half 90° clockwise, trims white borders, scales proportionally to fill original dimensions (center-crop overflow), and builds a new EPUB.

## License

MIT
