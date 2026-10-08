"""Tesseract helpers shared by the image and PDF extractors.

Adaptive preprocessing (OCR_PREPROCESS=auto, default)
  1. "basic": grayscale + contrast stretch  (fast; enough for clean scans)
  2. if the result is empty / low-confidence / timed out, retry with
     "enhanced": upscale small images, remove shadows (background
     normalisation), denoise, binarise (Otsu), deskew
  3. optionally "enhanced+sharpen" for blurry input
  The variant with the best confidence wins. Clean pages therefore stay fast.

Modes: off | basic | auto
Only Pillow + numpy are required (no OpenCV).
"""
import math
import os

import common

MODE = os.environ.get("OCR_PREPROCESS", "auto").lower()
if MODE == "1":
    MODE = "basic"
elif MODE == "0":
    MODE = "off"
RETRY_CONF = float(os.environ.get("OCR_RETRY_CONF", "80"))     # retry below this mean confidence
FIRST_PASS_TIMEOUT = int(os.environ.get("OCR_FIRST_TIMEOUT", "20"))   # seconds
TARGET_LONG_SIDE = int(os.environ.get("OCR_TARGET_LONG_SIDE", "2300"))
MAX_DESKEW_DEG = float(os.environ.get("OCR_MAX_DESKEW", "12"))


def usable_lang(wanted):
    """Keep only installed languages; return (lang, warning_or_None)."""
    import pytesseract

    have = set(pytesseract.get_languages(config=""))
    parts = [p for p in wanted.split("+") if p]
    ok = [p for p in parts if p in have]
    if not ok:
        raise RuntimeError("none of the Tesseract languages %s are installed" % wanted)
    missing = [p for p in parts if p not in have]
    if missing:
        common.log("WARNING: Tesseract language(s) missing: %s" % ",".join(missing))
        return "+".join(ok), "missing_tesseract_lang:" + ",".join(missing)
    return "+".join(ok), None


# ------------------------------------------------------------ preprocessing
def preprocess_basic(image):
    from PIL import ImageOps
    return ImageOps.autocontrast(ImageOps.grayscale(image))


def _otsu(arr):
    import numpy as np
    hist, _ = np.histogram(arr, bins=256, range=(0, 256))
    total = arr.size
    sum_all = float((hist * np.arange(256)).sum())
    w0 = s0 = 0.0
    best, thr = -1.0, 128
    for t in range(256):
        w0 += hist[t]
        if w0 == 0:
            continue
        w1 = total - w0
        if w1 == 0:
            break
        s0 += t * hist[t]
        m0, m1 = s0 / w0, (sum_all - s0) / w1
        var = w0 * w1 * (m0 - m1) ** 2
        if var > best:
            best, thr = var, t
    return thr


def _estimate_skew(binary_img):
    """Angle (deg) that makes text lines horizontal: maximise row-profile variance."""
    import numpy as np
    from PIL import Image

    small = binary_img.copy()
    small.thumbnail((700, 700))
    ink = Image.fromarray(255 - np.array(small))          # text = bright
    best_angle, best_score = 0.0, -1.0

    def score(angle):
        rot = np.array(ink.rotate(angle, resample=Image.BILINEAR, fillcolor=0)).astype(np.float32)
        rows = rot.sum(axis=1)
        return float(np.var(rows))

    a = -MAX_DESKEW_DEG
    while a <= MAX_DESKEW_DEG + 1e-9:                     # coarse 1 degree
        sc = score(a)
        if sc > best_score:
            best_angle, best_score = a, sc
        a += 1.0
    for fine in [x * 0.25 for x in range(-4, 5)]:         # fine +-1 degree
        sc = score(best_angle + fine)
        if sc > best_score:
            best_angle, best_score = best_angle + fine, sc
    return best_angle if best_score > 0 else 0.0


def preprocess_enhanced(image, sharpen=False):
    """Upscale -> shadow removal -> denoise -> (sharpen) -> Otsu -> deskew."""
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps

    gray = ImageOps.grayscale(image)
    long_side = max(gray.size)
    factor = TARGET_LONG_SIDE / float(long_side)
    if factor > 1.15:                                      # small image: enlarge
        factor = min(factor, 4.0)
        gray = gray.resize((int(gray.size[0] * factor), int(gray.size[1] * factor)), Image.LANCZOS)
    elif factor < 0.6:                                     # huge image: shrink for speed
        gray = gray.resize((int(gray.size[0] * factor), int(gray.size[1] * factor)), Image.LANCZOS)

    # background estimate on a small copy (cheap), then divide it out
    w, h = gray.size
    small = gray.resize((max(8, w // 8), max(8, h // 8)), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(1.0)).filter(ImageFilter.MaxFilter(7))
    bg = small.filter(ImageFilter.GaussianBlur(6)).resize((w, h), Image.BILINEAR)
    g = np.array(gray).astype(np.float32)
    b = np.maximum(np.array(bg).astype(np.float32), 1.0)
    norm = np.clip(g / b * 255.0, 0, 255).astype(np.uint8)
    img = Image.fromarray(norm)

    img = img.filter(ImageFilter.GaussianBlur(1.2))        # denoise (text strokes are thick after upscale)
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=3, percent=220, threshold=0))
    arr = np.array(img)
    thr = _otsu(arr)
    binary = Image.fromarray(((arr > thr) * 255).astype(np.uint8))

    angle = _estimate_skew(binary)
    if abs(angle) >= 0.3:
        binary = binary.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=255)
    return binary


# ---------------------------------------------------------------------- OCR
def _run(image, lang, timeout=None):
    """One Tesseract pass -> (text, mean_conf or None)."""
    import pytesseract

    kwargs = {"lang": lang, "output_type": pytesseract.Output.DICT}
    if timeout:
        kwargs["timeout"] = timeout
    data = pytesseract.image_to_data(image, **kwargs)
    lines, order, confs = {}, [], []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append(word)
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if conf >= 0:
            confs.append(conf)
    text = "\n".join(" ".join(lines[k]) for k in order)
    return text, (round(sum(confs) / len(confs), 1) if confs else None)


def _score(text, conf):
    """Prefer confident results that also contain a reasonable amount of text."""
    words = len(text.split())
    if not words or conf is None:
        return -1.0
    return conf * math.log(1 + words)


def ocr_image(image, lang, return_variant=False):
    """Return (text, confidence) - best of the adaptive preprocessing variants."""
    from PIL import ImageOps

    if MODE == "off":
        text, conf = _run(ImageOps.grayscale(image), lang)
        return (text, conf, "off") if return_variant else (text, conf)

    candidates = []
    try:
        text, conf = _run(preprocess_basic(image), lang,
                          timeout=FIRST_PASS_TIMEOUT if MODE == "auto" else None)
        candidates.append((text, conf, "basic"))
    except RuntimeError as exc:                      # Tesseract timeout on noisy input
        common.log("first OCR pass failed (%s) - retrying with enhanced preprocessing" % exc)
        candidates.append(("", None, "basic"))

    good = candidates[0][1] is not None and candidates[0][1] >= RETRY_CONF and candidates[0][0].strip()
    if MODE == "auto" and not good:
        enhanced = preprocess_enhanced(image)
        text, conf = _run(enhanced, lang, timeout=FIRST_PASS_TIMEOUT * 2)
        candidates.append((text, conf, "enhanced"))
        if conf is None or conf < RETRY_CONF:
            sharp = preprocess_enhanced(image, sharpen=True)
            text, conf = _run(sharp, lang, timeout=FIRST_PASS_TIMEOUT * 2)
            candidates.append((text, conf, "enhanced+sharpen"))

    best = max(candidates, key=lambda c: _score(c[0], c[1]))
    return (best[0], best[1], best[2]) if return_variant else (best[0], best[1])
