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
| Avg seconds / file | 4.95 |
| p95 seconds / file | 20.25 |
| Throughput | 12.1 files/min |
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
| excel | 1 | 0.00% | 0.00% | 100.00% | - | 0.32 | 0.00% |
| image | 22 | 1.83% | 4.75% | 98.17% | 92.7 | 4.89 | 0.00% |
| pdf_mixed | 2 | 0.00% | 0.00% | 100.00% | 95.5 | 3.94 | 0.00% |
| pdf_scanned | 6 | 0.09% | 0.29% | 99.91% | 95.3 | 10.33 | 0.00% |
| pdf_text | 3 | 0.00% | 0.00% | 100.00% | - | 0.09 | 0.00% |

### By image condition / category

| Group | Files | CER | WER | Char acc. | Conf. | s/file | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| csv | 1 | 0.00% | 0.00% | 100.00% | - | 0.05 | 0.00% |
| csv_arabic | 1 | 0.00% | 0.00% | 100.00% | - | 0.04 | 0.00% |
| image_blurry | 2 | 0.00% | 0.00% | 100.00% | 94.8 | 2.55 | 0.00% |
| image_blurry_heavy | 2 | 7.46% | 31.16% | 92.54% | 80.6 | 5.63 | 0.00% |
| image_clean | 2 | 0.00% | 0.00% | 100.00% | 95.0 | 2.48 | 0.00% |
| image_jpeg_low | 2 | 0.00% | 0.00% | 100.00% | 95.0 | 2.67 | 0.00% |
| image_lowres | 2 | 0.00% | 0.00% | 100.00% | 94.7 | 2.09 | 0.00% |
| image_lowres_heavy | 2 | 0.00% | 0.00% | 100.00% | 92.0 | 3.84 | 0.00% |
| image_noisy | 2 | 0.00% | 0.00% | 100.00% | 95.2 | 3.50 | 0.00% |
| image_noisy_heavy | 2 | 0.00% | 0.00% | 100.00% | 94.8 | 21.91 | 0.00% |
| image_shadow | 2 | 0.00% | 0.00% | 100.00% | 94.6 | 3.86 | 0.00% |
| image_skewed | 2 | 0.00% | 0.00% | 100.00% | 95.5 | 2.53 | 0.00% |
| image_skewed_heavy | 2 | 12.64% | 21.05% | 87.36% | 87.7 | 2.72 | 0.00% |
| pdf_mixed | 2 | 0.00% | 0.00% | 100.00% | 95.5 | 3.94 | 0.00% |
| pdf_scanned | 6 | 0.09% | 0.29% | 99.91% | 95.3 | 10.33 | 0.00% |
| pdf_text | 3 | 0.00% | 0.00% | 100.00% | - | 0.09 | 0.00% |
| xlsx | 1 | 0.00% | 0.00% | 100.00% | - | 0.32 | 0.00% |

### Five hardest files

| File | CER | Failed |
|---|---:|---|
| letter_skewed_heavy_09.png | 25.27% |  |
| invoice_blurry_heavy_16.png | 11.11% |  |
| letter_blurry_heavy_17.png | 3.81% |  |
| letter_scanpdf_noisy_heavy_28.pdf | 0.55% |  |
| invoice_blurry_14.png | 0.00% |  |
