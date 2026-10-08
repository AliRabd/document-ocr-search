#!/usr/bin/env python3
"""Like-for-like comparison of several run_eval outputs.

    python evaluation/compare_runs.py v1=results/legacy/per_file_legacy.csv \
                                      v2=results/auto/per_file_v2.csv

Only files present in EVERY run are compared, so a pipeline that handles more
file types is not unfairly credited (or penalised).
"""
import csv
import sys


def load(path):
    return {r["file"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


def agg(rows):
    n = len(rows)
    ok = [r for r in rows if r["failed"] != "True"]
    f = lambda k, src: sum(float(r[k]) for r in src) / len(src) if src else float("nan")
    return {
        "files": n, "cer": f("cer", ok), "wer": f("wer", ok),
        "empty": sum(r["empty"] == "True" for r in rows) / float(n),
        "failed": sum(r["failed"] == "True" for r in rows) / float(n),
        "sec": f("seconds", rows),
    }


def main(argv):
    runs = [a.split("=", 1) for a in argv]
    data = [(name, load(path)) for name, path in runs]
    common = set.intersection(*[set(d) for _, d in data])
    print("Files compared (present in every run): %d\n" % len(common))
    types = {}
    for f in common:
        types.setdefault(data[0][1][f]["doc_type"], []).append(f)
    header = "| Group | Run | Files | CER | WER | Empty | Failed | s/file |"
    print(header + "\n|---|---|---:|---:|---:|---:|---:|---:|")
    groups = [("ALL", sorted(common))] + sorted(types.items())
    for gname, files in groups:
        for name, d in data:
            a = agg([d[f] for f in files])
            print("| %s | %s | %d | %.2f%% | %.2f%% | %.1f%% | %.1f%% | %.2f |" % (
                gname, name, a["files"], 100 * a["cer"], 100 * a["wer"],
                100 * a["empty"], 100 * a["failed"], a["sec"]))


if __name__ == "__main__":
    main(sys.argv[1:])
