# Data pipeline

```text
Input document -> INPUT_DIR -> main_dispatcher.py
   |- DOC/DOCX/XLSX/CSV/TXT -> doc_extractor.py
   |- PDF                   -> pdf_image_extractor_2.py (per page: text layer or OCR)
   |- image                 -> image_extractor_2.py (EasyOCR / Tesseract)
-> JSON Lines (one object per chunk) -> Logstash exec + json_lines -> Elasticsearch -> Kibana
```

## JSON contract

```json
{
  "doc_id": "<sha1(file_path)>_0",
  "file_path": "/data/pdfs/new/example.pdf",
  "filename": "example.pdf",
  "extension": "pdf",
  "doc_type": "pdf_scanned",
  "ocr_engine": "tesseract",
  "content": "extracted text...",
  "chunk_index": 0,
  "chunk_total": 1,
  "char_count": 1234,
  "word_count": 210,
  "page_count": 3,
  "pages_text_layer": 1,
  "pages_ocr": 2,
  "ocr_confidence": 93.4,
  "extract_seconds": 4.2,
  "truncated": false,
  "processed_at": "2026-10-08T12:00:00+00:00"
}
```

Failures keep the same shape with `"content": ""` and an `"error"` string. Successful-but-empty extractions carry
`"warning": "no_text_extracted"`.

## Why stdout matters

Logstash decodes stdout with `json_lines`, so stdout must contain only JSON. Diagnostics go to stderr.

## Long documents

Text is split into chunks of `CHUNK_CHARS` (default 10 000) at word boundaries; `chunk_index`/`chunk_total` identify them
and nothing is discarded unless the `MAX_CHARS` safety cap (default 1 000 000) is exceeded (`truncated: true`).
Search results can be de-duplicated per file with `collapse` on `filename`.
