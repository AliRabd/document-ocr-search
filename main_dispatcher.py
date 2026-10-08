#!/usr/bin/env python3
"""Scan INPUT_DIR, run the right extractor, print JSON Lines to stdout.

Improvements over v1
  * every outcome reaches stdout (failures become records with `error`)
  * per-file/batch TIMEOUT so one stuck file cannot block the pipeline
  * STATE FILE: unchanged files are skipped on later runs (path+mtime+size)
  * images are sent in batches so the OCR model loads once per batch
  * recursive scan, unsupported types logged once, all paths via env vars
stdout = JSON only (Logstash json_lines). Diagnostics -> stderr.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PY_DIR = os.path.join(BASE_DIR, "python")
DOC_SCRIPT = os.path.join(PY_DIR, "doc_extractor.py")
PDF_SCRIPT = os.path.join(PY_DIR, "pdf_image_extractor_2.py")
IMG_SCRIPT = os.path.join(PY_DIR, "image_extractor_2.py")

INPUT_DIR = os.environ.get("INPUT_DIR", "/data/pdfs/new")
PYTHON_BIN = os.environ.get("PYTHON_BIN", sys.executable)
STATE_FILE = os.environ.get("STATE_FILE", os.path.join(BASE_DIR, ".dispatcher_state.json"))
RECURSIVE = os.environ.get("RECURSIVE", "1") == "1"
FILE_TIMEOUT = int(os.environ.get("FILE_TIMEOUT", "600"))     # seconds per file
IMAGE_BATCH = int(os.environ.get("IMAGE_BATCH", "20"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "3"))
REPROCESS = os.environ.get("REPROCESS", "0") == "1"

DOC_EXT = {".doc", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def classify(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in DOC_EXT:
        return DOC_SCRIPT
    if ext == ".pdf":
        return PDF_SCRIPT
    if ext in IMG_EXT:
        return IMG_SCRIPT
    return None


def signature(path):
    st = os.stat(path)
    return "%d:%d" % (st.st_size, int(st.st_mtime))


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def list_files(root):
    if RECURSIVE:
        for folder, dirs, files in os.walk(root):
            dirs.sort()
            for name in sorted(files):
                if not name.startswith("."):
                    yield os.path.join(folder, name)
    else:
        for name in sorted(os.listdir(root)):
            full = os.path.join(root, name)
            if os.path.isfile(full) and not name.startswith("."):
                yield full


def failure_line(path, message):
    return json.dumps({
        "file_path": path, "filename": os.path.basename(path),
        "doc_id": hashlib.sha1(path.encode("utf-8", "surrogateescape")).hexdigest() + "_0",
        "content": "", "error": message, "doc_type": "unknown",
        "chunk_index": 0, "chunk_total": 1,
    }, ensure_ascii=False)


def run_extractor(script, paths):
    """Run one extractor on `paths`; return list of JSON lines (always >= 1/path)."""
    timeout = FILE_TIMEOUT * len(paths)
    lines, error = [], None
    try:
        done = subprocess.run([PYTHON_BIN, script] + paths, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
        if done.stderr:
            sys.stderr.write(done.stderr.decode("utf-8", "replace"))
        lines = [l for l in done.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
        if done.returncode != 0:
            error = "extractor exit code %d" % done.returncode
    except subprocess.TimeoutExpired:
        error = "timeout after %ds" % timeout
    except Exception as exc:                       # cannot even start
        error = "cannot start extractor: %s" % exc

    seen = set()
    for l in lines:
        try:
            seen.add(json.loads(l).get("file_path"))
        except ValueError:
            pass
    for p in paths:                                # guarantee one record per file
        if p not in seen:
            lines.append(failure_line(p, error or "extractor produced no output"))
    return lines


def dispatch():
    if not os.path.isdir(INPUT_DIR):
        log("Input directory does not exist: %s" % INPUT_DIR)
        return 1

    state = {} if REPROCESS else load_state()
    jobs = {DOC_SCRIPT: [], PDF_SCRIPT: [], IMG_SCRIPT: []}
    skipped = unsupported = 0
    for path in list_files(INPUT_DIR):
        script = classify(path)
        if script is None:
            unsupported += 1
            continue
        entry = state.get(path)
        sig = signature(path)
        if entry and entry.get("sig") == sig and (
                entry.get("status") == "ok" or entry.get("attempts", 0) >= MAX_ATTEMPTS):
            skipped += 1
            continue
        jobs[script].append(path)

    todo = sum(len(v) for v in jobs.values())
    log("scan: %d to process, %d unchanged/skipped, %d unsupported" % (todo, skipped, unsupported))

    t0 = time.time()
    for script, paths in jobs.items():
        step = IMAGE_BATCH if script == IMG_SCRIPT else 1
        for i in range(0, len(paths), step):
            batch = paths[i:i + step]
            log("processing %d file(s) with %s" % (len(batch), os.path.basename(script)))
            lines = run_extractor(script, batch)
            for line in lines:
                print(line, flush=True)
            failed = set()
            for line in lines:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("error"):
                    failed.add(rec.get("file_path"))
            for p in batch:
                old = state.get(p, {})
                if p in failed:
                    state[p] = {"sig": signature(p), "status": "error",
                                "attempts": old.get("attempts", 0) + 1}
                else:
                    state[p] = {"sig": signature(p), "status": "ok", "attempts": 0}
            save_state(state)
    log("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(dispatch())
