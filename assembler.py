"""
assembler.py  —  ISA FDA Generator
Construye el invoice_map y ensambla el PDF final.
Soporta: Bahia Blanca, Necochea, San Lorenzo / Arroyo Seco / Gral. Lagos

FIX #1: Las FACBs de cada TC se insertan ANTES del PRIMER voucher de ese TC.
  - El TC de Agency Fee determina cuándo insertar NCB + FACB Agency + FACBs del mismo TC.
  - Los TCs siguientes (ej. 1385, 1457) insertan su bloque de FACBs justo antes
    del primer voucher de ese TC (Toll Dues AGP, Toll Dues CARP, River Plate TC1457, etc.).
  - Esto garantiza el orden correcto: Agency Fee va primero como voucher, y las
    FACBs se insertan en el orden correcto respecto a sus vouchers.
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
    "January": "Jan", "February": "Feb", "March": "Mar",   "April": "Apr",
    "May": "May",     "June": "Jun",     "July": "Jul",     "August": "Aug",
    "September": "Sep","October": "Oct", "November": "Nov", "December": "Dec",
}


# ── PDF helpers ───────────────────────────────────────────────────────────────

def _get_bna_tc(bna_path):
    """Lee el TC de un archivo BNA del Banco Nación."""
    try:
        import fitz as _fitz
        doc = _fitz.open(bna_path)
        text = doc[0].get_text()
        import re as _re
        # Buscar el valor de venta (el TC fiscal)
        matches = _re.findall(r"[\d]+[,\.][\d]{4}", text)
        vals = []
        for m in matches:
            try:
                vals.append(float(m.replace(",", ".")))
            except Exception:
                pass
        # El TC es el valor más alto (venta)
        if vals:
            return max(vals)
    except Exception:
        pass
    return None


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
    # REGLA ISA: en el sumario → NCBs primero (en rojo), luego Agency Fee, luego Port Expenses
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


# ── Normalize line_amounts with TC awareness ─────────────────────────────────

def normalize_line_amounts_with_tc(analysis, work_dir):
    """
    Extrae line_amounts por FACB con manejo inteligente de TC múltiples.
    
    Reglas especiales:
    - TOLL DUES → TOLL DUES (AGP) o TOLL DUES (CARP) según TC y proveedores
    - RIVER PLATE PILOTAGE en TC alto (con Glatil) → PILOT LAUNCH TRANSPORTATION RIVER PLATE
    - TAX ON CREDIT/DEBIT LAW 25.413 en TCs distintos al base → clave con sufijo _TC{n}
    """
    line_amounts = {}
    has_agp  = bool(analysis.get("agp"))
    has_carp = bool(analysis.get("carp"))
    
    facb_port = [(f["tc"], f["filename"]) for f in analysis.get("facbs", [])
                 if f.get("type") == "port_expenses" and f.get("filename") and f.get("tc")]
    facb_port.sort(key=lambda x: x[0])
    tcs_sorted = [tc for tc, _ in facb_port]
    tc_base = tcs_sorted[0] if tcs_sorted else 0
    
    for tc, fname in facb_port:
        fpath = os.path.join(work_dir, fname)
        if not os.path.exists(fpath):
            continue
        la = extract_facb_line_amounts(fpath)
        
        for k, v in la.items():
            key = k.upper().strip()
            key = key.replace("PRACTIQUE", "PRATIQUE").replace("CLEARENCE", "CLEARANCE")
            if key == "RIVER PLATE PILOTAGE ANCHORAGE": key = "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER"
            if key == "RIVER PARANA PILOTAGE ANCHORAG": key = "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER"
            if key == "MANDATORY HOLDS INSPECTION AT":  key = "MANDATORY HOLDS INSPECTION"
            if key == "HEADCLERK COMPULSORY":           key = "HEADCLERK COMPULSORY SERVICES"
            if key in ("LAUNCH SERVICES FOR CLEARENCE","LAUNCH SERVICES FOR CLEARANCE"):
                key = "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"
            if key == "FULL ON HIRE DELIVERY BUNKER A": key = "FULL ON HIRE / BQS SURVEY"
            
            # TOLL DUES → AGP o CARP según TC
            if key == "TOLL DUES":
                if has_agp and has_carp:
                    toll_tcs = sorted(set(
                        t for t, fn in facb_port
                        if "TOLL DUES" in [kk.upper() for kk in extract_facb_line_amounts(os.path.join(work_dir, fn)).keys()]
                    ))
                    key = "TOLL DUES (AGP)" if toll_tcs and tc == min(toll_tcs) else "TOLL DUES (CARP)"
                elif has_agp:
                    key = "TOLL DUES (AGP)"
                elif has_carp:
                    key = "TOLL DUES (CARP)"
            
            # RIVER PLATE PILOTAGE en TC alto → PILOT LAUNCH (Glatil)
            if key == "RIVER PLATE PILOTAGE" and tc > tc_base and analysis.get("glatil"):
                key = "PILOT LAUNCH TRANSPORTATION RIVER PLATE"
            
            # TAX en TCs distintos al base → clave separada por TC
            if key == "TAX ON CREDIT/DEBIT LAW 25.413" and tc > tc_base:
                key = f"TAX ON CREDIT/DEBIT LAW 25.413 _TC{tc:g}"
            
            line_amounts[key] = line_amounts.get(key, 0) + v
    
    return line_amounts


# ── Build FDA ─────────────────────────────────────────────────────────────────

def build_fda(analysis, work_dir, output_path, advance, date):
    """
    Ensambla el FDA completo. Retorna dict con estadísticas.

    FIX #1 — Orden de inserción de FACBs:
    Las FACBs de cada TC se insertan ANTES del primer voucher de ese TC.
    Orden dentro del grupo TC: NCB(s) → Agency Fee → Port Expenses.
    Esto garantiza que FACB 30317 (TC 1345) quede DESPUÉS del voucher Agency Fee,
    y que los grupos TC 1385 y TC 1457 aparezcan antes de sus vouchers respectivos.
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

    # Extraer logo si no existe
    if not os.path.exists(LOGO):
        for facb in analysis.get("facbs", []):
            fname = facb.get("filename")
            if fname and os.path.exists(fp_fn(fname)):
                extract_logo_from_facb(fp_fn(fname), LOGO)
                break

    # Combinar line_amounts — usar versión con TC-awareness para mapear TOLL DUES correctamente
    line_amounts = normalize_line_amounts_with_tc(analysis, work_dir)

    # Ordenar tc_groups: dentro de cada TC → NCBs, agency, port_expenses
    for tc in tc_groups:
        rows = tc_groups[tc]
        def _is_ncb(lbl):
            ll = lbl.lower()
            # FIX B6: detectar NCB con tilde, sin tilde, y por tipo ya extraído
            return ("crédito" in ll or "credito" in ll or "ncb" in ll or
                    "credit note" in ll or "nota de cr" in ll)
        ncbs     = [(n, l, a) for (n, l, a) in rows if _is_ncb(l)]
        agency   = [(n, l, a) for (n, l, a) in rows if "agency" in l.lower()]
        port_exp = [(n, l, a) for (n, l, a) in rows
                    if not _is_ncb(l) and "agency" not in l.lower()]
        # REGLA ISA: dentro de cada TC → Agency Fee PRIMERO, luego NCB(s), luego Port Expenses
        tc_groups[tc] = agency + ncbs + port_exp

    # ── 1. Sumario ────────────────────────────────────────────────────────────
    print("  [1] Sumario...")
    bank_info = None
    for facb in analysis.get("facbs", []):
        if facb.get("bank_name"):
            bank_info = facb
            break
    for pg in make_summary(vessel, port, sailed, date, client, advance, tc_groups, bank_info).pages:
        writer.add_page(pg)

    # ── 2. SOF ────────────────────────────────────────────────────────────────
    if analysis["sof"]:
        print("  [2] SOF...")
        add_pdf(writer, fp_fn(analysis["sof"]))

    # ── 3. BNA (solo Bahia Blanca lo incluye — San Lorenzo y otros NO) ─────────
    # Detectar puerto ANTES de insertar BNA para saber si corresponde
    port_config = _detect_port(analysis)
    _port_upper = (analysis.get("port") or "").upper()
    _is_bahia_blanca = "BAHIA BLANCA" in _port_upper or "BAHÍA BLANCA" in _port_upper
    if analysis["bna"] and _is_bahia_blanca:
        print("  [3] BNA...")
        add_pdf(writer, fp_fn(analysis["bna"]))

    # ── 4+. FACBs y vouchers ──────────────────────────────────────────────────
    # (port_config ya detectado arriba)
    invoice_map = port_config.build_invoice_map(analysis, work_dir, line_amounts)

    # FIX #1: Determinar el TC de cada entry para saber cuándo insertar FACBs.
    # Las FACBs del TC del Agency Fee se insertan inmediatamente DESPUÉS del SOF/BNA
    # y ANTES del primer voucher (Agency Fee). Los TCs siguientes se insertan
    # antes del primer voucher que use ese TC.
    tc_inserted = set()
    step = 4

    # Determinar el TC del Agency Fee (primer TC en orden)
    tc_agency = min(tc_groups.keys()) if tc_groups else None

    # FIX #1 (revisado): 
    # Antes del voucher Agency Fee: solo NCBs + FACB Agency del TC base.
    # La FACB de port_expenses del TC base se inserta antes del voucher PORT DUES
    # (es decir, después del voucher Agency Fee).
    # Los TCs siguientes (1385, 1457) se insertan antes de sus vouchers.
    if tc_agency and tc_agency not in tc_inserted:
        # Solo NCBs y agency del TC base antes del Agency Fee
        for (num, lbl, amt) in tc_groups.get(tc_agency, []):
            if "port" in lbl.lower() and "agency" not in lbl.lower() and "crédito" not in lbl.lower():
                continue  # Las port_expenses del TC base van después del Agency Fee
            fname = facb_files.get(num)
            if fname and os.path.exists(fp_fn(fname)):
                print(f"  [{step}] FACB {num} — {lbl}  (TC {tc_agency:g})")
                add_pdf(writer, fp_fn(fname))
                step += 1
        tc_inserted.add(tc_agency)
    # Marcar TC base como "parcialmente insertado" — las port_expenses se insertan luego
    tc_port_expenses_inserted = set()

    for entry in invoice_map:
        tc = entry["tc"]
        concept = entry["concept"]

        # Para el TC base: insertar las FACB de port_expenses SIEMPRE después del
        # voucher AGENCY FEE (antes del primer voucher de CUALQUIER TC que no sea
        # el Agency Fee). Esto cubre el caso donde todos los demás vouchers son de
        # TCs distintos al TC base.
        if tc_agency not in tc_port_expenses_inserted and concept != "AGENCY FEE":
            for (num, lbl, amt) in tc_groups.get(tc_agency, []):
                lbl_n = lbl.lower()
                # Solo port_expenses: ni agency ni NCB
                is_port_exp = ("port" in lbl_n or "expenses" in lbl_n) and "agency" not in lbl_n and "cr" not in lbl_n
                if is_port_exp:
                    fname = facb_files.get(num)
                    if fname and os.path.exists(fp_fn(fname)):
                        print(f"  [{step}] FACB {num} — {lbl}  (TC {tc_agency:g}, port_exp base)")
                        add_pdf(writer, fp_fn(fname))
                        step += 1
            tc_port_expenses_inserted.add(tc_agency)

        # Para TCs distintos al del Agency Fee: insertar BNA extra + FACBs antes del primer voucher
        if tc not in tc_inserted:
            # Insertar BNA extra solo en Bahia Blanca — San Lorenzo NO incluye BNA
            if _is_bahia_blanca:
                bna_extra_list = analysis.get("bna_extra", [])
                for bna_extra in bna_extra_list:
                    # Verificar si el BNA corresponde a este TC (por cotización)
                    bna_tc = _get_bna_tc(fp_fn(bna_extra))
                    if bna_tc and abs(bna_tc - tc) < 1:
                        print(f"  [{step}] BNA extra TC {tc:g}")
                        add_pdf(writer, fp_fn(bna_extra))
                        step += 1

            for (num, lbl, amt) in tc_groups.get(tc, []):
                fname = facb_files.get(num)
                if fname and os.path.exists(fp_fn(fname)):
                    print(f"  [{step}] FACB {num} — {lbl}  (TC {tc:g})")
                    add_pdf(writer, fp_fn(fname))
                    step += 1
            tc_inserted.add(tc)

        # Voucher — mapear nombres de display
        amount  = entry["amount"]
        port_v  = port.replace(" Port", "").replace(" port", "")
        # Los vouchers de Toll Dues se imprimen como "TOLL DUES" independientemente del proveedor
        display_concept = concept
        if concept in ("TOLL DUES (AGP)", "TOLL DUES (CARP)"):
            display_concept = "TOLL DUES"
        # FIX B5: Pilot Launch Transportation River Plate se muestra con su nombre correcto
        # NO como "RIVER PLATE PILOTAGE" — son vouchers distintos
        print(f"  [{step}] Voucher: {display_concept}")
        for pg in make_voucher(display_concept, amount, tc, vessel, sailed, port_v).pages:
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
































