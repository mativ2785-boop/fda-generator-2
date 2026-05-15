"""
assembler.py  —  ISA FDA Generator
Construye el invoice_map y ensambla el PDF final.
Soporta: Bahia Blanca, Necochea, San Lorenzo / Arroyo Seco / Gral. Lagos
"""

import os, io, re, sys
import fitz  # PyMuPDF
from pypdf import PdfWriter, PdfReader

try:
    from ports import detect_port as _detect_port_fn
except ImportError:
    import sys as _sys, os as _os2
    _sys.path.insert(0, _os2.path.dirname(_os2.path.abspath(__file__)))
    from ports import detect_port as _detect_port_fn

def _detect_port(analysis):
    return _detect_port_fn(analysis)

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

PW, PH   = A4
ISA_BLUE = colors.HexColor("#3B5490")
LOGO     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_isa.png")

MONTHS_ABBR = {
    "January":"Jan","February":"Feb","March":"Mar","April":"Apr",
    "May":"May","June":"Jun","July":"Jul","August":"Aug",
    "September":"Sep","October":"Oct","November":"Nov","December":"Dec",
}


# ── PDF helpers ───────────────────────────────────────────────────────────────

def fmt_amt(v):
    return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"


def add_pdf(writer, path, pages=None):
    if not os.path.exists(path):
        print(f"    ⚠ No encontrado: {os.path.basename(path)}")
        return 0
    reader = PdfReader(path)
    total  = len(reader.pages)
    idxs   = list(range(total)) if pages is None else pages
    n = 0
    for i in idxs:
        if 0 <= i < total:
            writer.add_page(reader.pages[i])
            n += 1
    return n


# ── Logo extractor ────────────────────────────────────────────────────────────

def extract_logo_from_facb(facb_path, dest_path):
    """
    Extrae el logo ISA desde una FACB como crop de la página.
    El logo aparece en la parte superior-izquierda de la FACB.
    """
    try:
        doc  = fitz.open(facb_path)
        pg   = doc[0]
        mat  = fitz.Matrix(4, 4)
        clip = fitz.Rect(60, 30, 210, 135)
        pix  = pg.get_pixmap(matrix=mat, clip=clip)
        pix.save(dest_path)
        return True
    except Exception:
        return False


# ── Voucher page ──────────────────────────────────────────────────────────────

def make_voucher(concept, amount, tc, vessel, sailed, port="BAHIA BLANCA"):
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)

    # Logo centrado arriba
    lw = lh = 100
    if os.path.exists(LOGO):
        c.drawImage(LOGO, (PW - lw) / 2, PH - 20 - lh, width=lw, height=lh,
                    preserveAspectRatio=True, mask="auto")

    port_label = port.upper().replace(" PORT", "")
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.black)
    c.drawString(80, PH - 182, port_label)

    c.setLineWidth(1)
    c.line(80, PH - 232, 520, PH - 232)

    vessel_short = vessel.replace("M/V ", "").replace("m/v ", "")
    c.setFont("Helvetica-Bold", 24)
    c.drawString(80, PH - 257, f"VESSEL: {vessel_short}")

    sailed_s = sailed or ""
    for full, abbr in MONTHS_ABBR.items():
        sailed_s = sailed_s.replace(full, abbr)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(80, PH - 277, f"SAILED: {sailed_s}")
    c.drawString(80, PH - 297, f"RATE OF EXCHANGE: {tc:g}")

    c.line(80, PH - 302, 520, PH - 302)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(80, PH - 382, concept)

    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(PW / 2, PH - 482, f"USD {fmt_amt(amount)}")

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawCentredString(PW / 2, PH - 742,
        "Av. del Libertador 602 - 9th Floor - C1001ABT - Buenos Aires - Argentina")
    c.drawCentredString(PW / 2, PH - 752,
        "Phone (+54 11) 4819-4100 - Fax (+54 11) 4819-4101 - disbursements@isa-agents.com.ar")

    c.save()
    buf.seek(0)
    return PdfReader(buf)


# ── Summary page ──────────────────────────────────────────────────────────────

def make_summary(vessel, port, sailed, date, client, advance, tc_groups, bank_info=None):
    """
    Genera la página de sumario ISA.
    Orden en tabla: NCBs primero (todos), luego agency fee, luego port expenses.
    """
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)

    # Logo arriba a la derecha
    lw = lh = 100
    if os.path.exists(LOGO):
        c.drawImage(LOGO, PW - 40 - lw, PH - 20 - lh, width=lw, height=lh,
                    preserveAspectRatio=True, mask="auto")

    c.setFont("Helvetica-Oblique", 11)
    c.setFillColor(ISA_BLUE)
    c.drawString(40, PH - 80, "Disbursement Summary")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    c.drawString(40, PH - 150, f"Buenos Aires, {date}")

    c.setStrokeColor(ISA_BLUE)
    c.setLineWidth(3)
    c.line(40, PH - 165, 555, PH - 165)
    c.setLineWidth(1)
    c.line(40, PH - 169, 555, PH - 169)

    y0 = PH - 188
    RH = 20
    for i, (lbl, val) in enumerate([("To:", client), ("Vessel:", vessel), ("Port:", port)]):
        bg = colors.HexColor("#F2F2F2") if i % 2 == 0 else colors.white
        c.setFillColor(bg)
        c.rect(40, y0 - RH * (i + 1), 260, RH, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(47, y0 - RH * (i + 1) + 6, lbl)
        c.setFont("Helvetica-Bold" if lbl == "To:" else "Helvetica", 9)
        c.drawString(95, y0 - RH * (i + 1) + 6, val)

    for i, (lbl, val) in enumerate([("Sailed:", sailed or ""), ("Date:", date)]):
        bg = colors.HexColor("#F2F2F2") if i % 2 == 0 else colors.white
        c.setFillColor(bg)
        c.rect(310, y0 - RH * (i + 1), 245, RH, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(317, y0 - RH * (i + 1) + 6, lbl)
        c.setFont("Helvetica", 9)
        c.drawString(360, y0 - RH * (i + 1) + 6, val)

    ty = y0 - RH * 3 - 18
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    c.drawString(40, ty, "Dear Sir / Madam,")
    c.drawString(40, ty - 14,
        "Please find our final disbursement account for the operations of the concerning vessel during the call at ref. port.")

    tbl_top = ty - 35
    HDR_H = ROW_H = 18

    c.setFillColor(ISA_BLUE)
    c.rect(40, tbl_top - HDR_H, 515, HDR_H, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    for lbl, x in zip(["Invoice Number", "Concept", "Port", "USD Amount"],
                       [44, 174, 374, 474]):
        c.drawString(x, tbl_top - HDR_H + 5, lbl)

    port_short = port.replace(" Port", "").replace(" port", "")

    # Orden: NCBs primero (de todos los TC), luego agency, luego port_expenses
    all_ncbs     = []
    all_agency   = []
    all_port_exp = []
    for tc in sorted(tc_groups.keys()):
        for (num, lbl, amt) in tc_groups[tc]:
            if "crédito" in lbl.lower() or "ncb" in lbl.lower():
                all_ncbs.append((num, lbl, amt))
            elif "agency" in lbl.lower():
                all_agency.append((num, lbl, amt))
            else:
                all_port_exp.append((num, lbl, amt))
    all_rows = all_ncbs + all_agency + all_port_exp

    ry = tbl_top - HDR_H
    total = 0.0
    for row_i, (num, lbl, amt) in enumerate(all_rows):
        bg = colors.white if row_i % 2 == 0 else colors.HexColor("#F2F2F2")
        c.setFillColor(bg)
        c.rect(40, ry - ROW_H, 515, ROW_H, fill=1, stroke=0)
        is_ncb = "crédito" in lbl.lower() or "ncb" in lbl.lower()
        c.setFillColor(colors.red if is_ncb else colors.black)
        c.setFont("Helvetica", 9)
        c.drawString(44,  ry - ROW_H + 5, f"Invoice {num}")
        c.drawString(174, ry - ROW_H + 5, lbl)
        c.drawString(374, ry - ROW_H + 5, port_short)
        if is_ncb:
            c.drawRightString(555, ry - ROW_H + 5, f"({fmt_amt(abs(amt))})")
        else:
            c.drawRightString(555, ry - ROW_H + 5, fmt_amt(amt))
        total += amt
        ry -= ROW_H

    # Total Expenses
    c.setFillColor(colors.white)
    c.rect(40, ry - ROW_H, 515, ROW_H, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(469, ry - ROW_H + 5, "Total Expenses")
    c.drawRightString(555, ry - ROW_H + 5, fmt_amt(total))
    ry -= ROW_H

    if advance > 0:
        c.setFillColor(colors.HexColor("#F2F2F2"))
        c.rect(40, ry - ROW_H, 515, ROW_H, fill=1, stroke=0)
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        c.drawString(174, ry - ROW_H + 5, f"Less advanced by {client}")
        c.setFillColor(colors.red)
        c.drawRightString(555, ry - ROW_H + 5, f"({fmt_amt(advance)})")
        ry -= ROW_H

    balance = total - advance
    label   = "Total due to ISA" if balance >= 0 else f"Total due to {client}"
    c.setFillColor(ISA_BLUE if balance >= 0 else colors.red)
    c.rect(40, ry - ROW_H, 515, ROW_H, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(44, ry - ROW_H + 5, label)
    c.drawRightString(555, ry - ROW_H + 5, fmt_amt(abs(balance)))
    ry -= ROW_H

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(40, ry - 18,
        "Please do not hesitate to contact us if you need to elaborate on this disbursement.")
    c.drawString(40, ry - 36,
        "We thank you very much for having chosen us as agents. We trust our performance has reached your requirements, and we look")
    c.drawString(40, ry - 48, "forward to be of assistance to you in the future.")

    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(0.5)
    c.line(40, 55, 555, 55)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(ISA_BLUE)
    c.drawString(40, 44, "Independent Ship Agents S.A.")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawString(40, 34, "Av. del Libertador 602, 9th Floor  |  C1001ABT Buenos Aires, Argentina")
    c.drawString(40, 24, "Tel: (+54 11) 4819-4100  |  isa@isa-agents.com.ar  |  www.isa-agents.com.ar")

    bk_y = ry - 80
    bk_w = 275
    bk_x = 40

    if bank_info and bank_info.get("bank_name") == "Santander Argentina":
        bank_rows = [
            ("Bank:",        "Santander Argentina"),
            ("Account No:",  bank_info.get("bank_account", "760-000975/5")),
            ("CBU:",         bank_info.get("bank_cbu", "0720760220000000097554")),
            ("Beneficiary:", bank_info.get("bank_beneficiary", "Independent Ship Agents S.A.")),
            ("CUIT:",        bank_info.get("bank_cuit", "30-70813875-0")),
        ]
    else:
        bank_rows = [
            ("Bank:",        "Citibank N.A., New York Branch"),
            ("Address:",     "111 Wall Street, New York, NY 10043"),
            ("ABA #:",       "21000089"),
            ("SWIFT:",       "CITIUS33"),
            ("Account No:",  "36404074"),
            ("Beneficiary:", "INDEPENDENT SHIP AGENTS S.A."),
        ]

    c.setFillColor(ISA_BLUE)
    c.rect(bk_x, bk_y, bk_w, 18, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(bk_x + 8, bk_y + 5, "Bank Details")
    bk_y -= 18
    for lbl, val in bank_rows:
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#CCCCCC"))
        c.rect(bk_x, bk_y - 16, bk_w, 16, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8)
        c.drawString(bk_x + 8, bk_y - 11, lbl)
        c.setFont("Helvetica-Bold" if lbl == "Beneficiary:" else "Helvetica", 8)
        c.drawString(bk_x + 80, bk_y - 11, val)
        bk_y -= 16

    c.save()
    buf.seek(0)
    return PdfReader(buf)


# ── Extract line amounts from FACB ────────────────────────────────────────────

def extract_facb_line_amounts(pdf_path):
    """
    Extrae montos por concepto de una FACB de port expenses.
    Formato: N° / CONCEPTO / 1.00 / MONTO
    """
    amounts = {}
    try:
        doc   = fitz.open(pdf_path)
        text  = doc[0].get_text()
        lines = [l.strip() for l in text.split("\n")]
        i = 0
        while i < len(lines):
            if re.match(r"^\d+$", lines[i]) and i + 3 < len(lines):
                concept = lines[i + 1].strip().upper()
                if lines[i + 2] == "1.00":
                    try:
                        amount = float(lines[i + 3].replace(",", ""))
                        amounts[concept] = amount
                        i += 4
                        continue
                    except ValueError:
                        pass
            i += 1
    except Exception:
        pass
    return amounts


# ── Normalize line_amounts keys ───────────────────────────────────────────────

def normalize_line_amounts(line_amounts):
    """
    Normaliza las claves de line_amounts para que coincidan con los nombres
    canónicos de los vouchers (truncados en FACBs, variaciones de spelling, etc.)
    """
    normalized = {}
    for k, v in line_amounts.items():
        key = k.upper().strip()
        key = key.replace("PRACTIQUE", "PRATIQUE")
        key = key.replace("CLEARENCE", "CLEARANCE")
        if key == "RIVER PLATE PILOTAGE ANCHORAGE":
            key = "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER"
        if key == "RIVER PARANA PILOTAGE ANCHORAG":
            key = "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER"
        if key == "MANDATORY HOLDS INSPECTION AT":
            key = "MANDATORY HOLDS INSPECTION"
        if key == "HEADCLERK COMPULSORY":
            key = "HEADCLERK COMPULSORY SERVICES"
        if key == "LAUNCH SERVICES FOR CLEARENCE":
            key = "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"
        if key == "LAUNCH SERVICES FOR CLEARANCE":
            key = "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"
        if key == "FULL ON HIRE DELIVERY BUNKER A":
            key = "FULL ON HIRE / BQS SURVEY"
        normalized[key] = v
    return normalized


# ── Build FDA ─────────────────────────────────────────────────────────────────

def build_fda(analysis, work_dir, output_path, advance, date):
    """
    Ensambla el FDA completo. Retorna dict con estadísticas.
    """
    writer = PdfWriter()

    vessel    = analysis.get("vessel")  or "M/V VESSEL"
    port      = analysis.get("port")    or "Bahia Blanca Port"
    sailed    = analysis.get("sailed")  or ""
    client    = analysis.get("client")  or "CLIENT"
    tc_groups = analysis["tc_groups"]

    fp_fn = lambda f: os.path.join(work_dir, f)
    facb_files = {f["number"]: f["filename"]
                  for f in analysis["facbs"] if f.get("number")}

    # Extraer logo desde la primera FACB disponible si no existe
    if not os.path.exists(LOGO):
        for facb in analysis.get("facbs", []):
            fname = facb.get("filename")
            if fname and os.path.exists(fp_fn(fname)):
                extract_logo_from_facb(fp_fn(fname), LOGO)
                break

    # Combinar line_amounts de TODAS las FACBs de port_expenses
    line_amounts = {}
    for facb in analysis["facbs"]:
        if facb.get("type") == "port_expenses" and facb.get("filename"):
            la = extract_facb_line_amounts(fp_fn(facb["filename"]))
            for k, v in la.items():
                line_amounts[k] = line_amounts.get(k, 0) + v
    line_amounts = normalize_line_amounts(line_amounts)

    # Ordenar tc_groups: dentro de cada TC, NCBs primero, luego agency, luego port_expenses
    for tc in tc_groups:
        rows = tc_groups[tc]
        ncbs     = [(n, l, a) for (n, l, a) in rows if "crédito" in l.lower() or "ncb" in l.lower()]
        agency   = [(n, l, a) for (n, l, a) in rows if "agency" in l.lower()]
        port_exp = [(n, l, a) for (n, l, a) in rows
                    if "crédito" not in l.lower() and "ncb" not in l.lower() and "agency" not in l.lower()]
        tc_groups[tc] = ncbs + agency + port_exp

    # 1. Sumario
    print("  [1] Sumario...")
    bank_info = None
    for facb in analysis.get("facbs", []):
        if facb.get("bank_name"):
            bank_info = facb
            break
    for pg in make_summary(vessel, port, sailed, date, client, advance, tc_groups, bank_info).pages:
        writer.add_page(pg)

    # 2. SOF
    if analysis["sof"]:
        print("  [2] SOF...")
        add_pdf(writer, fp_fn(analysis["sof"]))

    # 3. BNA — si existe
    if analysis["bna"]:
        print("  [3] BNA...")
        add_pdf(writer, fp_fn(analysis["bna"]))

    # 4+. FACBs y vouchers
    port_config = _detect_port(analysis)
    invoice_map = port_config.build_invoice_map(analysis, work_dir, line_amounts)
    tc_inserted = set()
    step = 4

    for entry in invoice_map:
        tc = entry["tc"]

        # Insertar FACBs del TC (una sola vez, en orden NCB→agency→port_expenses)
        if tc not in tc_inserted:
            for (num, lbl, amt) in tc_groups.get(tc, []):
                fname = facb_files.get(num)
                if fname and os.path.exists(fp_fn(fname)):
                    print(f"  [{step}] FACB {num} — {lbl}  (TC {tc:g})")
                    add_pdf(writer, fp_fn(fname))
                    step += 1
            tc_inserted.add(tc)

        # Voucher
        concept = entry["concept"]
        amount  = entry["amount"]
        port_v  = port.replace(" Port", "").replace(" port", "")
        print(f"  [{step}] Voucher: {concept}")
        for pg in make_voucher(concept, amount, tc, vessel, sailed, port_v).pages:
            writer.add_page(pg)
        step += 1

        # Facturas debajo del voucher
        for (fname, pages) in entry.get("invoices", []):
            full = fp_fn(fname)
            if os.path.exists(full):
                n = add_pdf(writer, full, pages)
                print(f"       + {fname}  ({n} pgs)")
            else:
                print(f"       ⚠ {fname}")

    with open(output_path, "wb") as f:
        writer.write(f)

    total_pages = len(list(writer.pages))
    total_exp   = sum(a for facbs in tc_groups.values() for (_, _, a) in facbs)
    balance     = total_exp - advance

    return {
        "pages":     total_pages,
        "total":     total_exp,
        "advance":   advance,
        "balance":   abs(balance),
        "direction": "due to ISA" if balance >= 0 else f"due to {client}",
        "vessel":    vessel,
        "client":    client,
    }









