#!/usr/bin/env python3
"""
ISA — Independent Ship Agents S.A.
build_fda.py — Generador de FDA (Final Disbursement Account)
Puerto: San Lorenzo / Arroyo Seco / Gral. Lagos

Uso:
    python build_fda.py                        # usa FDA_CONFIG definido en este archivo
    python build_fda.py --config mi_config.py  # usa archivo de config externo

Dependencias:
    pip install pymupdf pypdf reportlab Pillow numpy

Estructura de directorios esperada:
    invoices/        ← PDFs de facturas del buque
    model/           ← summary_model.pdf (para extraer logo ISA)
    assets/          ← logos generados automáticamente
    output/          ← FDA generado
"""

import fitz
import os
import io
import sys
import argparse
import numpy as np
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from pypdf import PdfWriter, PdfReader

# ── TAMAÑO DE PÁGINA ──────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4   # 595.27 x 841.89 pt

# ── COLORES (extraídos con fitz del modelo) ───────────────────────────────────
ISA_COL   = (0.231, 0.329, 0.565)
GREY_BG   = (0.949, 0.949, 0.949)
WHITE     = (1.0,   1.0,   1.0)
RED       = (1.0,   0.0,   0.0)
BLACK     = (0.0,   0.0,   0.0)
GREY_LINE = (0.8,   0.8,   0.8)


# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DEL FDA — modificar para cada buque nuevo
# ════════════════════════════════════════════════════════════════════════════════

FDA_CONFIG = {
    # Datos del buque
    "vessel":  "LASKARO S",
    "client":  "CEFETRA SPA",
    "port":    "San Lorenzo Port",
    "sailed":  "Apr 13, 2026",
    "date":    "May 19, 2026",
    "advance": 192980.00,

    # Facturas ISA: (numero, concepto, puerto, monto, es_ncb)
    "invoices": [
        ("Invoice 16450", "Nota de crédito", "San Lorenzo", -15774.89, True),
        ("Invoice 16451", "Nota de crédito", "San Lorenzo",   -898.65, True),
        ("Invoice 29961", "Agency fee",       "San Lorenzo",   3000.00, False),
        ("Invoice 30317", "Port expenses",    "San Lorenzo", 170220.75, False),
        ("Invoice 30318", "Port expenses",    "San Lorenzo", 102073.91, False),
        ("Invoice 30319", "Port expenses",    "San Lorenzo",  17392.75, False),
    ],
    "total_expenses": 276013.87,

    # Rutas
    "invoices_dir":      "invoices",
    "output_path":       "output/FDA_LASKARO_S.pdf",
    "summary_model_pdf": "model/summary_model.pdf",
    "logo_path":         "assets/logo_isa.png",
    "logo_voucher_path": "assets/logo_voucher.png",

    # Secuencia de páginas: ("tipo", args...)
    # "summary"                           → genera sumario ISA
    # ("file", nombre, [pages])           → agrega archivo/páginas
    # ("voucher", concepto, monto, rate)  → genera voucher ISA
    "sequence": [
        ("summary",),
        ("file", "SOF (10).pdf"),

        # BLOQUE TC 1345
        ("file", "TC.pdf"),
        ("file", "N_CB0000300016450.pdf"),
        ("file", "FACB0000300029961.pdf"),
        ("voucher", "AGENCY FEE", "3,000", "1345"),
        ("file", "FACB0000300030317.pdf"),

        ("voucher", "PORT DUES", "28,037.49", "1345"),
        ("file", "TERMINAL 6 S.A. (120007)_W311273.pdf"),

        ("voucher", "ENTRANCE AND LIGHT DUES", "1,769.79", "1345"),
        ("file", "MARITIME SHIPPING AGENCY SRL (130025)_W315288.pdf", [6]),

        ("voucher", "RIVER PLATE PILOTAGE", "48,858.40", "1345"),
        ("file", "PRACTICAJE RIO DE LA PLATA CT (120002)_W311170.pdf"),
        ("file", "PRACTICAJE RIO DE LA PLATA CT (120002)_W311171.pdf"),
        ("file", "PRACTICAJE RIO DE LA PLATA CT (120002)_W311302.pdf"),
        ("file", "PRACTICAJE RIO DE LA PLATA CT (120002)_W311303.pdf"),

        ("voucher", "RIVER PLATE PILOTAGE (DELAY)", "300", "1345"),
        ("file", "PRACTICAJE RIO DE LA PLATA CT (120002)_W311303.pdf"),

        ("voucher", "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER", "2,520", "1345"),
        ("file", "PRACTICAJE RIO DE LA PLATA CT (120002)_W311303.pdf"),

        ("voucher", "RIVER PARANA PILOTAGE", "50,904", "1345"),
        ("file", "COPRAC (120083)_W311014.pdf", [0]),
        ("file", "COPRAC (120083)_W311015.pdf", [0]),
        ("file", "COPRAC (120083)_W311524.pdf", [0]),
        ("file", "COPRAC (120083)_W311525.pdf", [0]),

        ("voucher", "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER", "5,040", "1345"),
        ("file", "COPRAC (120083)_W311016.pdf", [0]),
        ("file", "COPRAC (120083)_W311526.pdf", [0]),

        ("voucher", "PORT PILOTAGE", "14,116", "1345"),
        ("file", "ROSARIO PILOTS COOP DE TRAB. (120033)_W310744.pdf"),
        ("file", "ROSARIO PILOTS COOP DE TRAB. (120033)_W310747.pdf"),
        ("file", "ROSARIO PILOTS COOP DE TRAB. (120033)_W310758.pdf"),
        ("file", "ROSARIO PILOTS COOP DE TRAB. (120033)_W310759.pdf"),

        ("voucher", "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)", "3,000", "1345"),
        ("file", "AMARRE CORAL S.A. (401604)_W310696.pdf", [0]),

        ("voucher", "MOORING & UNMOORING SERVICES", "11,000", "1345"),
        ("file", "AMARRE CORAL S.A. (401604)_W310698.pdf"),

        ("voucher", "CUSTOM HOUSE EXPENSES", "266.97", "1345"),
        ("file", "MARITIME SHIPPING AGENCY SRL (130025)_W315288.pdf", [7]),
        ("file", "MARITIME SHIPPING AGENCY SRL (130025)_W315288.pdf", [8]),
        ("file", "CENTRO DE NAVEGACION ASOCIACION CIVIL (110144)_W312375.pdf"),

        ("voucher", "MIGRATION EXPENSES", "3,310.97", "1345"),
        ("file", "MARITIME SHIPPING AGENCY SRL (130025)_W315288.pdf", [10,11,12,13,14,15]),

        ("voucher", "SANITARY DUES AND FREE PRATIQUE", "484.94", "1345"),
        ("file", "MARITIME SHIPPING AGENCY SRL (130025)_W315288.pdf", [16,17,18,19]),

        ("voucher", "GARBAGE COMPULSORY INSPECTION", "95.96", "1345"),
        ("file", "MARITIME SHIPPING AGENCY SRL (130025)_W315288.pdf", [20,21]),

        ("voucher", "FULL ON HIRE / BQS SURVEY", "900", "1345"),
        ("file", "EDI SEPAROVIC (300391)_W311936.pdf", [0]),

        ("voucher", "MANDATORY HOLDS INSPECTION", "3,160", "1345"),
        ("file", "MARITIME SHIPPING AGENCY SRL (130025)_W315284.pdf", [1,2,3]),

        ("voucher", "HEADCLERK COMPULSORY SERVICES", "3,317.81", "1345"),
        ("file", "MARITIME SHIPPING AGENCY SRL (130025)_W315287.pdf", [2,3]),

        ("voucher", "TAX ON CREDIT/DEBIT LAW 25.413", "3,346.08", "1345"),

        # BLOQUE TC 1385
        ("file", "TC TOLL DUES.pdf"),
        ("file", "FACB0000300030318.pdf"),
        ("voucher", "TOLL DUES (AGP)", "100,952.48", "1385"),
        ("file", "ADMINISTRACION GENERAL DE PUERTOS S. A. U. (401262)_W310624.pdf"),
        ("file", "ADMINISTRACION GENERAL DE PUERTOS S. A. U. (401262)_W311634.pdf"),
        ("voucher", "TAX ON CREDIT/DEBIT LAW 25.413", "1,121.43", "1385"),

        # BLOQUE TC 1457
        ("file", "N_CB0000300016451.pdf"),
        ("file", "FACB0000300030319.pdf"),
        ("voucher", "TOLL DUES (CARP)", "8,306.52", "1457"),
        ("file", "CARP (COMISION ADM DEL RIO DE LP) (400477)_W310304.pdf"),
        ("voucher", "RIVER PLATE PILOTAGE", "8,880", "1457"),
        ("file", "GLATIL SA (300361)_W311415.pdf"),
        ("file", "GLATIL SA (300361)_W311467.pdf"),
        ("voucher", "TAX ON CREDIT/DEBIT LAW 25.413", "206.23", "1457"),
    ],
}


# ════════════════════════════════════════════════════════════════════════════════
# FUNCIONES INTERNAS
# ════════════════════════════════════════════════════════════════════════════════

def _sf(c, col): c.setFillColorRGB(*col)
def _ss(c, col): c.setStrokeColorRGB(*col)


def extract_logo(cfg):
    """
    Extrae logo ISA del PDF sumario modelo.
    Genera:
      logo_path         → logo completo (para sumario)
      logo_voucher_path → logo sin 'Independent Ship Agents S.A.' (para vouchers)
    """
    logo    = cfg["logo_path"]
    logo_v  = cfg["logo_voucher_path"]
    if os.path.exists(logo) and os.path.exists(logo_v):
        return

    for p in [logo, logo_v]:
        d = os.path.dirname(p)
        if d:
            os.makedirs(d, exist_ok=True)

    model = cfg["summary_model_pdf"]
    if not os.path.exists(model):
        raise FileNotFoundError(
            f"No se encontró el PDF modelo: {model}\n"
            "Copiar el sumario modelo a esa ruta (ver README)."
        )

    doc  = fitz.open(model)
    imgs = doc[0].get_images(full=True)
    # Buscar imagen más grande (el logo PNG)
    best_xref = max(imgs, key=lambda i: fitz.Pixmap(doc, i[0]).width * fitz.Pixmap(doc, i[0]).height)[0]
    base = doc.extract_image(best_xref)
    doc.close()

    img_full = Image.open(io.BytesIO(base["image"]))
    img_full.save(logo)

    # Recortar antes de "Independent Ship Agents S.A." (≈ 70% de altura)
    H_im   = img_full.height
    cutoff = int(H_im * 0.70)
    crop   = img_full.crop((0, 0, img_full.width, cutoff))
    arr    = np.array(crop)
    rows   = np.where(np.any(arr < 220, axis=(1, 2)))[0]
    if len(rows):
        crop = crop.crop((0, max(0, rows[0]-10), img_full.width, min(cutoff, rows[-1]+10)))
    crop.save(logo_v)
    print(f"  Logos extraídos → {logo}, {logo_v}")


def build_summary(cfg):
    """Genera la página de sumario ISA (layout fiel al modelo)."""
    vessel  = cfg["vessel"]
    client  = cfg["client"]
    port    = cfg["port"]
    date    = cfg["date"]
    advance = cfg["advance"]
    total   = cfg["total_expenses"]
    balance = total - advance

    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)
    W, H = PAGE_W, PAGE_H

    # Logo (top-right)
    c.drawImage(cfg["logo_path"], 455.28, H-120, width=100, height=100,
                preserveAspectRatio=True, mask="auto")

    # "Disbursement Summary"
    _sf(c, ISA_COL); c.setFont("Helvetica-Oblique", 11)
    c.drawString(40, H-80, "Disbursement Summary")

    # Fecha
    _sf(c, BLACK); c.setFont("Helvetica", 9)
    c.drawString(40, H-150, f"Buenos Aires, {date}")

    # Líneas separadoras
    _ss(c, ISA_COL)
    c.setLineWidth(3); c.line(40, H-165, 555, H-165)
    c.setLineWidth(1); c.line(40, H-169, 555, H-169)

    # Tabla buque
    _sf(c, GREY_BG)
    c.rect(40, H-208, 260, 20, fill=1, stroke=0)
    c.rect(310, H-208, 245, 20, fill=1, stroke=0)
    _sf(c, WHITE)
    c.rect(40, H-228, 260, 20, fill=1, stroke=0)
    c.rect(310, H-228, 245, 20, fill=1, stroke=0)
    _sf(c, GREY_BG)
    c.rect(40, H-248, 260, 20, fill=1, stroke=0)

    _sf(c, BLACK)
    for bold, x, y, txt in [
        (True,  47,  202, "To:"),     (False, 95,  202, client),
        (True,  317, 202, "Sailed:"),
        (True,  47,  222, "Vessel:"), (False, 95,  222, f"M/V {vessel}"),
        (True,  317, 222, "Date:"),   (False, 360, 222, date),
        (True,  47,  242, "Port:"),   (False, 95,  242, port),
    ]:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 9)
        c.drawString(x, H-y, txt)

    # Intro
    c.setFont("Helvetica", 9)
    c.drawString(40, H-266, "Dear Sir / Madam,")
    c.drawString(40, H-280,
        "Please find our final disbursement account for the operations of the "
        "concerning vessel during the call at ref. port.")

    # Header tabla
    _sf(c, ISA_COL); c.rect(40, H-319, 515, 18, fill=1, stroke=0)
    _sf(c, WHITE); c.setFont("Helvetica-Bold", 9)
    for x, h in [(44,"Invoice Number"),(174,"Concept"),(374,"Port"),(474,"USD Amount")]:
        c.drawString(x, H-314, h)

    # Filas facturas
    fills  = [WHITE, GREY_BG, WHITE, GREY_BG, WHITE, GREY_BG]
    ytops  = [319, 337, 355, 373, 391, 409]
    for i, (num, concept, prt, amount, is_ncb) in enumerate(cfg["invoices"]):
        fill = fills[i] if i < len(fills) else (WHITE if i%2==0 else GREY_BG)
        ytop = ytops[i] if i < len(ytops) else ytops[-1] + 18*(i-len(ytops)+1)
        _sf(c, fill); c.rect(40, H-ytop-18, 515, 18, fill=1, stroke=0)
        _sf(c, RED if is_ncb else BLACK); c.setFont("Helvetica", 9)
        ty = H - ytop - 14
        c.drawString(44,  ty, num)
        c.drawString(174, ty, concept)
        c.drawString(374, ty, prt)
        amt = f"({abs(amount):,.2f})" if is_ncb else f"{amount:,.2f}"
        c.drawRightString(555, ty, amt)

    # Total expenses (fila blanca)
    _sf(c, WHITE); c.rect(40, H-445, 515, 18, fill=1, stroke=0)
    _sf(c, BLACK); c.setFont("Helvetica-Bold", 9)
    c.drawRightString(460, H-440, "Total Expenses")
    c.drawRightString(555, H-440, f"{total:,.2f}")

    # Less advanced (fila gris)
    _sf(c, GREY_BG); c.rect(40, H-463, 515, 18, fill=1, stroke=0)
    _sf(c, BLACK); c.setFont("Helvetica", 9)
    c.drawString(174, H-458, f"Less advanced by {client}")
    _sf(c, RED); c.drawRightString(555, H-458, f"({advance:,.0f})")

    # Balance (fila azul)
    _sf(c, ISA_COL); c.rect(40, H-481, 515, 18, fill=1, stroke=0)
    _sf(c, WHITE); c.setFont("Helvetica-Bold", 10)
    lbl = "Total due to ISA" if balance >= 0 else f"Total due to {client}"
    c.drawString(44,  H-476, lbl)
    c.drawRightString(555, H-476, f"{abs(balance):,.2f}")

    # Texto cierre
    _sf(c, BLACK); c.setFont("Helvetica", 9)
    c.drawString(40, H-499,
        "Please do not hesitate to contact us if you need to elaborate on this disbursement.")
    c.drawString(40, H-517,
        "We thank you very much for having chosen us as agents. We trust our performance "
        "has reached your requirements, and we look")
    c.drawString(40, H-529, "forward to be of assistance to you in the future.")

    # Bank Details
    _sf(c, ISA_COL); c.rect(40, H-561, 275, 18, fill=1, stroke=0)
    _sf(c, WHITE); c.setFont("Helvetica-Bold", 9)
    c.drawString(48, H-556, "Bank Details")
    for y_pdf, lbl_b, val in [
        (579, "Bank:",        "Citibank N.A., New York Branch"),
        (595, "Address:",     "111 Wall Street, New York, NY 10043"),
        (611, "ABA #:",       "21000089"),
        (627, "SWIFT:",       "CITIUS33"),
        (643, "Account No:",  "36404074"),
        (659, "Beneficiary:", "INDEPENDENT SHIP AGENTS S.A."),
    ]:
        _sf(c, WHITE); _ss(c, GREY_LINE); c.setLineWidth(0.5)
        c.rect(40, H-y_pdf-16, 275, 16, fill=1, stroke=1)
        _sf(c, BLACK)
        c.setFont("Helvetica", 8); c.drawString(48, H-y_pdf-10, lbl_b)
        c.setFont("Helvetica-Bold" if lbl_b=="Beneficiary:" else "Helvetica", 8)
        c.drawString(120, H-y_pdf-10, val)

    # Footer
    _ss(c, GREY_LINE); c.setLineWidth(0.5)
    c.line(40, H-786.89, 555, H-786.89)
    _sf(c, ISA_COL); c.setFont("Helvetica-Bold", 8)
    c.drawString(40, H-797.9, "Independent Ship Agents S.A.")
    _sf(c, BLACK); c.setFont("Helvetica", 8)
    c.drawString(40, H-807.9,
        "Av. del Libertador 602, 9th Floor  |  C1001ABT Buenos Aires, Argentina")
    c.drawString(40, H-817.9,
        "Tel: (+54 11) 4819-4100  |  isa@isa-agents.com.ar  |  www.isa-agents.com.ar")

    c.save(); buf.seek(0)
    return buf


def build_voucher(cfg, concept, amount_str, rate):
    """Genera una página de voucher ISA."""
    # SAILED se muestra solo cuando el TC es distinto de 1345
    sailed_txt = cfg["sailed"] if rate != "1345" else ""

    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)
    W, H = PAGE_W, PAGE_H

    # Logo centrado arriba
    lw, lh = 170, 150
    c.drawImage(cfg["logo_voucher_path"],
                (W-lw)/2, H-35-lh, width=lw, height=lh,
                preserveAspectRatio=True, mask="auto")

    c.setFillColorRGB(0,0,0); c.setFont("Helvetica-Bold", 16)
    c.drawString(50, H-275, "SAN LORENZO")

    c.setStrokeColorRGB(0,0,0); c.setLineWidth(1)
    c.line(50, H-310, W-50, H-310)

    c.setFont("Helvetica-Bold", 24); c.drawString(50, H-345, f"VESSEL: {cfg['vessel']}")
    c.setFont("Helvetica-Bold", 16); c.drawString(50, H-370, f"SAILED: {sailed_txt}")
    c.drawString(50, H-392, f"RATE OF EXCHANGE: {rate}")

    c.setLineWidth(1); c.line(50, H-410, W-50, H-410)

    c.setFont("Helvetica-Bold", 18); c.drawString(50, H-470, concept)
    c.setFont("Helvetica-Bold", 22); c.drawCentredString(W/2, H-570, f"USD {amount_str}")

    c.setFont("Helvetica", 8)
    c.drawCentredString(W/2, 28,
        "Av. del Libertador 602 - 9th Floor - C1001ABT - Buenos Aires - Argentina")
    c.drawCentredString(W/2, 18,
        "Phone (+54 11) 4819-4100 - Fax (+54 11) 4819-4101 - disbursements@isa-agents.com.ar")

    c.save(); buf.seek(0)
    return buf


def add_file(writer, invoices_dir, fname, pages=None):
    path   = os.path.join(invoices_dir, fname)
    reader = PdfReader(path)
    n      = len(reader.pages)
    idxs   = pages if pages is not None else list(range(n))
    for i in idxs:
        if i < n:
            writer.add_page(reader.pages[i])


def add_buf(writer, buf):
    for page in PdfReader(buf).pages:
        writer.add_page(page)


def build_fda(cfg=None):
    if cfg is None:
        cfg = FDA_CONFIG

    print(f"\n{'='*60}")
    print(f"  FDA: {cfg['vessel']}  |  {cfg['port']}  |  Sailed: {cfg['sailed']}")
    print(f"{'='*60}")

    extract_logo(cfg)
    writer = PdfWriter()

    for step in cfg["sequence"]:
        kind = step[0]

        if kind == "summary":
            print("  + Sumario")
            add_buf(writer, build_summary(cfg))

        elif kind == "voucher":
            _, concept, amount_str, rate = step
            print(f"  + Voucher: {concept}  USD {amount_str}  [TC {rate}]")
            add_buf(writer, build_voucher(cfg, concept, amount_str, rate))

        elif kind == "file":
            fname = step[1]
            pages = step[2] if len(step) > 2 else None
            pg_str = f" {pages}" if pages else ""
            print(f"  + {fname}{pg_str}")
            add_file(writer, cfg["invoices_dir"], fname, pages)

        else:
            print(f"  ! Tipo desconocido ignorado: {kind}")

    out = cfg["output_path"]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as fh:
        writer.write(fh)

    n = len(writer.pages)
    print(f"\n✓  FDA generado: {out}  ({n} páginas)")
    return out, n


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera FDA ISA en PDF")
    parser.add_argument("--config", help="Archivo .py con FDA_CONFIG personalizado")
    args = parser.parse_args()

    if args.config:
        import importlib.util
        spec = importlib.util.spec_from_file_location("cfg", args.config)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        build_fda(mod.FDA_CONFIG)
    else:
        build_fda()
