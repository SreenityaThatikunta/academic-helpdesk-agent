"""OCR scanned PDFs (no text layer) in data/docs/ into data/ocr/<name>.txt.

Pages are rendered at 300 dpi with PyMuPDF and read with the tesseract CLI.
Page breaks are kept as form feeds so ingestion can still cite page numbers.

Usage: .venv/bin/python scripts/ocr_scanned.py
"""

import subprocess
import tempfile
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
DOCS, OUT = ROOT / "data" / "docs", ROOT / "data" / "ocr"


def needs_ocr(pdf: Path) -> bool:
    with pymupdf.open(pdf) as d:
        return sum(len(p.get_text().strip()) for p in d) < 50 * len(d)


def ocr(pdf: Path) -> str:
    pages = []
    with pymupdf.open(pdf) as d, tempfile.TemporaryDirectory() as tmp:
        for i, page in enumerate(d):
            img = Path(tmp) / f"p{i}.png"
            page.get_pixmap(dpi=300).save(img)
            res = subprocess.run(["tesseract", str(img), "stdout"], capture_output=True, text=True, check=True)
            pages.append(res.stdout.strip())
    return "\f".join(pages)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(DOCS.glob("*.pdf")):
        if needs_ocr(pdf):
            text = ocr(pdf)
            (OUT / f"{pdf.stem}.txt").write_text(text)
            print(f"OCR {pdf.name}: {len(text)} chars")


if __name__ == "__main__":
    main()
