# Architecture

## Five layers

1. **Ingestion** - files arrive in `INPUT_DIR`; `main_dispatcher.py` scans it recursively and keeps a state
   file (path + size + mtime) so unchanged files are skipped and failing files are retried a limited number of times.
2. **Extraction / OCR** - routing by extension:

   | Input | Component |
   |---|---|
   | DOC | `doc_extractor.py` + antiword |
   | DOCX | `doc_extractor.py` + docx2txt |
   | XLSX | `doc_extractor.py` + openpyxl (all sheets) |
   | CSV / TXT | `doc_extractor.py` (utf-8, utf-16, cp1256 fallback) |
   | PDF | `pdf_image_extractor_2.py`, **per page**: text layer if present, otherwise Tesseract OCR |
   | JPG/PNG/TIFF/BMP/WEBP | `image_extractor_2.py` (EasyOCR default, Tesseract optional) |

   Tesseract input goes through adaptive preprocessing (`python/ocr_tesseract.py`).
3. **Transport** - Logstash `exec` runs the dispatcher and reads JSON Lines. `doc_id` (SHA-1 of the path + chunk index)
   is the Elasticsearch `_id`, so re-processing a changed file overwrites its old chunks.
4. **Storage / search** - Elasticsearch index `all_extractor` with `content` plus `content.ar` / `content.en` sub-fields.
5. **Visualization** - Kibana: search, and monitoring of `ocr_confidence`, `warning`, `error`, `pages_ocr`.

## Reliability rules

- Every input file produces at least one record, even on failure (`error` field), so nothing disappears silently.
- A hung file is abandoned after `FILE_TIMEOUT` and reported.
- stdout carries JSON only; diagnostics go to stderr.

## Current limitation / scaling

Logstash `exec` is a polling model and returns results after each scan finishes. It is suitable for a single host and
moderate volumes. For very large archives (1 TB+), replace directory scanning with a durable queue, run OCR workers
separately from Logstash and Elasticsearch data nodes, and keep originals in object storage.
