# How the pipeline is measured

Every number in the README comes from `evaluation/run_eval.py`, which runs the
**same code path as production** (dispatcher routing + extractor subprocess) on a
set of files that have hand-verified ground truth.

## Metrics

| Metric | Definition | Better |
|---|---|---|
| **CER** | (substitutions + deletions + insertions) / characters in ground truth | lower |
| **WER** | same, counted on words | lower |
| **Character accuracy** | 1 − CER (floored at 0) | higher |
| **Empty-output rate** | files for which nothing readable was extracted | lower |
| **Failure rate** | files whose extraction raised an error / timed out | lower |
| **Seconds per file / p95 / throughput** | wall-clock including process start-up | lower / higher |
| **OCR confidence** | mean word confidence reported by Tesseract / EasyOCR | higher |
| **Field accuracy** | exact match of invoice no., date, total, extracted from the OCR text | higher |
| **hit@k** | share of queries whose expected file is in the top k results | higher |
| **MRR** | mean of 1/rank of the expected file | higher |
| **nDCG@10** | rank-aware gain | higher |
| **Search retention** | MRR on OCR text ÷ MRR on perfect text | higher (1.0 = OCR errors cost nothing) |

CER/WER are computed on whitespace-normalised text. With `--arabic-normalize`
alef variants, taa-marbuta/haa, yaa/alef-maqsura, diacritics and tatweel are
folded first, so harmless spelling variants are not counted as OCR errors.

## Search quality without a cluster

`run_eval.py` builds a small BM25 index over the extracted text (and over the
ground truth) and runs `queries.csv`. Comparing the two isolates the damage that
OCR errors do to search. To measure the real thing — your analyzers, mappings and
cluster — run `evaluation/es_search_eval.py`.

## Test sets

| Set | How | Purpose |
|---|---|---|
| **dev** | `make_samples.py` (seed 42, bundled truth) | used while improving the code |
| **held-out** | `make_samples.py --seed 7 --out /tmp/heldout` | never used for tuning — honest generalisation check |
| **your data** | your files + corrected text | the only numbers that describe *your* documents |

The synthetic sets contain: clean, noisy, heavily noisy, skewed, heavily skewed,
low-resolution, very low-resolution, blurry, heavily blurry, shadowed and heavily
JPEG-compressed images; text PDFs; scanned PDFs; mixed text+scan PDFs; CSV
(UTF-8 and Windows-1256 Arabic); and a two-sheet XLSX.

**Limits to keep in mind:** the pages are clean synthetic text in one font, English
only. Real handwriting, stamps, tables, Arabic photographs and EasyOCR were *not*
measured in the bundled benchmark. Treat the bundled numbers as a regression
test and a method, not as a promise about your production accuracy.

## Evaluating your own documents (recommended)

1. Copy 50–100 representative files into `my_set/samples/` (include bad scans).
2. Create `my_set/samples/truth/<exact file name>.txt` with the correct text.
   Faster: run the extractor once, then correct its output by hand.
3. Create `my_set/manifest.json`:
   ```json
   { "scan001.png": { "truth": "truth/scan001.png.txt",
                      "category": "image_phone", "doc_type": "image", "fields": {} } }
   ```
4. Create `my_set/queries.csv` (`query,expected_file`) with 20–30 real searches.
5. Run:
   ```bash
   python evaluation/run_eval.py --samples my_set/samples --manifest my_set/manifest.json \
       --queries my_set/queries.csv --image-engine easyocr --lang ara+eng --arabic-normalize
   ```
Do not commit private documents to GitHub; commit only the report.

## Quality gate

`evaluation/thresholds.json` sets minimum standards. `run_eval.py` exits with a
non-zero status when one is missed, so CI fails when a change makes OCR worse.
