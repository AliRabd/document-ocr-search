#!/usr/bin/env python3
"""Generate a reproducible synthetic evaluation set with ground truth.

    python evaluation/make_samples.py            # writes evaluation/samples/

Creates images (clean / noisy / skewed / low-res / blurry), text PDFs, scanned
PDFs, a mixed text+scan PDF, CSV and XLSX files, plus:
  samples/truth/<file>.txt   exact expected text
  manifest.json              file -> {truth, category, fields}
  queries.csv                search queries and the file that must be found
Everything is synthetic, so it is safe to publish on GitHub.
For REAL measurements, add your own files + hand-corrected truth (see README).
"""
import csv
import json
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "samples")          # overridden by --out in main()
TRUTH = os.path.join(OUT, "truth")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SIZE = 34
W, H = 1654, 2339            # A4 @ 200 dpi

COMPANIES = ["Brightwave Logistics", "Cedarfield Textiles", "Northgate Optics",
             "Silverpine Foods", "Harborview Medical", "Ironbridge Steel",
             "Lakeshore Software", "Maplecrest Printing", "Oakridge Energy",
             "Pinnacle Furniture", "Riverstone Hotels", "Stonehaven Paper",
             "Willowbrook Labs", "Redwood Analytics", "Goldleaf Packaging",
             "Bluepeak Consulting", "Crestline Motors", "Dunmore Chemicals",
             "Eastfield Pharma", "Falconridge Travel", "Greystone Bakery",
             "Highland Plastics", "Ivywood Education", "Juniper Marine"]
ITEMS = [("Office chairs", 85.5), ("Printer toner", 42.25), ("Steel brackets", 12.8),
         ("Cotton fabric roll", 140.0), ("Safety gloves", 6.75), ("LED panels", 58.4),
         ("Packing boxes", 2.15), ("Network cables", 9.9), ("Lab reagents", 215.0)]
CITIES = ["Amman", "Cairo", "Dubai", "Riyadh", "Doha", "Muscat", "Beirut", "Tunis"]
PEOPLE = ["Samir Haddad", "Layla Mansour", "Omar Khalil", "Nadia Farouk",
          "Yusuf Barakat", "Huda Saleh", "Karim Nasser", "Rania Aziz"]
SENTENCES = [
    "We confirm receipt of your purchase order and the agreed delivery schedule.",
    "Payment is due within thirty days of the invoice date unless stated otherwise.",
    "The warehouse in %(city)s will dispatch the goods on the first working day.",
    "Please contact %(person)s if any item is damaged or missing on arrival.",
    "This agreement is governed by the commercial laws of the country of supply.",
    "Quarterly volumes will be reviewed jointly to adjust pricing and capacity.",
    "All shipments include a packing list and a signed certificate of origin.",
]


def font():
    return ImageFont.truetype(FONT, FONT_SIZE)


def make_invoice(rng, n):
    company = COMPANIES[n % len(COMPANIES)]
    inv_no = "INV-2026-%04d" % rng.randint(100, 9999)
    date = "2026-%02d-%02d" % (rng.randint(1, 12), rng.randint(1, 28))
    items = rng.sample(ITEMS, 3)
    lines = ["INVOICE", "", "Company: %s" % company, "Invoice No: %s" % inv_no,
             "Date: %s" % date, "City: %s" % rng.choice(CITIES), "",
             "Description          Qty    Price"]
    total = 0.0
    for name, price in items:
        qty = rng.randint(1, 20)
        total += qty * price
        lines.append("%s  %d  %.2f" % (name, qty, price))
    lines += ["", "Total: %.2f USD" % total]
    fields = {"invoice_no": inv_no, "date": date, "total": "%.2f" % total}
    return lines, fields, company


def make_letter(rng, n):
    company = COMPANIES[(n + 11) % len(COMPANIES)]
    person = rng.choice(PEOPLE)
    city = rng.choice(CITIES)
    lines = ["%s" % company, "Attention: %s" % person, "Reference: LTR-%04d" % rng.randint(100, 9999), ""]
    for s in rng.sample(SENTENCES, 4):
        lines.append(s % {"city": city, "person": person})
    return lines, {}, company


def wrap(lines, width=62):
    out = []
    for line in lines:
        while len(line) > width:
            cut = line.rfind(" ", 0, width)
            cut = cut if cut > 0 else width
            out.append(line[:cut].rstrip())
            line = line[cut:].lstrip()
        out.append(line)
    return out


def render(lines):
    img = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(img)
    f, y = font(), 140
    for line in lines:
        draw.text((130, y), line, fill=0, font=f)
        y += int(FONT_SIZE * 1.6)
    return img


def degrade(img, kind, rng):
    """Degradation levels are fixed up-front (not tuned to the pipeline's results)."""
    seed = rng.randint(0, 9999)
    ns = np.random.RandomState(seed)
    if kind in ("noisy", "noisy_heavy"):
        sigma = 28 if kind == "noisy" else 80
        arr = np.array(img).astype(np.float32) + ns.normal(0, sigma, (img.size[1], img.size[0]))
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if kind in ("skewed", "skewed_heavy"):
        angle = rng.choice([-2.5, 2.0, 3.0]) if kind == "skewed" else rng.choice([-9.0, 8.0])
        return img.rotate(angle, expand=False, fillcolor=255, resample=Image.BICUBIC)
    if kind == "lowres":
        return img.resize((W // 2, H // 2), Image.LANCZOS)
    if kind == "lowres_heavy":                       # ~50 dpi: tiny characters
        return img.resize((W // 4, H // 4), Image.LANCZOS)
    if kind in ("blurry", "blurry_heavy"):
        return img.filter(ImageFilter.GaussianBlur(1.6 if kind == "blurry" else 3.4))
    if kind == "shadow":                             # uneven lighting like a phone photo
        yy, xx = np.mgrid[0:img.size[1], 0:img.size[0]]
        grad = 0.45 + 0.55 * (xx / float(img.size[0]))
        arr = np.array(img).astype(np.float32) * grad[:, :]
        arr += ns.normal(0, 12, arr.shape)
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if kind == "jpeg_low":                           # heavy compression artefacts
        import io
        buf = io.BytesIO()
        img.convert("L").save(buf, "JPEG", quality=8)
        return Image.open(io.BytesIO(buf.getvalue())).convert("L")
    return img


KINDS = ["clean", "noisy", "noisy_heavy", "skewed", "skewed_heavy", "lowres",
         "lowres_heavy", "blurry", "blurry_heavy", "shadow", "jpeg_low"]
SCAN_KINDS = ["clean", "noisy", "skewed", "noisy_heavy", "skewed_heavy", "shadow"]


def pdf_text_page_bytes(lines):
    """Hand-built single-page PDF with a real text layer (Helvetica)."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = ["BT", "/F1 12 Tf", "14 TL", "56 780 Td"]
    for line in lines:
        content.append("(%s) Tj T*" % esc(line))
    content.append("ET")
    stream = "\n".join(content).encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def main():
    global OUT, TRUTH, COMPANIES
    import argparse
    ap = argparse.ArgumentParser(description="Generate a synthetic OCR evaluation set")
    ap.add_argument("--seed", type=int, default=42, help="content/noise seed (42 = bundled dev set)")
    ap.add_argument("--out", default=HERE, help="folder that will contain samples/, manifest.json, queries.csv")
    args = ap.parse_args()
    root = os.path.abspath(args.out)
    OUT, TRUTH = os.path.join(root, "samples"), os.path.join(root, "samples", "truth")
    rng = random.Random(args.seed)
    if args.seed != 42:                       # different companies/people/order for held-out sets
        COMPANIES = COMPANIES[:]
        rng.shuffle(COMPANIES)
    os.makedirs(TRUTH, exist_ok=True)
    manifest, queries = {}, []

    def register(name, lines, category, fields, company, kind):
        truth = "\n".join(lines)
        with open(os.path.join(TRUTH, name + ".txt"), "w", encoding="utf-8") as h:
            h.write(truth)
        manifest[name] = {"truth": "truth/%s.txt" % name, "category": category,
                          "doc_type": kind, "fields": fields}
        queries.append((company, name))
        if "invoice_no" in fields:
            queries.append((fields["invoice_no"], name))

    n = 0
    # --- images: 5 degradations x (invoice, letter)
    for kind in KINDS:
        for maker in (make_invoice, make_letter):
            lines, fields, company = maker(rng, n)
            lines = wrap(lines)
            img = degrade(render(lines), kind, rng)
            name = "%s_%s_%02d.png" % (maker.__name__.replace("make_", ""), kind, n)
            img.save(os.path.join(OUT, name), dpi=(200, 200), optimize=True)
            register(name, lines, "image_" + kind, fields, company, "image")
            n += 1

    # --- text PDFs
    for i in range(3):
        lines, fields, company = make_invoice(rng, n)
        name = "invoice_textpdf_%02d.pdf" % n
        with open(os.path.join(OUT, name), "wb") as h:
            h.write(pdf_text_page_bytes(lines))
        register(name, lines, "pdf_text", fields, company, "pdf_text")
        n += 1

    # --- scanned PDFs (image only, no text layer)
    for kind in SCAN_KINDS:
        lines, fields, company = make_letter(rng, n)
        lines = wrap(lines)
        img = degrade(render(lines), kind, rng).convert("RGB")
        name = "letter_scanpdf_%s_%02d.pdf" % (kind, n)
        img.save(os.path.join(OUT, name), "PDF", resolution=200.0)
        register(name, lines, "pdf_scanned", fields, company, "pdf_scanned")
        n += 1

    # --- mixed PDFs: page 1 = text layer, page 2 = scan
    for i in range(2):
        l1, f1, c1 = make_invoice(rng, n)
        l2, _f2, c2 = make_letter(rng, n)
        l2 = wrap(l2)
        tmp1, tmp2 = os.path.join(OUT, "_p1.pdf"), os.path.join(OUT, "_p2.pdf")
        with open(tmp1, "wb") as h:
            h.write(pdf_text_page_bytes(l1))
        render(l2).convert("RGB").save(tmp2, "PDF", resolution=200.0)
        name = "mixed_textscan_%02d.pdf" % n
        subprocess.check_call(["pdfunite", tmp1, tmp2, os.path.join(OUT, name)])
        os.remove(tmp1), os.remove(tmp2)
        register(name, l1 + [""] + l2, "pdf_mixed", f1, c1, "pdf_mixed")
        queries.append((c2, name))        # text that lives on the SCANNED page
        n += 1

    # --- CSV (utf-8) and CSV (cp1256 bytes, Arabic) and XLSX
    rows = [["Product", "Qty", "City"], ["Steel brackets", "40", "Amman"], ["Safety gloves", "300", "Cairo"]]
    name = "stock_utf8.csv"
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as h:
        csv.writer(h).writerows(rows)
    lines = [", ".join(r) for r in rows]
    register(name, lines, "csv", {}, "Safety gloves", "csv")

    ar_rows = [[u"الاسم", u"المدينة"],
               [u"أحمد", u"الرياض"],
               [u"ليلى", u"عمان"]]
    name = "names_cp1256.csv"
    with open(os.path.join(OUT, name), "wb") as h:
        h.write(("\r\n".join(",".join(r) for r in ar_rows) + "\r\n").encode("cp1256"))
    register(name, [", ".join(r) for r in ar_rows], "csv_arabic", {}, ar_rows[1][0], "csv")

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Q1"
    ws.append(["Region", "Sales"]); ws.append(["North", 1200])
    ws2 = wb.create_sheet("Q2")
    ws2.append(["Region", "Sales"]); ws2.append(["Southpoint", 3400])
    name = "sales_two_sheets.xlsx"
    wb.save(os.path.join(OUT, name))
    register(name, ["## Q1", "Region, Sales", "North, 1200", "## Q2", "Region, Sales",
                    "Southpoint, 3400"], "xlsx", {}, "Southpoint", "excel")

    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as h:
        json.dump(manifest, h, indent=2, ensure_ascii=False)
    with open(os.path.join(root, "queries.csv"), "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["query", "expected_file"])
        w.writerows(queries)
    print("Generated %d files, %d queries in %s" % (len(manifest), len(queries), OUT))


if __name__ == "__main__":
    sys.exit(main())
