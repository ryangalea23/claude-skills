"""Prep a signature image: convert a photo/scan (white background) to a
transparent PNG for use with sign_pdf.py.

Threshold-based: pixels brighter than `threshold` become fully transparent;
darker pixels keep their original color and stay opaque. Tweak threshold if
the result loses ink or keeps background paper texture.

Usage:
  python prep_signature.py <source-image> <dest.png> [--threshold 230]
"""

import argparse
import sys
from pathlib import Path

from PIL import Image


def prep(src: Path, dst: Path, threshold: int) -> tuple[int, int, int]:
    im = Image.open(src).convert("RGBA")
    pixels = im.load()
    w, h = im.size
    cleared = 0
    for y in range(h):
        for x in range(w):
            r, g, b, _ = pixels[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                pixels[x, y] = (255, 255, 255, 0)
                cleared += 1

    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "PNG")
    return w, h, cleared


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="Path to the source photo/scan (jpg/png)")
    parser.add_argument("dest", help="Path to write the transparent PNG")
    parser.add_argument(
        "--threshold",
        type=int,
        default=230,
        help="0-255; higher keeps more near-white paper texture, lower is more aggressive removal (default 230)",
    )
    args = parser.parse_args()

    src = Path(args.source)
    dst = Path(args.dest)

    if not src.exists():
        print(f"Source not found: {src}", file=sys.stderr)
        return 1

    w, h, cleared = prep(src, dst, args.threshold)
    total = w * h
    print(f"Saved: {dst}")
    print(f"Size: {w}x{h}, cleared {cleared}/{total} pixels ({cleared * 100 // total}%) to transparent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
