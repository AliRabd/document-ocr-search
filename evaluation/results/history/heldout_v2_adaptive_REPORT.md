# OCR pipeline evaluation (v2 - improved)

Date: 2026-10-08 · Files scored: 36 · Image engine: tesseract · Tesseract lang: eng
Environment: tesseract 5.3.4, Linux

## Headline metrics

| Metric | Value |
|---|---:|
| Character error rate (CER) | 2.26% |
| Word error rate (WER) | 4.27% |
| Character accuracy | 97.74% |
| Failure rate | 0.00% |
| Empty-output rate | 0.00% |
| Avg seconds / file | 4.85 |
| p95 seconds / file | 23.53 |
| Throughput | 12.4 files/min |
| Field accuracy (invoice no / date / total) | 97.92% |
| Search hit@1 / hit@3 / hit@10 | 68.52% / 100.00% / 100.00% |
| Search MRR | 0.824 (perfect text: 0.824) |
| Search retention (MRR) | 100.00% |

### Field accuracy

| Field | Exact match |
|---|---:|
| invoice_no | 100.00% |
| date | 100.00% |
| total | 93.75% |

### By document type

| Group | Files | CER | WER | Char acc. | Conf. | s/file | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| csv | 2 | 0.00% | 0.00% | 100.00% | - | 0.05 | 0.00% |
| excel | 1 | 0.00% | 0.00% | 100.00% | - | 0.32 | 0.00% |
| image | 22 | 1.26% | 3.91% | 98.74% | 93.0 | 4.92 | 0.00% |
| pdf_mixed | 2 | 0.00% | 0.00% | 100.00% | 95.3 | 3.78 | 0.00% |
| pdf_scanned | 6 | 8.91% | 11.31% | 91.09% | 94.5 | 9.69 | 0.00% |
| pdf_text | 3 | 0.00% | 0.00% | 100.00% | - | 0.07 | 0.00% |

### By image condition / category

| Group | Files | CER | WER | Char acc. | Conf. | s/file | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| csv | 1 | 0.00% | 0.00% | 100.00% | - | 0.04 | 0.00% |
| csv_arabic | 1 | 0.00% | 0.00% | 100.00% | - | 0.05 | 0.00% |
| image_blurry | 2 | 0.00% | 0.00% | 100.00% | 94.5 | 2.54 | 0.00% |
| image_blurry_heavy | 2 | 12.75% | 35.34% | 87.25% | 79.3 | 4.42 | 0.00% |
| image_clean | 2 | 0.00% | 0.00% | 100.00% | 94.8 | 2.57 | 0.00% |
| image_jpeg_low | 2 | 0.00% | 0.00% | 100.00% | 95.0 | 2.45 | 0.00% |
| image_lowres | 2 | 0.00% | 0.00% | 100.00% | 95.0 | 1.88 | 0.00% |
| image_lowres_heavy | 2 | 0.66% | 4.31% | 99.34% | 93.3 | 3.54 | 0.00% |
| image_noisy | 2 | 0.25% | 1.67% | 99.75% | 94.2 | 3.47 | 0.00% |
| image_noisy_heavy | 2 | 0.24% | 1.67% | 99.76% | 93.4 | 23.82 | 0.00% |
| image_shadow | 2 | 0.00% | 0.00% | 100.00% | 94.3 | 3.53 | 0.00% |
| image_skewed | 2 | 0.00% | 0.00% | 100.00% | 94.5 | 2.35 | 0.00% |
| image_skewed_heavy | 2 | 0.00% | 0.00% | 100.00% | 94.7 | 3.54 | 0.00% |
| pdf_mixed | 2 | 0.00% | 0.00% | 100.00% | 95.3 | 3.78 | 0.00% |
| pdf_scanned | 6 | 8.91% | 11.31% | 91.09% | 94.5 | 9.69 | 0.00% |
| pdf_text | 3 | 0.00% | 0.00% | 100.00% | - | 0.07 | 0.00% |
| xlsx | 1 | 0.00% | 0.00% | 100.00% | - | 0.32 | 0.00% |

### Five hardest files

| File | CER | Failed |
|---|---:|---|
| letter_scanpdf_skewed_heavy_29.pdf | 53.46% |  |
| invoice_blurry_heavy_16.png | 21.32% |  |
| letter_blurry_heavy_17.png | 4.18% |  |
| invoice_lowres_heavy_12.png | 1.04% |  |
| invoice_noisy_02.png | 0.50% |  |
