# OCR pipeline evaluation (v2 - improved)

Date: 2026-10-08 · Files scored: 36 · Image engine: tesseract · Tesseract lang: eng
Environment: tesseract 5.3.4, Linux

## Headline metrics

| Metric | Value |
|---|---:|
| Character error rate (CER) | 1.13% |
| Word error rate (WER) | 2.95% |
| Character accuracy | 98.87% |
| Failure rate | 0.00% |
| Empty-output rate | 0.00% |
| Avg seconds / file | 4.91 |
| p95 seconds / file | 19.97 |
| Throughput | 12.2 files/min |
| Field accuracy (invoice no / date / total) | 93.75% |
| Search hit@1 / hit@3 / hit@10 | 66.67% / 98.15% / 98.15% |
| Search MRR | 0.806 (perfect text: 0.824) |
| Search retention (MRR) | 97.75% |

### Field accuracy

| Field | Exact match |
|---|---:|
| invoice_no | 93.75% |
| date | 93.75% |
| total | 93.75% |

### By document type

| Group | Files | CER | WER | Char acc. | Conf. | s/file | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| csv | 2 | 0.00% | 0.00% | 100.00% | - | 0.05 | 0.00% |
| excel | 1 | 0.00% | 0.00% | 100.00% | - | 0.31 | 0.00% |
| image | 22 | 1.83% | 4.75% | 98.17% | 92.7 | 4.84 | 0.00% |
| pdf_mixed | 2 | 0.00% | 0.00% | 100.00% | 95.5 | 3.82 | 0.00% |
| pdf_scanned | 6 | 0.09% | 0.29% | 99.91% | 95.3 | 10.36 | 0.00% |
| pdf_text | 3 | 0.00% | 0.00% | 100.00% | - | 0.09 | 0.00% |

### By image condition / category

| Group | Files | CER | WER | Char acc. | Conf. | s/file | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| csv | 1 | 0.00% | 0.00% | 100.00% | - | 0.04 | 0.00% |
| csv_arabic | 1 | 0.00% | 0.00% | 100.00% | - | 0.05 | 0.00% |
| image_blurry | 2 | 0.00% | 0.00% | 100.00% | 94.8 | 2.46 | 0.00% |
| image_blurry_heavy | 2 | 7.46% | 31.16% | 92.54% | 80.6 | 5.66 | 0.00% |
| image_clean | 2 | 0.00% | 0.00% | 100.00% | 95.0 | 2.55 | 0.00% |
| image_jpeg_low | 2 | 0.00% | 0.00% | 100.00% | 95.0 | 2.35 | 0.00% |
| image_lowres | 2 | 0.00% | 0.00% | 100.00% | 94.7 | 1.99 | 0.00% |
| image_lowres_heavy | 2 | 0.00% | 0.00% | 100.00% | 92.0 | 3.62 | 0.00% |
| image_noisy | 2 | 0.00% | 0.00% | 100.00% | 95.2 | 3.48 | 0.00% |
| image_noisy_heavy | 2 | 0.00% | 0.00% | 100.00% | 94.8 | 21.60 | 0.00% |
| image_shadow | 2 | 0.00% | 0.00% | 100.00% | 94.6 | 3.94 | 0.00% |
| image_skewed | 2 | 0.00% | 0.00% | 100.00% | 95.5 | 2.66 | 0.00% |
| image_skewed_heavy | 2 | 12.64% | 21.05% | 87.36% | 87.7 | 2.86 | 0.00% |
| pdf_mixed | 2 | 0.00% | 0.00% | 100.00% | 95.5 | 3.82 | 0.00% |
| pdf_scanned | 6 | 0.09% | 0.29% | 99.91% | 95.3 | 10.36 | 0.00% |
| pdf_text | 3 | 0.00% | 0.00% | 100.00% | - | 0.09 | 0.00% |
| xlsx | 1 | 0.00% | 0.00% | 100.00% | - | 0.31 | 0.00% |

### Five hardest files

| File | CER | Failed |
|---|---:|---|
| letter_skewed_heavy_09.png | 25.27% |  |
| invoice_blurry_heavy_16.png | 11.11% |  |
| letter_blurry_heavy_17.png | 3.81% |  |
| letter_scanpdf_noisy_heavy_28.pdf | 0.55% |  |
| invoice_blurry_14.png | 0.00% |  |

## Quality gate

| Metric | Value | Threshold | Result |
|---|---:|---:|:--:|
| CER | 1.13% | <= 3.00% | PASS |
| WER | 2.95% | <= 6.00% | PASS |
| Failure rate | 0.00% | <= 0.00% | PASS |
| Empty-output rate | 0.00% | <= 2.00% | PASS |
| Avg seconds/file | 4.911 | <= 10.000 | PASS |
| Field accuracy | 93.75% | >= 85.00% | PASS |
| Search hit@10 | 98.15% | >= 90.00% | PASS |
| Search MRR | 0.806 | >= 0.700 | PASS |
| Search retention (MRR) | 97.75% | >= 90.00% | PASS |
