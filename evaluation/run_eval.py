#!/usr/bin/env python3
"""End-to-end evaluation of the OCR pipeline with measurable metrics.

    python evaluation/run_eval.py                       # v2 pipeline, bundled samples
    python evaluation/run_eval.py --mode legacy         # original v1 logic, same files
    python evaluation/run_eval.py --samples my_set/ --manifest my_set/manifest.json

For every file it runs the real extractor (same code path as production),
then measures:
  * CER / WER / character accuracy vs. ground truth
  * seconds per file, throughput, failure rate, empty-output rate
  * OCR confidence (when the engine reports it)
  * field accuracy (invoice no / date / total) = business-level accuracy
  * search quality: hit@1/3/10, MRR, nDCG, and "search retention"
    (how much of the perfect-text search quality survives OCR errors)
Writes results/summary.json, results/per_file.csv and results/REPORT.md and
exits non-zero when a quality gate in thresholds.json is not met (CI-friendly).
"""
import argparse
import csv
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import metrics as M  # noqa: E402

FIELD_PATTERNS = {
    "invoice_no": re.compile(r"INV-\d{4}-\d{4}"),
    "date": re.compile(r"\b20\d\d-\d\d-\d\d\b"),
    "total": re.compile(r"Total:\s*([\d,]+\.\d\d)"),
}


# ------------------------------------------------------------------ extractors
def run_v2(path, dispatcher):
    """Production code path: dispatcher routing + extractor subprocess."""
    script = dispatcher.classify(path)
    if script is None:
        return None
    start = time.time()
    lines = dispatcher.run_extractor(script, [path])
    wall = time.time() - start
    recs = []
    for line in lines:
        try:
            recs.append(json.loads(line))
        except ValueError:
            pass
    recs.sort(key=lambda r: r.get("chunk_index", 0))
    text = "\n".join(r.get("content", "") for r in recs)
    errors = [r["error"] for r in recs if r.get("error")]
    conf = next((r["ocr_confidence"] for r in recs if r.get("ocr_confidence") is not None), None)
    return {"text": text, "seconds": wall, "error": errors[0] if errors else None,
            "confidence": conf, "emitted": bool(recs)}


def run_legacy(path, lang):
    """Re-creation of the ORIGINAL v1 behaviour using the same tools.

    v1 routing: .csv -> utf-8-sig only; PDF with ANY text page -> pdftotext
    (scanned pages ignored); PDF without text -> Tesseract 250 dpi, no
    preprocessing; failures from OCR scripts never reach Logstash.
    Images (EasyOCR) and xlsx (xlsx2csv) cannot be re-run here -> skipped.
    """
    ext = os.path.splitext(path)[1].lower()
    start = time.time()
    if ext == ".csv":
        try:
            import csv as _csv
            with open(path, newline="", encoding="utf-8-sig") as h:
                text = "\n".join(", ".join(r) for r in _csv.reader(h))
            err = None
        except Exception as exc:
            text, err = "[ERROR] Failed to process: %s" % exc, str(exc)
        return {"text": text, "seconds": time.time() - start, "error": err,
                "confidence": None, "emitted": True}
    if ext == ".pdf":
        pages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(
            ["pdfinfo", path], stdout=subprocess.PIPE).stdout.decode()).group(1))
        has_text = any(subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), path, "-"],
                                      stdout=subprocess.PIPE).stdout.strip()
                       for p in range(1, pages + 1))
        if has_text:
            text = subprocess.run(["pdftotext", path, "-"], stdout=subprocess.PIPE).stdout.decode("utf-8", "replace")
        else:
            import io
            import pytesseract
            from PIL import Image
            out = []
            for p in range(1, pages + 1):
                png = subprocess.run(["pdftoppm", "-r", "250", "-f", str(p), "-l", str(p), "-png", path],
                                     stdout=subprocess.PIPE).stdout
                out.append(pytesseract.image_to_string(Image.open(io.BytesIO(png)).convert("RGB"), lang=lang).strip())
            text = "\n\n".join(out)
        return {"text": text, "seconds": time.time() - start, "error": None,
                "confidence": None, "emitted": True}
    return None


# --------------------------------------------------------------------- helpers
def pct(x):
    return "%.2f%%" % (100.0 * x)


def mean(v):
    return sum(v) / len(v) if v else None


def p95(v):
    if not v:
        return None
    s = sorted(v)
    return s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]


def extract_fields(text):
    out = {}
    for k, pat in FIELD_PATTERNS.items():
        m = pat.search(text)
        out[k] = (m.group(1) if m and m.groups() else (m.group(0) if m else ""))
    return out


def aggregate(rows):
    ok = [r for r in rows if not r["failed"]]
    return {
        "files": len(rows),
        "cer": mean([r["cer"] for r in ok]),
        "wer": mean([r["wer"] for r in ok]),
        "char_accuracy": mean([r["char_accuracy"] for r in ok]),
        "median_cer": statistics.median([r["cer"] for r in ok]) if ok else None,
        "avg_confidence": mean([r["confidence"] for r in ok if r["confidence"] is not None]),
        "avg_seconds": mean([r["seconds"] for r in rows]),
        "p95_seconds": p95([r["seconds"] for r in rows]),
        "failure_rate": sum(r["failed"] for r in rows) / float(len(rows)) if rows else None,
        "empty_rate": sum(r["empty"] for r in rows) / float(len(rows)) if rows else None,
    }


def table(title, groups):
    lines = ["### %s" % title, "",
             "| Group | Files | CER | WER | Char acc. | Conf. | s/file | Failed |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, a in sorted(groups.items()):
        lines.append("| %s | %d | %s | %s | %s | %s | %.2f | %s |" % (
            name, a["files"],
            pct(a["cer"]) if a["cer"] is not None else "-",
            pct(a["wer"]) if a["wer"] is not None else "-",
            pct(a["char_accuracy"]) if a["char_accuracy"] is not None else "-",
            "%.1f" % a["avg_confidence"] if a["avg_confidence"] is not None else "-",
            a["avg_seconds"] or 0, pct(a["failure_rate"] or 0)))
    return lines + [""]


# ------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", default=os.path.join(HERE, "samples"))
    ap.add_argument("--manifest", default=os.path.join(HERE, "manifest.json"))
    ap.add_argument("--queries", default=os.path.join(HERE, "queries.csv"))
    ap.add_argument("--mode", choices=["v2", "legacy"], default="v2")
    ap.add_argument("--image-engine", default="tesseract", choices=["tesseract", "easyocr"])
    ap.add_argument("--lang", default="eng", help="Tesseract language(s), e.g. ara+eng")
    ap.add_argument("--arabic-normalize", action="store_true",
                    help="fold Arabic letter variants before scoring (use for Arabic sets)")
    ap.add_argument("--thresholds", default=os.path.join(HERE, "thresholds.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("--no-gate", action="store_true")
    args = ap.parse_args()

    os.environ["IMAGE_OCR_ENGINE"] = args.image_engine
    os.environ["OCR_LANG"] = args.lang
    os.environ.setdefault("OCR_DPI", "250")
    os.makedirs(args.out, exist_ok=True)

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    base = args.samples          # manifest "truth" paths are relative to the samples folder

    dispatcher = None
    if args.mode == "v2":
        import main_dispatcher as dispatcher  # noqa: E402

    rows, ocr_docs, truth_docs, truth_fields, ocr_fields = [], {}, {}, [], []
    skipped = []
    for name in sorted(manifest):
        info = manifest[name]
        path = os.path.join(args.samples, name)
        truth = open(os.path.join(base, info["truth"]), encoding="utf-8").read()
        res = run_v2(path, dispatcher) if args.mode == "v2" else run_legacy(path, args.lang)
        if res is None:
            skipped.append(name)
            continue
        text = res["text"]
        failed = bool(res["error"]) or not res["emitted"]
        empty = not text.strip() or text.startswith("[ERROR]")
        sc = M.ocr_scores(truth, "" if failed else text, arabic=args.arabic_normalize)
        rows.append({"file": name, "doc_type": info["doc_type"], "category": info["category"],
                     "cer": sc["cer"], "wer": sc["wer"], "char_accuracy": sc["char_accuracy"],
                     "ref_chars": sc["ref_chars"], "confidence": res["confidence"],
                     "seconds": res["seconds"], "failed": failed, "empty": empty,
                     "error": res["error"] or ""})
        ocr_docs[name] = "" if failed else text
        truth_docs[name] = truth
        if info.get("fields"):
            truth_fields.append(dict(info["fields"], file=name))
            ocr_fields.append(dict(extract_fields(text), file=name))
        print("  %-34s CER %6.2f%%  %5.2fs%s" % (name, 100 * sc["cer"], res["seconds"],
                                                 "  FAILED" if failed else ""), file=sys.stderr)

    # ----- aggregates
    overall = aggregate(rows)
    total_secs = sum(r["seconds"] for r in rows)
    overall["throughput_files_per_min"] = 60.0 * len(rows) / total_secs if total_secs else None
    by_type, by_cat = defaultdict(list), defaultdict(list)
    for r in rows:
        by_type[r["doc_type"]].append(r)
        by_cat[r["category"]].append(r)
    by_type = {k: aggregate(v) for k, v in by_type.items()}
    by_cat = {k: aggregate(v) for k, v in by_cat.items()}

    # ----- field accuracy
    fields = M.field_accuracy(truth_fields, ocr_fields, ["invoice_no", "date", "total"]) if truth_fields else {}
    field_avg = mean(list(fields.values())) if fields else None

    # ----- search quality (offline BM25 over the extracted text)
    search = {}
    if os.path.exists(args.queries):
        qs = [r for r in csv.DictReader(open(args.queries, encoding="utf-8"))
              if r["expected_file"] in ocr_docs]
        for label, docs in (("ocr", ocr_docs), ("ground_truth", truth_docs)):
            idx = M.BM25(docs)
            results = [idx.search(q["query"], 10) for q in qs]
            search[label] = M.search_metrics(results, [{q["expected_file"]} for q in qs])
        if search["ground_truth"].get("mrr"):
            search["retention_mrr"] = search["ocr"]["mrr"] / search["ground_truth"]["mrr"]
        if search["ground_truth"].get("hit@10"):
            search["retention_hit@10"] = search["ocr"]["hit@10"] / search["ground_truth"]["hit@10"]

    summary = {
        "date": str(date.today()), "mode": args.mode, "image_engine": args.image_engine,
        "tesseract_lang": args.lang, "files_evaluated": len(rows), "files_skipped": skipped,
        "overall": overall, "by_doc_type": by_type, "by_category": by_cat,
        "field_accuracy": fields, "field_accuracy_avg": field_avg, "search": search,
        "environment": {"python": platform.python_version(),
                        "tesseract": subprocess.run(["tesseract", "--version"], stdout=subprocess.PIPE,
                                                    stderr=subprocess.STDOUT).stdout.decode().splitlines()[0]},
    }

    # ----- gate
    gate = []
    if os.path.exists(args.thresholds) and args.mode == "v2" and not args.no_gate:
        th = json.load(open(args.thresholds))
        checks = [
            ("CER", overall["cer"], "max_cer", "<="), ("WER", overall["wer"], "max_wer", "<="),
            ("Failure rate", overall["failure_rate"], "max_failure_rate", "<="),
            ("Empty-output rate", overall["empty_rate"], "max_empty_rate", "<="),
            ("Avg seconds/file", overall["avg_seconds"], "max_avg_seconds", "<="),
            ("Field accuracy", field_avg, "min_field_accuracy", ">="),
            ("Search hit@10", search.get("ocr", {}).get("hit@10"), "min_hit_at_10", ">="),
            ("Search MRR", search.get("ocr", {}).get("mrr"), "min_mrr", ">="),
            ("Search retention (MRR)", search.get("retention_mrr"), "min_search_retention", ">="),
        ]
        for label, val, key, op in checks:
            if key in th and val is not None:
                passed = val <= th[key] if op == "<=" else val >= th[key]
                gate.append({"metric": label, "value": val, "threshold": th[key], "op": op, "passed": passed})
    summary["quality_gate"] = gate

    json.dump(summary, open(os.path.join(args.out, "summary_%s.json" % args.mode), "w"), indent=2, default=str)
    with open(os.path.join(args.out, "per_file_%s.csv" % args.mode), "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ----- markdown report
    L = ["# OCR pipeline evaluation (%s)" % ("v2 - improved" if args.mode == "v2" else "v1 - original logic"), "",
         "Date: %s · Files scored: %d · Image engine: %s · Tesseract lang: %s" % (
             summary["date"], len(rows), args.image_engine, args.lang),
         "Environment: %s, Python %s" % (summary["environment"]["tesseract"], summary["environment"]["python"]), "",
         "## Headline metrics", "",
         "| Metric | Value |", "|---|---:|",
         "| Character error rate (CER) | %s |" % pct(overall["cer"]),
         "| Word error rate (WER) | %s |" % pct(overall["wer"]),
         "| Character accuracy | %s |" % pct(overall["char_accuracy"]),
         "| Failure rate | %s |" % pct(overall["failure_rate"]),
         "| Empty-output rate | %s |" % pct(overall["empty_rate"]),
         "| Avg seconds / file | %.2f |" % overall["avg_seconds"],
         "| p95 seconds / file | %.2f |" % overall["p95_seconds"],
         "| Throughput | %.1f files/min |" % (overall["throughput_files_per_min"] or 0)]
    if field_avg is not None:
        L.append("| Field accuracy (invoice no / date / total) | %s |" % pct(field_avg))
    if search:
        L += ["| Search hit@1 / hit@3 / hit@10 | %s / %s / %s |" % (
            pct(search["ocr"]["hit@1"]), pct(search["ocr"]["hit@3"]), pct(search["ocr"]["hit@10"])),
            "| Search MRR | %.3f (perfect text: %.3f) |" % (search["ocr"]["mrr"], search["ground_truth"]["mrr"]),
            "| Search retention (MRR) | %s |" % pct(search.get("retention_mrr", 0))]
    L.append("")
    if fields:
        L += ["### Field accuracy", "", "| Field | Exact match |", "|---|---:|"]
        L += ["| %s | %s |" % (k, pct(v)) for k, v in fields.items()] + [""]
    L += table("By document type", by_type) + table("By image condition / category", by_cat)
    worst = sorted(rows, key=lambda r: -r["cer"])[:5]
    L += ["### Five hardest files", "", "| File | CER | Failed |", "|---|---:|---|"]
    L += ["| %s | %s | %s |" % (r["file"], pct(r["cer"]), "yes" if r["failed"] else "") for r in worst] + [""]
    if skipped:
        L += ["_Not run in this mode: %s_" % ", ".join(skipped), ""]
    if gate:
        L += ["## Quality gate", "", "| Metric | Value | Threshold | Result |", "|---|---:|---:|:--:|"]
        for g in gate:
            fmt = (lambda x: "%.3f" % x) if g["metric"].startswith(("Avg", "Search MRR")) else pct
            L.append("| %s | %s | %s %s | %s |" % (g["metric"], fmt(g["value"]), g["op"], fmt(g["threshold"]),
                                                    "PASS" if g["passed"] else "**FAIL**"))
        L.append("")
    open(os.path.join(args.out, "REPORT_%s.md" % args.mode), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))
    return 0 if all(g["passed"] for g in gate) else 1


if __name__ == "__main__":
    sys.exit(main())
