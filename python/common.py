"""Shared helpers for all extractors (Python 3.8+ compatible).

Output contract
---------------
Every extractor prints JSON Lines to stdout: one JSON object per *chunk* of
text. Short files give one line, long files several (chunk_index/chunk_total).
Nothing else may be written to stdout; diagnostics go to stderr.
Failures are still emitted as a record with an ``error`` field, so they are
visible in Kibana instead of disappearing.
"""
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

# Safety cap per file, and size of each Elasticsearch chunk.
MAX_TOTAL_CHARS = int(os.environ.get("MAX_CHARS", "1000000"))
CHUNK_CHARS = int(os.environ.get("CHUNK_CHARS", "10000"))

# Zero-width / bidi control characters break Arabic search and add nothing.
_INVISIBLE = re.compile("[​-‏‪-‮⁦-⁩﻿\x00]")


def setup_stdio():
    """Force UTF-8 output regardless of the locale Logstash/systemd provides."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass


def log(message):
    print(message, file=sys.stderr, flush=True)


def normalize_text(text):
    """NFKC (fixes Arabic presentation forms), drop invisible chars, tidy blanks."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _INVISIBLE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    text = re.sub(r"[ \t\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chunks(text, size):
    """Split near `size` at a newline/space so words are not cut in half."""
    if len(text) <= size:
        return [text]
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            cut = text.rfind("\n", start + size // 2, end)
            if cut == -1:
                cut = text.rfind(" ", start + size // 2, end)
            if cut != -1:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
    return chunks or [""]


def path_hash(file_path):
    """Stable, short, ASCII Elasticsearch _id base (raw paths can exceed 512 bytes)."""
    return hashlib.sha1(file_path.encode("utf-8", "surrogateescape")).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _file_meta(file_path):
    meta = {
        "file_path": file_path,
        "filename": os.path.basename(file_path),
        "extension": os.path.splitext(file_path)[1].lower().lstrip("."),
    }
    try:
        st = os.stat(file_path)
        meta["file_size"] = st.st_size
        meta["modified"] = datetime.fromtimestamp(
            st.st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        pass
    return meta


def make_records(file_path, text, doc_type, engine, extra=None,
                 error=None, warning=None, truncated=False, elapsed=None):
    """Return a list of JSON-serialisable dicts, one per chunk."""
    text = normalize_text(text)
    if len(text) > MAX_TOTAL_CHARS:
        text, truncated = text[:MAX_TOTAL_CHARS], True
    chunks = split_chunks(text, CHUNK_CHARS)

    base = _file_meta(file_path)
    base.update({
        "doc_type": doc_type,
        "ocr_engine": engine,
        "char_count": len(text),
        "word_count": len(text.split()),
        "truncated": bool(truncated),
        "processed_at": _now(),
    })
    if elapsed is not None:
        base["extract_seconds"] = round(elapsed, 3)
    if extra:
        base.update({k: v for k, v in extra.items() if v is not None})
    if error:
        base["error"] = error
    elif not text:
        base["warning"] = warning or "no_text_extracted"
    elif warning:
        base["warning"] = warning

    records = []
    for index, chunk in enumerate(chunks):
        rec = dict(base)
        rec.update({
            "content": chunk,
            "chunk_index": index,
            "chunk_total": len(chunks),
            "doc_id": "%s_%d" % (path_hash(file_path), index),
        })
        records.append(rec)
    return records


def error_record(file_path, doc_type, message):
    """Failures are indexed too: content stays empty, message goes in `error`."""
    return make_records(file_path, "", doc_type, "none", error=message)[0]


def print_records(records):
    for rec in records:
        sys.stdout.write(json.dumps(rec, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def candidate_encodings(path):
    """BOM-aware encoding list; cp1256 covers Arabic Excel exports."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(4)
    except OSError:
        head = b""
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return ["utf-16", "utf-8-sig", "cp1256", "latin-1"]
    return ["utf-8-sig", "cp1256", "latin-1"]
