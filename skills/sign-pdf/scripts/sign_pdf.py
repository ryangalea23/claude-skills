"""Sign a PDF by stamping a transparent signature image (and optionally a date).

Modes:
  inspect   - Print page count, dimensions, AcroForm fields, candidate sig markers
  preview   - Render a single page as a PNG so you can pick coordinates visually
  stamp     - Place signature image at (page, x, y) on a copy of the PDF
  text      - Stamp plain text at (page, x, y) for printed name, title, date
  auto      - Try to fill AcroForm signature fields, fall back to text-search

Coordinates are in PDF points (72 per inch). Origin is top-left of each page
(PyMuPDF default). Use `inspect` to see page sizes, then `preview` to render
with a coordinate grid before committing to `stamp`.

The signature image path comes from `--signature`, or from the
SIGNATURE_IMAGE environment variable if `--signature` is omitted. There is no
built-in default signature — you provide your own (see prep_signature.py and
the skill's SKILL.md for how to make one).

Usage:
  python sign_pdf.py inspect <input.pdf>
  python sign_pdf.py preview <input.pdf> --page 1 [--out preview.png]
  python sign_pdf.py stamp <input.pdf> --page 1 --x 100 --y 600 [--width 150] [--date] [--signature sig.png] [--out signed.pdf]
  python sign_pdf.py auto <input.pdf> [--signature sig.png] [--out signed.pdf]
"""

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

SIG_LABEL_RE = re.compile(r"signature|signed|by:\s*$|\b/s/\b", re.IGNORECASE)


def resolve_signature(cli_value: str | None) -> Path | None:
    """Signature image path: --signature flag, else SIGNATURE_IMAGE env var, else None."""
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get("SIGNATURE_IMAGE")
    if env_value:
        return Path(env_value)
    return None


def default_output(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}-signed.pdf")


def save_pdf(pdf: "fitz.Document", input_path: Path, out_path: Path) -> None:
    """Save with incremental flag if writing back to the same file (PyMuPDF requirement)."""
    if out_path.resolve() == input_path.resolve():
        pdf.save(str(out_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    else:
        pdf.save(str(out_path))


def cmd_inspect(args: argparse.Namespace) -> int:
    pdf = fitz.open(args.input)
    print(f"Pages: {len(pdf)}")
    for i, page in enumerate(pdf, 1):
        rect = page.rect
        print(f"  Page {i}: {rect.width:.0f} x {rect.height:.0f} pts")
    widgets = []
    for page in pdf:
        for w in page.widgets() or []:
            widgets.append((page.number + 1, w))
    if widgets:
        print(f"\nForm fields ({len(widgets)}):")
        for page_num, w in widgets:
            print(f"  Page {page_num}: type={w.field_type_string} name={w.field_name!r} rect={w.rect}")
    else:
        print("\nNo AcroForm fields detected.")

    print("\nCandidate signature markers (text search):")
    found_any = False
    for page in pdf:
        for inst in page.search_for("Signature") + page.search_for("By:") + page.search_for("/s/"):
            found_any = True
            print(f"  Page {page.number + 1}: rect={inst}")
    if not found_any:
        print("  (none)")

    pdf.close()
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    pdf = fitz.open(args.input)
    page = pdf[args.page - 1]
    pix = page.get_pixmap(dpi=120)
    out = Path(args.out) if args.out else Path(args.input).with_name(f"preview-p{args.page}.png")
    pix.save(out)
    print(f"Saved preview: {out}")
    print(f"Page size: {page.rect.width:.0f} x {page.rect.height:.0f} pts")
    pdf.close()
    return 0


def stamp_signature(page: fitz.Page, sig_path: Path, x: float, y: float, width: float, date: bool) -> None:
    sig_pix = fitz.Pixmap(str(sig_path))
    aspect = sig_pix.height / sig_pix.width
    height = width * aspect
    rect = fitz.Rect(x, y, x + width, y + height)
    page.insert_image(rect, filename=str(sig_path), keep_proportion=True)
    if date:
        today = datetime.date.today().strftime("%Y-%m-%d")
        page.insert_text(
            (x, y + height + 12),
            today,
            fontsize=10,
            fontname="helv",
            color=(0, 0, 0),
        )


def cmd_stamp(args: argparse.Namespace) -> int:
    sig_path = resolve_signature(args.signature)
    if not sig_path:
        print("No signature image given. Pass --signature or set SIGNATURE_IMAGE.", file=sys.stderr)
        return 1
    if not sig_path.exists():
        print(f"Signature image not found: {sig_path}", file=sys.stderr)
        return 1

    pdf = fitz.open(args.input)
    if not (1 <= args.page <= len(pdf)):
        print(f"Page {args.page} out of range (1..{len(pdf)})", file=sys.stderr)
        return 1
    page = pdf[args.page - 1]
    stamp_signature(page, sig_path, args.x, args.y, args.width, args.date)
    out = Path(args.out) if args.out else default_output(Path(args.input))
    save_pdf(pdf, Path(args.input), out)
    pdf.close()
    print(f"Signed PDF saved: {out}")
    return 0


def cmd_text(args: argparse.Namespace) -> int:
    pdf = fitz.open(args.input)
    if not (1 <= args.page <= len(pdf)):
        print(f"Page {args.page} out of range (1..{len(pdf)})", file=sys.stderr)
        return 1
    page = pdf[args.page - 1]
    page.insert_text(
        (args.x, args.y),
        args.text,
        fontsize=args.size,
        fontname=args.font,
        color=(0, 0, 0),
    )
    out = Path(args.out) if args.out else default_output(Path(args.input))
    save_pdf(pdf, Path(args.input), out)
    pdf.close()
    print(f"Text stamped on page {args.page} at ({args.x}, {args.y}): {args.text!r}")
    print(f"Saved: {out}")
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    sig_path = resolve_signature(args.signature)
    if not sig_path:
        print("No signature image given. Pass --signature or set SIGNATURE_IMAGE.", file=sys.stderr)
        return 1
    if not sig_path.exists():
        print(f"Signature image not found: {sig_path}", file=sys.stderr)
        return 1

    pdf = fitz.open(args.input)
    placed = 0

    # 1. AcroForm signature widgets first.
    for page in pdf:
        for w in page.widgets() or []:
            if w.field_type_string and "signature" in w.field_type_string.lower():
                rect = w.rect
                page.insert_image(rect, filename=str(sig_path), keep_proportion=True)
                placed += 1
                print(f"  Filled signature field on page {page.number + 1}: {w.field_name!r}")

    # 2. Fallback: search for "Signature" / "By:" labels and stamp to the right.
    if placed == 0:
        for page in pdf:
            for label in ("Signature:", "By:", "Signed:"):
                for rect in page.search_for(label):
                    # Stamp roughly to the right of the label, sized for a signature.
                    x = rect.x1 + 5
                    y = rect.y0 - 5
                    width = 150
                    aspect = fitz.Pixmap(str(sig_path)).height / fitz.Pixmap(str(sig_path)).width
                    height = width * aspect
                    target = fitz.Rect(x, y, x + width, y + height)
                    page.insert_image(target, filename=str(sig_path), keep_proportion=True)
                    placed += 1
                    print(f"  Stamped near '{label}' on page {page.number + 1} at ({x:.0f}, {y:.0f})")

    if placed == 0:
        print("No signature fields or labels found. Use `inspect` then `stamp` with explicit coords.", file=sys.stderr)
        pdf.close()
        return 2

    out = Path(args.out) if args.out else default_output(Path(args.input))
    save_pdf(pdf, Path(args.input), out)
    pdf.close()
    print(f"Signed PDF saved: {out} (placed {placed} signature{'s' if placed > 1 else ''})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_inspect = sub.add_parser("inspect", help="Show pages, form fields, and signature markers")
    sp_inspect.add_argument("input")
    sp_inspect.set_defaults(func=cmd_inspect)

    sp_preview = sub.add_parser("preview", help="Render a page as PNG to pick coordinates")
    sp_preview.add_argument("input")
    sp_preview.add_argument("--page", type=int, required=True)
    sp_preview.add_argument("--out", default=None)
    sp_preview.set_defaults(func=cmd_preview)

    sp_stamp = sub.add_parser("stamp", help="Stamp signature at explicit coordinates")
    sp_stamp.add_argument("input")
    sp_stamp.add_argument("--page", type=int, required=True)
    sp_stamp.add_argument("--x", type=float, required=True)
    sp_stamp.add_argument("--y", type=float, required=True)
    sp_stamp.add_argument("--width", type=float, default=150.0, help="Signature width in PDF points (default 150 ~= 2 inches)")
    sp_stamp.add_argument("--date", action="store_true", help="Stamp today's date below signature")
    sp_stamp.add_argument("--signature", default=None, help="Path to signature image (else SIGNATURE_IMAGE env var)")
    sp_stamp.add_argument("--out", default=None)
    sp_stamp.set_defaults(func=cmd_stamp)

    sp_text = sub.add_parser("text", help="Stamp plain text at explicit coordinates (for printed name, title, date)")
    sp_text.add_argument("input")
    sp_text.add_argument("text", help="Text to stamp")
    sp_text.add_argument("--page", type=int, required=True)
    sp_text.add_argument("--x", type=float, required=True)
    sp_text.add_argument("--y", type=float, required=True, help="Text baseline y in PDF points")
    sp_text.add_argument("--size", type=float, default=11.0, help="Font size in points (default 11)")
    sp_text.add_argument("--font", default="helv", help="PyMuPDF builtin font name (default 'helv')")
    sp_text.add_argument("--out", default=None)
    sp_text.set_defaults(func=cmd_text)

    sp_auto = sub.add_parser("auto", help="Auto-detect signature fields/labels and fill")
    sp_auto.add_argument("input")
    sp_auto.add_argument("--signature", default=None, help="Path to signature image (else SIGNATURE_IMAGE env var)")
    sp_auto.add_argument("--out", default=None)
    sp_auto.set_defaults(func=cmd_auto)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
