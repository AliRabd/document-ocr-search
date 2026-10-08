#!/usr/bin/env bash
# Smoke test: runs the dispatcher on a tiny folder and checks that EVERY stdout
# line is valid JSON with the required fields (this is what Logstash relies on).
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/in"
printf 'name,city\nAhmed,Riyadh\n' > "$TMP/in/sample.csv"
printf 'broken' > "$TMP/in/broken.xlsx"     # must still produce an error record

echo "1) Python syntax"
"$PYTHON_BIN" -m py_compile "$ROOT"/main_dispatcher.py "$ROOT"/python/*.py
echo "   OK"

echo "2) Dispatcher output must be JSON Lines"
INPUT_DIR="$TMP/in" STATE_FILE="$TMP/state.json" PYTHON_BIN="$PYTHON_BIN" \
  "$PYTHON_BIN" "$ROOT/main_dispatcher.py" > "$TMP/out.jsonl" 2> "$TMP/err.txt"

"$PYTHON_BIN" - "$TMP/out.jsonl" <<'PY'
import json, sys
need = {"file_path", "filename", "doc_id", "content", "chunk_index"}
n = 0
for line in open(sys.argv[1], encoding="utf-8"):
    rec = json.loads(line)
    missing = need - rec.keys()
    assert not missing, "missing fields %s in %s" % (missing, rec)
    n += 1
assert n == 2, "expected 2 records (1 ok + 1 error), got %d" % n
print("   OK - %d valid records" % n)
PY
echo "All checks passed."
