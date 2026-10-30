"""Keep a text copy of each primary document the seed lists cite.

    python tools/fetch_documents.py            # fetch anything not yet saved
    python tools/fetch_documents.py --refresh  # fetch everything again

Reports and registers move or vanish (the HSE and gov.ie have both reorganised
their sites since 2019), so each document in data/seed/documents.csv is
downloaded and its text saved under data/documents/<slug>.txt, headed with the
URL, the retrieval date and the file's SHA-256. The seed CSVs cite the slug
and page, so a reader can check a figure without trusting a live link. The
original PDF or page is kept locally in data/raw/documents/ (not committed).
"""

import argparse
import hashlib
import io
import re
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wotl import config  # noqa: E402

DOC_DIR = config.SEED_DIR.parent / "documents"
RAW_DIR = config.RAW_DIR / "documents"
HEADERS = {"User-Agent": "OpenTalamh/0.1 (+https://opentalamh.ie; research on public records)"}


def pdf_text(data):
    """Text of each page; scanned pages (no text layer) are read with OCR when tesseract is installed."""
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text(layout=True) or ""
            if not text.strip():
                text = _ocr(page)
            pages.append(f"\n--- page {i} ---\n" + text)
    return "".join(pages)


def _ocr(page):
    try:
        import pytesseract
    except ImportError:
        return ""
    image = page.to_image(resolution=300).original
    return "[OCR]\n" + pytesseract.image_to_string(image, config="--psm 6")


def html_text(data):
    """Visible text plus every link, so a document's own links can be followed."""
    html = data.decode("utf-8", "replace")
    links = sorted(set(re.findall(r'href="([^"#]+)"', html)))
    # Form fields show how a search page takes its filters.
    fields = re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', html)
    options = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)<', html)
    body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = re.sub(r"[ \t\r\f\v]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n", body)
    return (body.strip() + "\n\n--- links ---\n" + "\n".join(links)
            + "\n\n--- form fields ---\n" + "\n".join(dict.fromkeys(fields))
            + "\n\n--- options ---\n" + "\n".join(f"{v}\t{t.strip()}" for v, t in options))


def fetch(row, refresh=False):
    out = DOC_DIR / f"{row.slug}.txt"
    if out.exists() and not refresh:
        return "kept"
    r = requests.get(row.url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    data = r.content
    is_pdf = data[:4] == b"%PDF"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{row.slug}.{'pdf' if is_pdf else 'html'}").write_bytes(data)
    text = pdf_text(data) if is_pdf else html_text(data)
    header = (f"title: {row.title}\nurl: {row.url}\nretrieved: {date.today().isoformat()}\n"
              f"sha256: {hashlib.sha256(data).hexdigest()}\nformat: {'pdf' if is_pdf else 'html'}\n")
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(header + "\n" + text, encoding="utf-8")
    return f"saved ({len(text):,} characters)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    docs = pd.read_csv(config.SEED_DIR / "documents.csv").fillna("")
    for row in docs.itertuples():
        try:
            print(f"{row.slug}: {fetch(row, args.refresh)}", flush=True)
        except Exception as e:  # one dead link shouldn't stop the rest
            print(f"{row.slug}: FAILED {e}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
