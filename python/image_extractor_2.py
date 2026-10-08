#!/usr/bin/env python3
"""Images -> OCR -> JSON Lines.

Engines:  easyocr (default, good on Arabic photos)  |  tesseract
Choose with  IMAGE_OCR_ENGINE=easyocr|tesseract.
Accepts MANY files per call so the (slow) model is loaded once per batch.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from common import make_records  # noqa: E402

ENGINE = os.environ.get("IMAGE_OCR_ENGINE", "easyocr").lower()
MAX_IMAGE_SIDE = int(os.environ.get("MAX_IMAGE_SIDE", "4000"))
MIN_CONF = float(os.environ.get("EASYOCR_MIN_CONF", "0.0"))     # 0..1
USE_GPU = os.environ.get("EASYOCR_GPU", "0") == "1"
EASY_LANGS = os.environ.get("EASYOCR_LANGS", "en,ar").split(",")
TESS_LANG = os.environ.get("OCR_LANG", "ara+eng")


def load_pil(path):
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)        # phone photos: fix rotation
        image = image.convert("RGB")
        if max(image.size) > MAX_IMAGE_SIDE:          # bound memory/time
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        return image.copy()


def easyocr_one(reader, path):
    import numpy as np

    image = load_pil(path)
    results = reader.readtext(np.array(image), detail=1, paragraph=False)
    kept = [(t, c) for _b, t, c in results if c >= MIN_CONF]
    text = "\n".join(t for t, _ in kept)
    confs = [c for _, c in kept]
    conf = round(100.0 * sum(confs) / len(confs), 1) if confs else None
    return text, conf


def main(argv):
    common.setup_stdio()
    if not argv:
        common.log("Usage: image_extractor_2.py <image> [<image> ...]")
        return 1

    reader, warn = None, None
    try:
        if ENGINE == "easyocr":
            import easyocr
            reader = easyocr.Reader(EASY_LANGS, gpu=USE_GPU)
        else:
            import ocr_tesseract
            lang, warn = ocr_tesseract.usable_lang(TESS_LANG)
    except Exception as exc:
        msg = "Cannot start OCR engine %s: %s" % (ENGINE, exc)
        common.log(msg)
        for path in argv:
            common.print_records([common.error_record(path, "image", msg)])
        return 0

    for path in argv:
        start = time.time()
        try:
            if ENGINE == "easyocr":
                text, conf = easyocr_one(reader, path)
            else:
                text, conf = ocr_tesseract.ocr_image(load_pil(path), lang)
            records = make_records(path, text, "image", ENGINE,
                                   {"ocr_confidence": conf}, warning=warn,
                                   elapsed=time.time() - start)
        except Exception as exc:
            msg = "Failed to process image %s: %s" % (os.path.basename(path), exc)
            common.log(msg)
            records = [common.error_record(path, "image", msg)]
        common.print_records(records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
