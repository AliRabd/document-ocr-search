#!/usr/bin/env python3
"""PDF -> JSON Lines, decided PAGE BY PAGE.

For every page: use the embedded text layer when it has real text, otherwise
render the page and OCR it with Tesseract. A PDF that mixes text pages and
scanned pages is therefore handled correctly.

Backends: PyMuPDF (fast) if installed, otherwise poppler-utils
(pdftotext / pdftoppm / pdfinfo) - so it also works without PyMuPDF.
"""
import io
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import ocr_tesseract  # noqa: E402
from common import make_records  # noqa: E402

OCR_DPI = int(os.environ.get("OCR_DPI", "250"))
OCR_LANG = os.environ.get("OCR_LANG", "ara+eng")
MIN_TEXT_CHARS = int(os.environ.get("MIN_TEXT_CHARS", "25"))   # per page
CMD_TIMEOUT = int(os.environ.get("CMD_TIMEOUT", "300"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "2000"))


class MuPdfBackend(object):
    name = "pymupdf"

    def __init__(self, path):
        import fitz
        self.doc = fitz.open(path)

    def page_count(self):
        return len(self.doc)

    def text(self, index):
        return self.doc[index].get_text()

    def image(self, index):
        from PIL import Image
        pix = self.doc[index].get_pixmap(dpi=OCR_DPI, alpha=False)
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

    def close(self):
        self.doc.close()


class PopplerBackend(object):
    name = "poppler"

    def __init__(self, path):
        self.path = path
        out = subprocess.run(["pdfinfo", path], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=CMD_TIMEOUT,
                             check=True).stdout.decode("utf-8", "replace")
        match = re.search(r"^Pages:\s+(\d+)", out, re.M)
        self.pages = int(match.group(1)) if match else 0

    def page_count(self):
        return self.pages

    def text(self, index):
        out = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", "-f", str(index + 1), "-l",
             str(index + 1), self.path, "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=CMD_TIMEOUT, check=True).stdout
        return out.decode("utf-8", "replace")

    def image(self, index):
        from PIL import Image
        out = subprocess.run(
            ["pdftoppm", "-r", str(OCR_DPI), "-f", str(index + 1), "-l",
             str(index + 1), "-png", self.path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=CMD_TIMEOUT, check=True).stdout
        return Image.open(io.BytesIO(out)).convert("RGB")

    def close(self):
        pass


def open_backend(path):
    try:
        return MuPdfBackend(path)
    except ImportError:
        return PopplerBackend(path)


def process_pdf(path):
    """Return (text, extra_dict, warning)."""
    backend = open_backend(path)
    parts, confs = [], []
    n_text = n_ocr = n_fail = 0
    lang, warn = None, None
    try:
        total = min(backend.page_count(), MAX_PAGES)
        for index in range(total):
            try:
                layer = backend.text(index)
                if len(layer.strip()) >= MIN_TEXT_CHARS:
                    parts.append(layer.strip())
                    n_text += 1
                    continue
                if lang is None:
                    lang, warn = ocr_tesseract.usable_lang(OCR_LANG)
                image = backend.image(index)
                try:
                    text, conf = ocr_tesseract.ocr_image(image, lang)
                finally:
                    image.close()
                if text.strip():
                    parts.append(text.strip())
                if conf is not None:
                    confs.append(conf)
                n_ocr += 1
            except Exception as exc:
                n_fail += 1
                common.log("Page %d failed in %s: %s" % (index + 1, path, exc))
    finally:
        backend.close()

    extra = {
        "page_count": total,
        "pages_text_layer": n_text,
        "pages_ocr": n_ocr,
        "pages_failed": n_fail,
        "ocr_confidence": round(sum(confs) / len(confs), 1) if confs else None,
        "pdf_backend": backend.name,
    }
    if n_fail:
        warn = (warn + ";" if warn else "") + "pages_failed:%d" % n_fail
    return "\n\n".join(parts), extra, warn


def main(argv):
    common.setup_stdio()
    if not argv:
        common.log("Usage: pdf_image_extractor_2.py <pdf> [<pdf> ...]")
        return 1
    for path in argv:
        start = time.time()
        try:
            text, extra, warn = process_pdf(path)
            engine = "tesseract" if extra["pages_ocr"] else "text_layer"
            if extra["pages_ocr"] and extra["pages_text_layer"]:
                engine = "hybrid"
            doc_type = "pdf_scanned" if extra["pages_ocr"] else "pdf_text"
            records = make_records(path, text, doc_type, engine, extra,
                                   warning=warn, elapsed=time.time() - start)
        except Exception as exc:
            msg = "Failed to extract PDF %s: %s" % (os.path.basename(path), exc)
            common.log(msg)
            records = [common.error_record(path, "pdf", msg)]
        common.print_records(records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
