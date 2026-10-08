# Document OCR Search Pipeline

Ingest **DOC / DOCX / XLSX / CSV / TXT / PDF (text, scanned, or mixed) / images**
into **Elasticsearch** (via **Logstash**) for search in **Kibana** — with Arabic + English
support and a built-in, reproducible **evaluation suite** that measures OCR accuracy,
speed and search quality.

![python](https://img.shields.io/badge/python-3.8%2B-blue) ![tests](https://img.shields.io/badge/tests-23%20passing-brightgreen)

## Measured results

Same files, same machine (Tesseract 5.3.4). Full tables: [`evaluation/results/COMPARISON.md`](evaluation/results/COMPARISON.md).

**Like-for-like on the 13 PDF/CSV files the original v1 code can process:**

| | v1 (original) | v2 | Change |
|---|---:|---:|---|
| Character error rate (dev set) | 35.4% | **0.04%** | ~99.9% lower |
| Character error rate (**held-out** set) | 31.9% | **4.1%** | ~87% lower |
| Files with empty output | 23% | **0%** | |
| Files that errored (the Arabic CSV) | 7.7% | **0%** | |
| Mixed text+scan PDFs (CER) | 64% | **0%** | scanned pages were ignored in v1 |

**New pipeline on all 36 files (22 images, 3 text PDFs, 6 scanned PDFs, 2 mixed PDFs, CSV, XLSX):**

| Metric | Dev set | Held-out set |
|---|---:|---:|
| CER / WER | 1.13% / 2.95% | 2.26% / 4.27% |
| Empty-output rate | 0% | 0% |
| Field accuracy (invoice no., date, total) | 93.8% | 97.9% |
| Search hit@10 / MRR | 98.2% / 0.81 | 100% / 0.82 |
| Search retention (MRR vs. perfect text) | 97.8% | 100% |
| Avg seconds per file | 4.95 | 4.85 |

The **held-out** set was generated with a different seed and was *not* used while tuning the
code — it is the honest number. The dev numbers are better because the preprocessing was
developed against that set.

**Still weak (reported, not hidden):** very blurry pages (CER 11–21% on the worst), heavily
skewed *short* scanned letters (one held-out page at 53% CER), and heavily noisy pages that
cost ~24 s each (a 20 s first-pass timeout before the retry — tunable via `OCR_FIRST_TIMEOUT`).

> These benchmarks use **synthetic English pages** so they can be published safely. They
> are a regression test and a method, not a promise about your documents. To measure *your*
> accuracy (Arabic photos, EasyOCR, handwriting), follow [docs/EVALUATION.md](docs/EVALUATION.md).

## What changed from v1

| # | Problem in v1 | Fix in v2 |
|---|---|---|
| 1 | `requirements.txt` was git-ignored (`*.txt`), so it never reached GitHub | `.gitignore` corrected |
| 2 | OCR failures exited non-zero and the dispatcher dropped them — files silently missing from Kibana | every file always produces a record; failures carry an `error` field |
| 3 | Arabic CSV (Windows-1256) crashed with a UTF-8 error | encoding fallback (utf-8-sig → utf-16 → cp1256 → latin-1) |
| 4 | PDF with *any* text page was never OCR'd — scanned pages lost | decided **per page**: text layer when present, OCR otherwise |
| 5 | Every file re-processed every 5 minutes | state file skips unchanged files (path + size + mtime); retries capped |
| 6 | One stuck file blocked the pipeline forever | per-file timeout, reported as an error record |
| 7 | Text silently cut at 10 000 chars, `[...truncated...]` marker became searchable | long text is split into **chunks** (nothing lost); `truncated` flag if the safety cap is hit |
| 8 | XLSX: first sheet only | all sheets |
| 9 | `[ERROR] ...` text was written into the searchable `content` | errors only in the `error` field |
| 10 | Raw file path as Elasticsearch `_id` (512-byte limit, Arabic = 2 bytes/char) | SHA-1 of the path + chunk index |
| 11 | EasyOCR model reloaded for every image | images processed in batches |
| 12 | No image clean-up (phone photos sideways, shadows, noise) | EXIF rotation + adaptive preprocessing (shadow removal, denoise, deskew, upscale) |
| 13 | Default analyzer for Arabic | `content.ar` (Arabic analyzer) and `content.en` sub-fields; NFKC normalisation |
| 14 | Logstash `grok` could make `filename` an array; no ES authentication | grok removed; HTTPS + user/password/CA via environment variables |
| 15 | Hard-coded `/root/...` paths and an internal IP in the repo | environment variables / placeholders only |
| 16 | `test_json_output.sh` only compiled the code | real smoke test + 23 regression tests + CI quality gate |

## Architecture

```text
INPUT_DIR (scanned recursively)
        |
        v
main_dispatcher.py  --- state file: skip unchanged files, cap retries, per-file timeout
        |
        +--> doc_extractor.py          DOC/DOCX/XLSX/CSV/TXT (+ text PDF fallback)
        +--> pdf_image_extractor_2.py  PDF, page by page: text layer or Tesseract OCR
        +--> image_extractor_2.py      images: EasyOCR (default) or Tesseract
        |
        v   JSON Lines on stdout (one record per chunk; diagnostics on stderr)
Logstash exec + json_lines  ->  Elasticsearch (index all_extractor)  ->  Kibana
```

Record fields: `doc_id, file_path, filename, extension, doc_type, ocr_engine, content,
chunk_index, chunk_total, char_count, word_count, page_count, pages_text_layer, pages_ocr,
ocr_confidence, extract_seconds, truncated, warning, error, modified, processed_at`.
Because these fields are indexed, quality can be monitored in Kibana (e.g. average
`ocr_confidence` per `doc_type`, count of documents with `error`/`warning`).

## Quick start

```bash
git clone https://github.com/AliRabd/document-ocr-search.git && cd document-ocr-search
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
sudo apt install tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng poppler-utils antiword   # Debian/Ubuntu
# CentOS/RHEL: sudo dnf install tesseract tesseract-langpack-ara tesseract-langpack-eng poppler-utils antiword

INPUT_DIR=/path/to/docs python main_dispatcher.py > out.jsonl   # JSON Lines, ready for Logstash
```

### Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `INPUT_DIR` | `/data/pdfs/new` | folder scanned (recursively) |
| `STATE_FILE` | `./.dispatcher_state.json` | remembers processed files |
| `FILE_TIMEOUT` | 600 | seconds before a file is abandoned |
| `MAX_ATTEMPTS` | 3 | retries for a failing file |
| `REPROCESS` | 0 | `1` ignores the state file |
| `OCR_LANG` | `ara+eng` | Tesseract languages (missing ones are skipped with a warning) |
| `OCR_DPI` | 250 | PDF rendering resolution |
| `OCR_PREPROCESS` | `auto` | `off` / `basic` / `auto` (retry with enhanced preprocessing) |
| `OCR_FIRST_TIMEOUT` | 20 | seconds for the first OCR pass before the enhanced retry |
| `IMAGE_OCR_ENGINE` | `easyocr` | `easyocr` or `tesseract` |
| `CHUNK_CHARS` / `MAX_CHARS` | 10000 / 1000000 | chunk size / per-file safety cap |

Copy `.env.example` to `.env` for the server. **Never commit `.env`.**

### Logstash / Elasticsearch

1. Put `logstash/pipelines/document_ingestion.conf` in `/etc/logstash/conf.d/`.
2. Set `ES_HOST`, `ES_USER`, `ES_PASSWORD`, `ES_CA_CERT` for the Logstash service
   (or use the Logstash keystore for the password).
3. Apply `elasticsearch/index-template.json` (index template API) **before** the first run.
4. Validate and restart:
   ```bash
   sudo /usr/share/logstash/bin/logstash --path.settings /etc/logstash -t -f /etc/logstash/conf.d/document_ingestion.conf
   sudo systemctl restart logstash
   ```
5. Run Logstash as the `logstash` user with the venv in a path it can read (e.g. `/opt/ocr/venv`), not under `/root`.

## Test and evaluate

```bash
pip install -r requirements-eval.txt
python -m unittest discover -s tests -v      # 23 tests
bash scripts/test_json_output.sh             # smoke test of the JSON contract
python evaluation/make_samples.py            # regenerate the synthetic sample set (seeded)
python evaluation/run_eval.py                # metrics + report + quality gate (exit 1 on regression)
python evaluation/make_samples.py --seed 7 --out /tmp/heldout   # honest held-out check
python evaluation/run_eval.py --samples /tmp/heldout/samples --manifest /tmp/heldout/manifest.json \
       --queries /tmp/heldout/queries.csv --no-gate
```

Search quality on the **real** cluster (your analyzers and mappings):

```bash
export ES_USER=elastic ES_PASSWORD='...'
python evaluation/es_search_eval.py --es-url https://ES_HOST:9200 --ca-cert /path/to/http_ca.crt
```

Metric definitions, how to build your own ground-truth set, and the limits of the bundled
benchmark are in [docs/EVALUATION.md](docs/EVALUATION.md). GitHub Actions runs the tests and
the quality gate on every push ([.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Known limitations

- **Not benchmarked here:** EasyOCR (Arabic/English photos), Arabic OCR accuracy, handwriting,
  tables, `.doc`/`.docx` extraction (needs `antiword` / `docx2txt`, not installed in the benchmark setup).
  Measure these on your own data with the evaluation suite.
- `es_search_eval.py` was tested against a stand-in HTTP server, not a real cluster; check the
  first run against Kibana.
- Logstash `exec` collects a run's output after the command ends, so documents appear at the end
  of each scan. The state file keeps scans short, but for very large archives (1 TB+) use a queue and
  separate OCR workers (see [docs/architecture.md](docs/architecture.md)).
- PyMuPDF was not installed in the benchmark setup; the PDF code falls back to poppler
  (`pdftotext`/`pdftoppm`), which is what was measured. The PyMuPDF path is the same logic but untested here.

## Repository layout

```text
main_dispatcher.py            scan, route, state, timeouts
python/                       common.py, doc_extractor.py, pdf_image_extractor_2.py,
                              image_extractor_2.py, ocr_tesseract.py
logstash/                     pipeline + logstash.yml.example
elasticsearch/                index template (Arabic/English sub-fields)
evaluation/                   metrics, sample generator, run_eval, compare_runs, es_search_eval,
                              thresholds.json, results/ (committed baseline reports)
tests/                        23 unit/regression tests
scripts/test_json_output.sh   JSON contract smoke test
docs/                         architecture, pipeline, evaluation
```
