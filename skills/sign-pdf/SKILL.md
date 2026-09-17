---
name: sign-pdf
description: Use when the user asks to sign a PDF, add their signature to an attached document, return a signed Docusign-style PDF, or "sign and return" any contract or agreement. Stamps a transparent signature image onto a PDF at AcroForm fields, near "Signature:" labels, or at explicit coordinates.
allowed-tools:
  - Bash
  - Read
---

# Sign PDF (signature stamping for sign-and-return workflows)

## Overview

Most "sign and return" PDFs aren't true Docusign envelopes — they're flat PDFs with a "Signature:" line, or proper AcroForm PDFs with fillable signature fields. This skill stamps a transparent PNG of the user's signature at the right spot, optionally adds today's date, and saves a signed copy. The output is a normal PDF that can be attached to a reply email.

**Tool:** `scripts/sign_pdf.py` (PyMuPDF-based)
**Signature image:** you provide this — see Setup below. Never use a placeholder or a signature that isn't the actual user's.

## Setup

Before first use:

1. Get a clear image of the user's signature: a photo of it signed on plain white paper, or a scan.
2. Run `scripts/prep_signature.py` to turn it into a transparent PNG (white background removed, ink kept):
   ```bash
   python scripts/prep_signature.py "/path/to/signature-source.jpg" "/path/to/signature.png"
   ```
   Tune `--threshold` (default 230, range 0-255) if the result loses ink or keeps paper texture — lower is more aggressive at removing near-white pixels.
3. Tell `sign_pdf.py` where that PNG lives, either by passing `--signature /path/to/signature.png` on every command, or by setting the environment variable `SIGNATURE_IMAGE` so you don't have to repeat it.
4. Keep the signature PNG out of source control and treat it like a sensitive file (see Signature Asset Hygiene below).

## When to Use

**Use when:**
- The user attaches/forwards a PDF and says "sign this", "add my signature", "sign and return"
- A contract/agreement/form needs their signature

**Don't use for:**
- Docs marked "must be wet-signed" or with notary blocks (legally insufficient)
- Real-estate closings, banking power-of-attorney, anything requiring witnessing
- True Docusign envelopes — those should go through Docusign's UI for the audit trail

## Legal Note (ESIGN Act, US)

This is general background, not legal advice.

Image-stamp signatures on flat PDFs are binding for normal commercial contracts under the US ESIGN Act 2000. Avoid them for: notarized documents, anything explicitly requiring wet-ink, real-estate closings, and Docusign-grade-audit-trail required docs (some banking/HIPAA contexts). If you're outside the US, check your own jurisdiction's e-signature rules before relying on this. When in doubt, surface the question to the user before signing.

## Workflow

```
inspect -> preview (optional) -> stamp OR auto
```

1. **`inspect`** — print page count, dimensions, AcroForm fields, and "Signature:"/"By:" labels detected by text search. Always start here.
2. **`auto`** — try AcroForm signature fields first; fall back to stamping near label text. Works on the majority of well-built PDFs, not all.
3. **`preview`** — render a page as PNG so you can eyeball the layout and pick (x,y) coordinates manually.
4. **`stamp`** — place signature image at explicit `--page --x --y --width` (PDF points, 72 per inch, top-left origin).
5. **`text`** — stamp plain text (printed name, title, date) at explicit `--page --x --y --size`. The y is the text baseline. Use this to fill the rows below the signature line.

## Quick Reference

```bash
# Inspect
python scripts/sign_pdf.py inspect "/path/to/contract.pdf"

# Auto (try first — fastest path)
python scripts/sign_pdf.py auto "/path/to/contract.pdf" --signature "/path/to/signature.png"

# Preview a page to pick coordinates
python scripts/sign_pdf.py preview "/path/to/contract.pdf" --page 5

# Stamp at explicit coords + date below signature
python scripts/sign_pdf.py stamp "/path/to/contract.pdf" --page 5 --x 100 --y 620 --width 150 --date --signature "/path/to/signature.png"

# Stamp plain text (printed name, title, date) at coords. Run once per field; chain via --out.
python scripts/sign_pdf.py text "Jane Doe" --page 5 --x 316 --y 161 --size 11
python scripts/sign_pdf.py text "Chief Executive Officer" --page 5 --x 316 --y 194 --size 11
python scripts/sign_pdf.py text "2026-05-06" --page 5 --x 316 --y 227 --size 11

# Custom output path
... --out "/path/to/contract-signed.pdf"
```

Default output is `<original>-signed.pdf` next to the input. `--signature` can be omitted if you set the `SIGNATURE_IMAGE` environment variable.

## Decision Flow

```
Got PDF to sign
  |
  v
Run inspect
  |
  v
Has AcroForm signature widgets?  -- yes --> auto, then verify with preview
  |
  no
  v
Has "Signature:" / "By:" labels found?  -- yes --> auto (text-search fallback), verify
  |
  no
  v
Manual: preview each candidate page, pick coords, stamp explicitly
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Renaming the signed PDF with a date/recipient prefix | Preserve the original filename — only append `-signed`. Recipients recognize docs by original name; renaming confuses them. |
| Skipping inspect, stamping blind | Always inspect first; coordinates differ per PDF. |
| Guessing text field y-coordinates | Extract the existing signer's filled values via `page.get_text('dict')` and mirror those exact y positions. Don't estimate — use the PDF's own data. |
| Placing text values below their label | Values go ABOVE the label/rule that identifies the field (traditional form convention). Use the other party's filled positions as the reference. |
| Putting the signer's name twice | Name goes only in the Printed Name field. The signature image alone occupies the Signature area — no typed name there unless the other party did the same. |
| Using an 11pt font when form labels are 9pt | Match the form's font size (check `span['size']` in text extraction). Mismatched size looks off. |
| Using stamp width too small (<100) | Signature looks tiny. Default 150 pts (~2 inches) is right. |
| Not adding `--date` when the doc has a date line | Reader expects ISO date or "MM/DD/YYYY" near sig. Use `--date`. |
| Stamping a notarized doc | Legally insufficient. Surface the notary block to the user before signing. |
| Using initials per page when only signature wanted | Tool currently stamps once; for per-page initials, run `stamp` once per page. |

## Signature Asset Hygiene

- Keep the source photo/scan and the transparent working PNG out of source control (`.gitignore` should cover them — see this repo's own `.gitignore` as an example, but if you install this skill inside your own project, make sure your `.gitignore` there also excludes it).
- If the machine holding the signature PNG is compromised, that PNG could be used to forge documents. Consider encrypting it at rest, or storing it in your OS's credential manager, if that risk matters to you.

## Limitations (current v1)

- **Single signature per run** for `stamp` mode (auto can place multiple if multiple fields/labels found)
- **No initials-per-page mode** — would need a `--initials` flag with corner placement
- **No checkbox/text-field filling** — only signature image stamping
- **No verification of signed output** — always open the signed PDF and visually confirm before sending
- **Coordinate origin is top-left** in PyMuPDF, but some PDF tools use bottom-left. If a stamp lands in the wrong place, try `--y (page_height - y)`.
