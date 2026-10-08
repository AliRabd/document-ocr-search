# OCR pipeline evaluation (v1 - original logic)

Date: 2026-10-08 · Files scored: 13 · Image engine: tesseract · Tesseract lang: eng
Environment: tesseract 5.3.4, Linux

## Headline metrics

| Metric | Value |
|---|---:|
| Character error rate (CER) | 35.36% |
| Word error rate (WER) | 36.02% |
| Character accuracy | 64.64% |
| Failure rate | 7.69% |
| Empty-output rate | 23.08% |
| Avg seconds / file | 5.94 |
| p95 seconds / file | 10.01 |
| Throughput | 10.1 files/min |
| Field accuracy (invoice no / date / total) | 100.00% |
| Search hit@1 / hit@3 / hit@10 | 70.00% / 70.00% / 70.00% |
| Search MRR | 0.700 (perfect text: 1.000) |
| Search retention (MRR) | 70.00% |

### Field accuracy

| Field | Exact match |
|---|---:|
| invoice_no | 100.00% |
| date | 100.00% |
| total | 100.00% |

### By document type

| Group | Files | CER | WER | Char acc. | Conf. | s/file | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| csv | 2 | 0.00% | 0.00% | 100.00% | - | 0.00 | 50.00% |
| pdf_mixed | 2 | 64.20% | 66.09% | 35.80% | - | 0.04 | 0.00% |
| pdf_scanned | 6 | 49.32% | 50.00% | 50.68% | - | 12.84 | 0.00% |
| pdf_text | 3 | 0.00% | 0.00% | 100.00% | - | 0.04 | 0.00% |

### By image condition / category

| Group | Files | CER | WER | Char acc. | Conf. | s/file | Failed |
|---|---:|---:|---:|---:|---:|---:|---:|
| csv | 1 | 0.00% | 0.00% | 100.00% | - | 0.00 | 0.00% |
| csv_arabic | 1 | - | - | - | - | 0.00 | 100.00% |
| pdf_mixed | 2 | 64.20% | 66.09% | 35.80% | - | 0.04 | 0.00% |
| pdf_scanned | 6 | 49.32% | 50.00% | 50.68% | - | 12.84 | 0.00% |
| pdf_text | 3 | 0.00% | 0.00% | 100.00% | - | 0.04 | 0.00% |

### Five hardest files

| File | CER | Failed |
|---|---:|---|
| letter_scanpdf_shadow_30.pdf | 100.00% |  |
| letter_scanpdf_skewed_heavy_29.pdf | 100.00% |  |
| names_cp1256.csv | 100.00% | yes |
| letter_scanpdf_noisy_heavy_28.pdf | 95.89% |  |
| mixed_textscan_32.pdf | 64.74% |  |

_Not run in this mode: invoice_blurry_14.png, invoice_blurry_heavy_16.png, invoice_clean_00.png, invoice_jpeg_low_20.png, invoice_lowres_10.png, invoice_lowres_heavy_12.png, invoice_noisy_02.png, invoice_noisy_heavy_04.png, invoice_shadow_18.png, invoice_skewed_06.png, invoice_skewed_heavy_08.png, letter_blurry_15.png, letter_blurry_heavy_17.png, letter_clean_01.png, letter_jpeg_low_21.png, letter_lowres_11.png, letter_lowres_heavy_13.png, letter_noisy_03.png, letter_noisy_heavy_05.png, letter_shadow_19.png, letter_skewed_07.png, letter_skewed_heavy_09.png, sales_two_sheets.xlsx_
