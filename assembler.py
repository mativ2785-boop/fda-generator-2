"""
assembler.py — ISA FDA Generator
Version: 2.0 (Jun 2026)

Cambios respecto a v1:
- Lógica de inserción de FACBs reescrita (bug 2 del diagnóstico):
  tc_groups NO se muta antes de pasarse a make_summary.
  Inserción determinista: se itera invoice_map UNA sola vez y se inserta
  el bloque FACB de cada TC exactamente antes del primer voucher de ese TC.
- extract_facb_line_amounts: robusto ante formatos alternativos de texto.
- normalize_line_amounts_with_tc: sin loop anidado O(n²); usa caché.
- make_summary: recibe tc_groups como copia (no muta el original).
"""

import os, io, re, copy
import fitz
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
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "May": "May",     "June": "Jun",     "July": "Jul",  "August": "Aug",
    "September": "Sep","October": "Oct", "November": "Nov","December": "Dec",
}

# ── PDF helpers ───────────────────────────────────────────────────────────────

def _get_bna_tc(bna_path):
    try:
        doc     = fitz.open(bna_path)
        text    = doc[0].get_text()
        vals    = []
        for m in re.findall(r"[\d]+[,\.][\d]{4}", text):
            try:
                vals.append(float(m.replace(",", ".")))
            except Exception:
                pass
        return max(vals) if vals else None
    except Exception:
        return None

def fmt_amt(v):
    return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"

def add_pdf(writer, path, pages=None):
    if not os.path.exists(path):
        print(f"  ⚠ No encontrado: {os.path.basename(path)}")
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
    Genera la página de sumario.
    IMPORTANTE: recibe una COPIA de tc_groups — no muta el original.
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

    c.setStrokeColor(ISA_BLUE);  c.setLineWidth(3)
    c.line(40, PH - 165, 555, PH - 165)
    c.setStrokeColor(ISA_BLUE);  c.setLineWidth(1)
    c.line(40, PH - 169, 555, PH - 169)

    y0 = PH - 188; RH = 20
    for i, (lbl, val) in enumerate([("To:", client), ("Vessel:", vessel), ("Port:", port)]):
        bg = colors.HexColor("#F2F2F2") if i % 2 == 0 else colors.white
        c.setFillColor(bg);          c.rect(40, y0 - RH*(i+1), 260, RH, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9); c.drawString(47, y0 - RH*(i+1) + 6, lbl)
        c.setFont("Helvetica-Bold" if lbl == "To:" else "Helvetica", 9)
        c.drawString(95, y0 - RH*(i+1) + 6, val)

    for i, (lbl, val) in enumerate([("Sailed:", sailed or ""), ("Date:", date)]):
        bg = colors.HexColor("#F2F2F2") if i % 2 == 0 else colors.white
        c.setFillColor(bg);          c.rect(310, y0 - RH*(i+1), 245, RH, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9); c.drawString(317, y0 - RH*(i+1) + 6, lbl)
        c.setFont("Helvetica", 9);      c.drawString(360, y0 - RH*(i+1) + 6, val)

    ty = y0 - RH*3 - 18
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(40, ty, "Dear Sir / Madam,")
    c.drawString(40, ty - 14,
        "Please find our final disbursement account for the operations "
        "of the concerning vessel during the call at ref. port.")

    tbl_top = ty - 35
    HDR_H = ROW_H = 18
    c.setFillColor(ISA_BLUE)
    c.rect(40, tbl_top - HDR_H, 515, HDR_H, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
    for lbl, x in zip(["Invoice Number", "Concept", "Port", "USD Amount"],
                       [44, 174, 374, 474]):
        c.drawString(x, tbl_top - HDR_H + 5, lbl)

    port_short = port.replace(" Port", "").replace(" port", "")

    # Construir filas — orden: NCBs (rojo) → Agency → Port expenses
    def _is_ncb(lbl):
        ll = lbl.lower()
        return any(k in ll for k in ("crédito", "credito", "ncb", "credit note", "nota de cr"))

    all_ncbs    = []
    all_agency  = []
    all_port_exp = []
    for tc in sorted(tc_groups.keys()):
        for (num, lbl, amt) in tc_groups[tc]:
            if   _is_ncb(lbl):             all_ncbs.append((num, lbl, amt))
            elif "agency" in lbl.lower():  all_agency.append((num, lbl, amt))
            else:                          all_port_exp.append((num, lbl, amt))

    all_rows = all_ncbs + all_agency + all_port_exp

    ry    = tbl_top - HDR_H
    total = 0.0
    for row_i, (num, lbl, amt) in enumerate(all_rows):
        bg = colors.white if row_i % 2 == 0 else colors.HexColor("#F2F2F2")
        c.setFillColor(bg);  c.rect(40, ry - ROW_H, 515, ROW_H, fill=1, stroke=0)
        is_ncb = _is_ncb(lbl)
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
        ry    -= ROW_H

    # Total expenses
    c.setFillColor(colors.white); c.rect(40, ry - ROW_H, 515, ROW_H, fill=1, stroke=0)
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 9)
    c.drawRightString(469, ry - ROW_H + 5, "Total Expenses")
    c.drawRightString(555, ry - ROW_H + 5, fmt_amt(total))
    ry -= ROW_H

    # Less advanced
    if advance > 0:
        c.setFillColor(colors.HexColor("#F2F2F2"))
        c.rect(40, ry - ROW_H, 515, ROW_H, fill=1, stroke=0)
        c.setFont("Helvetica", 9);  c.setFillColor(colors.black)
        c.drawString(174, ry - ROW_H + 5, f"Less advanced by {client}")
        c.setFillColor(colors.red)
        c.drawRightString(555, ry - ROW_H + 5, f"({fmt_amt(advance)})")
        ry -= ROW_H

    balance = total - advance
    label   = "Total due to ISA" if balance >= 0 else f"Total due to {client}"
    c.setFillColor(ISA_BLUE if balance >= 0 else colors.red)
    c.rect(40, ry - ROW_H, 515, ROW_H, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10)
    c.drawString(44,  ry - ROW_H + 5, label)
    c.drawRightString(555, ry - ROW_H + 5, fmt_amt(abs(balance)))
    ry -= ROW_H

    c.setFillColor(colors.black); c.setFont("Helvetica", 9)
    c.drawString(40, ry - 18,
        "Please do not hesitate to contact us if you need to elaborate on this disbursement.")
    c.drawString(40, ry - 36,
        "We thank you very much for having chosen us as agents. We trust our performance "
        "has reached your requirements, and we look")
    c.drawString(40, ry - 48, "forward to be of assistance to you in the future.")

    c.setStrokeColor(colors.HexColor("#CCCCCC")); c.setLineWidth(0.5)
    c.line(40, 55, 555, 55)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(ISA_BLUE)
    c.drawString(40, 44, "Independent Ship Agents S.A.")
    c.setFont("Helvetica", 8);     c.setFillColor(colors.black)
    c.drawString(40, 34, "Av. del Libertador 602, 9th Floor | C1001ABT Buenos Aires, Argentina")
    c.drawString(40, 24, "Tel: (+54 11) 4819-4100 | isa@isa-agents.com.ar | www.isa-agents.com.ar")

    # Bank details
    bk_y = ry - 80; bk_w = 275; bk_x = 40
    if bank_info and bank_info.get("bank_name") == "Santander Argentina":
        bank_rows = [
            ("Bank:",        "Santander Argentina"),
            ("Account No:",  bank_info.get("bank_account",     "760-000975/5")),
            ("CBU:",         bank_info.get("bank_cbu",          "0720760220000000097554")),
            ("Beneficiary:", bank_info.get("bank_beneficiary",  "Independent Ship Agents S.A.")),
            ("CUIT:",        bank_info.get("bank_cuit",         "30-70813875-0")),
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

    c.setFillColor(ISA_BLUE); c.rect(bk_x, bk_y, bk_w, 18, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
    c.drawString(bk_x + 8, bk_y + 5, "Bank Details")
    bk_y -= 18
    for lbl, val in bank_rows:
        c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor("#CCCCCC"))
        c.rect(bk_x, bk_y - 16, bk_w, 16, fill=1, stroke=1)
        c.setFillColor(colors.black); c.setFont("Helvetica", 8)
        c.drawString(bk_x + 8, bk_y - 11, lbl)
        c.setFont("Helvetica-Bold" if lbl == "Beneficiary:" else "Helvetica", 8)
        c.drawString(bk_x + 80, bk_y - 11, val)
        bk_y -= 16

    c.save(); buf.seek(0)
    return PdfReader(buf)


# ── Extract line amounts from FACB ────────────────────────────────────────────

def extract_facb_line_amounts(pdf_path):
    """
    Extrae (concepto → monto) de una FACB ISA.
    Soporta múltiples formatos de extracción de texto:
      Formato A: líneas en orden "idx\\nconcepto\\n1.00\\nmonto"
      Formato B: línea única "N  CONCEPTO  1.00  28,037.49"
    """
    amounts = {}
    try:
        doc  = fitz.open(pdf_path)
        text = doc[0].get_text()
    except Exception:
        return amounts

    lines = [l.strip() for l in text.split("\n")]

    # Formato A: número de ítem en línea propia
    i = 0
    while i < len(lines):
        if re.match(r"^\d+$", lines[i]) and i + 3 < len(lines):
            concept = lines[i + 1].strip().upper()
            qty_line = lines[i + 2].strip()
            if qty_line == "1.00":
                try:
                    amount = float(lines[i + 3].replace(",", ""))
                    if amount > 0:
                        amounts[concept] = amount
                    i += 4
                    continue
                except ValueError:
                    pass
        i += 1

    # Formato B: todo en una línea "1  CONCEPTO  1.00  28,037.49"
    # (fallback si Formato A no encontró nada)
    if not amounts:
        for line in lines:
            m = re.match(
                r"^\d+\s+([A-Z][A-Z0-9 /&\.\(\)]+?)\s+1\.00\s+([\d,]+\.\d{2})$",
                line
            )
            if m:
                concept = m.group(1).strip().upper()
                try:
                    amount = float(m.group(2).replace(",", ""))
                    if amount > 0:
                        amounts[concept] = amount
                except ValueError:
                    pass

    return amounts


# ── Normalize keys ────────────────────────────────────────────────────────────

_KEY_ALIASES = {
    "RIVER PLATE PILOTAGE ANCHORAGE":      "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER",
    "RIVER PARANA PILOTAGE ANCHORAG":      "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
    "MANDATORY HOLDS INSPECTION AT":       "MANDATORY HOLDS INSPECTION",
    "HEADCLERK COMPULSORY":                "HEADCLERK COMPULSORY SERVICES",
    "LAUNCH SERVICES FOR CLEARENCE":       "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
    "LAUNCH SERVICES FOR CLEARANCE":       "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
    "FULL ON HIRE DELIVERY BUNKER A":      "FULL ON HIRE / BQS SURVEY",
    "PILOT LAUNCH TRANSPORTATION":         "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
    "PILOT LAUNCH RIVER PLATE":            "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
    # Variantes exactas de conceptos del VTC PHOENIX FACB 30537
    "RIVER PARANA PILOTAGE ANCHORAG":      "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
    "LAUNCH SERV FOR INWARD/OUTWAR":       "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
    "LAUNCH SERV. FOR INWARD/OUTWA":       "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
    "MOORING & UNMORING SERVICES":         "MOORING & UNMOORING SERVICES",
    "MOORING & UNMORING":                  "MOORING & UNMOORING SERVICES",
    "COAST GUARD EXPENSES":                "COAST GUARD EXPENSES",   # pass-through
    "MIGRATION EXPENSES - OUTWARD":        "MIGRATION EXPENSES - OUTWARD",   # pass-through
    "MIGRATION EXPENSES":                  "MIGRATION EXPENSES",
}

def _normalize_key(key):
    k = key.upper().strip().replace("PRACTIQUE", "PRATIQUE").replace("CLEARENCE", "CLEARANCE")
    return _KEY_ALIASES.get(k, k)


def normalize_line_amounts_with_tc(analysis, work_dir):
    """
    Extrae line_amounts por FACB con manejo de TC múltiples.
    Sin loop anidado — usa caché de la primera pasada.
    """
    has_agp  = bool(analysis.get("agp"))
    has_carp = bool(analysis.get("carp"))

    facb_port = [
        (f["tc"], f["filename"])
        for f in analysis.get("facbs", [])
        if f.get("type") == "port_expenses" and f.get("filename") and f.get("tc")
    ]
    facb_port.sort(key=lambda x: x[0])
    tc_base = facb_port[0][0] if facb_port else 0

    # Primera pasada: extraer todos los line_amounts por archivo (caché)
    cache = {}
    for tc, fname in facb_port:
        fpath = os.path.join(work_dir, fname)
        if os.path.exists(fpath):
            cache[(tc, fname)] = extract_facb_line_amounts(fpath)

    # Segunda pasada: construir resultado normalizado
    line_amounts = {}

    for tc, fname in facb_port:
        raw = cache.get((tc, fname), {})
        for k, v in raw.items():
            key = _normalize_key(k)

            # Pilot Launch en TC alto → mantener nombre correcto
            if key.startswith("PILOT LAUNCH"):
                key = "PILOT LAUNCH TRANSPORTATION RIVER PLATE"

            # River Plate Pilotage en TC alto con Glatil → Pilot Launch
            if (key == "RIVER PLATE PILOTAGE"
                    and tc > tc_base
                    and analysis.get("glatil")):
                key = "PILOT LAUNCH TRANSPORTATION RIVER PLATE"

            # Toll Dues → AGP o CARP
            if key == "TOLL DUES":
                if   has_agp and has_carp:
                    # AGP = TC más bajo con TOLL DUES; CARP = TC más alto
                    toll_tcs = sorted(
                        t for (t, fn) in facb_port
                        if "TOLL DUES" in [_normalize_key(kk)
                                           for kk in cache.get((t, fn), {})]
                    )
                    key = "TOLL DUES (AGP)" if tc == min(toll_tcs) else "TOLL DUES (CARP)"
                elif has_agp:  key = "TOLL DUES (AGP)"
                elif has_carp: key = "TOLL DUES (CARP)"

            # Tax en TCs distintos al base → clave con sufijo
            if key == "TAX ON CREDIT/DEBIT LAW 25.413" and tc > tc_base:
                key = f"TAX ON CREDIT/DEBIT LAW 25.413 _TC{tc:g}"

            line_amounts[key] = line_amounts.get(key, 0) + v

    return line_amounts


# ── Build FDA ─────────────────────────────────────────────────────────────────

def build_fda(analysis, work_dir, output_path, advance, date):
    """
    Ensambla el FDA completo.

    REGLA REAL (confirmada del FDA VTC PHOENIX CORRECTO):
      1. SUMARIO
      2. SOF
      3. BNA (del TC base — siempre)
      4. Todas las NCBs (todos los TCs, juntas)
      5. FACB Agency Fee
      6. Vouchers en orden:
         - Para TCs != base: BNA extra justo antes del primer voucher del TC
         - FACB port_exp: justo antes del primer voucher cuyo concepto
           coincide con el primer ítem de esa FACB
    """
    writer = PdfWriter()

    vessel = analysis.get("vessel") or "M/V VESSEL"
    port   = analysis.get("port")   or "San Lorenzo Port"
    sailed = analysis.get("sailed") or ""
    client = analysis.get("client") or "CLIENT"

    tc_groups_summary = copy.deepcopy(analysis["tc_groups"])
    tc_groups         = copy.deepcopy(analysis["tc_groups"])
    fp_fn = lambda f: os.path.join(work_dir, f)

    facb_files = {f["number"]: f["filename"]
                  for f in analysis["facbs"] if f.get("number")}

    if not os.path.exists(LOGO):
        for facb in analysis.get("facbs", []):
            fname = facb.get("filename")
            if fname and os.path.exists(fp_fn(fname)):
                extract_logo_from_facb(fp_fn(fname), LOGO)
                break

    line_amounts = normalize_line_amounts_with_tc(analysis, work_dir)

    def _is_ncb(lbl):
        ll = lbl.lower()
        return any(k in ll for k in ("crédito","credito","ncb","credit note","nota de cr"))

    tc_base = min(tc_groups.keys()) if tc_groups else None

    # Separar NCBs, Agency Fee y port_expenses
    all_ncbs    = []  # (num, lbl, amt, fname, tc)
    agency_facb = []  # (num, lbl, amt, fname, tc)
    port_facbs  = {}  # tc → [(num, lbl, amt, fname)]

    for tc in sorted(tc_groups.keys()):
        for (num, lbl, amt) in tc_groups[tc]:
            fname = facb_files.get(num)
            if not fname or not os.path.exists(fp_fn(fname)):
                continue
            if _is_ncb(lbl):
                all_ncbs.append((num, lbl, amt, fname, tc))
            elif "agency" in lbl.lower():
                agency_facb.append((num, lbl, amt, fname, tc))
            else:
                port_facbs.setdefault(tc, []).append((num, lbl, amt, fname))

    # Mapa: primer concepto de la FACB → (tc, num, fname)
    # Determina ante qué voucher se inserta cada FACB port_exp
    concept_to_facb = {}
    for tc in sorted(port_facbs.keys()):
        for (num, lbl, amt, fname) in port_facbs[tc]:
            la = extract_facb_line_amounts(fp_fn(fname))
            if la:
                first = list(la.keys())[0].upper()
                concept_to_facb[first] = (tc, num, fname)

    port_config = _detect_port(analysis)
    invoice_map = port_config.build_invoice_map(analysis, work_dir, line_amounts)
    step = 4

    # 1. Sumario
    print("  [1] Sumario...")
    bank_info = next((f for f in analysis.get("facbs", []) if f.get("bank_name")), None)
    for pg in make_summary(vessel, port, sailed, date, client,
                           advance, tc_groups_summary, bank_info).pages:
        writer.add_page(pg)

    # 2. SOF
    if analysis["sof"]:
        print("  [2] SOF...")
        add_pdf(writer, fp_fn(analysis["sof"]))

    # 3. BNA del TC base (siempre)
    if analysis["bna"]:
        print("  [3] BNA...")
        add_pdf(writer, fp_fn(analysis["bna"]))

    # 4. Todas las NCBs juntas — orden DESCENDENTE por TC (el más alto primero)
    all_ncbs.sort(key=lambda x: x[4], reverse=True)
    for (num, lbl, amt, fname, tc) in all_ncbs:
        print(f"  [{step}] NCB {num} (TC {tc:g})")
        add_pdf(writer, fp_fn(fname))
        step += 1

    # 5. FACB Agency Fee
    for (num, lbl, amt, fname, tc) in agency_facb:
        print(f"  [{step}] FACB Agency {num} (TC {tc:g})")
        add_pdf(writer, fp_fn(fname))
        step += 1

    # 5b. FACBs port_exp de TCs DISTINTOS al base cuyo PRIMER CONCEPTO
    #     aparece ANTES que el primer voucher del TC base.
    #     Solo las FACBs cuyo primer concepto matchea un voucher que viene
    #     antes de PORT DUES (primer voucher del TC base).
    # REGLA: cada FACB va JUSTO ANTES de su primer voucher, no todas juntas.
    # Para TC 1462.74: FACB 30544 tiene primer concepto PILOT LAUNCH
    #   → va justo antes del voucher PILOT LAUNCH
    # Para TC 1400: FACB 30536 tiene primer concepto TOLL DUES
    #   → va justo antes del voucher TOLL DUES
    # → NINGUNA va aquí en el bloque inicial; todas se insertan inline en el loop
    pass  # inserción inline en el loop de vouchers

    # 6. Vouchers con FACBs port_exp intercaladas inline
    tc_bna_inserted  = set()
    tc_facb_inserted = set()

    def _bna_for_tc(tc):
        for bna_extra in analysis.get("bna_extra", []):
            bna_tc_val = _get_bna_tc(fp_fn(bna_extra))
            if bna_tc_val and abs(bna_tc_val - tc) < 2:
                return bna_extra
        return None

    for entry in invoice_map:
        tc         = entry["tc"]
        concept    = entry["concept"]
        concept_up = concept.upper()

        # Suprimir voucher AGENCY FEE del cuerpo del FDA
        if concept_up == "AGENCY FEE":
            continue

        # FACB port_exp primero, luego BNA (orden del FDA correcto: FACB → BNA → voucher)
        if tc != tc_base:
            # 1. FACB
            if tc not in tc_facb_inserted and tc in port_facbs:
                for first_concept, (ftc, fnum, ffname) in concept_to_facb.items():
                    if ftc != tc:
                        continue
                    if (first_concept in concept_up or
                            concept_up in first_concept or
                            any(word in concept_up for word in first_concept.split()[:3]
                                if len(word) > 4)):
                        print(f"  [{step}] FACB {fnum} (TC {tc:g})")
                        add_pdf(writer, fp_fn(ffname))
                        step += 1
                        tc_facb_inserted.add(tc)
                        break
            # 2. BNA después de la FACB
            if tc not in tc_bna_inserted:
                bna_file = _bna_for_tc(tc)
                if bna_file:
                    print(f"  [{step}] BNA TC {tc:g}")
                    add_pdf(writer, fp_fn(bna_file))
                    step += 1
                tc_bna_inserted.add(tc)
        else:
            # TC base: solo FACB (BNA base ya fue insertado al inicio)
            if tc not in tc_facb_inserted and tc in port_facbs:
                for first_concept, (ftc, fnum, ffname) in concept_to_facb.items():
                    if ftc != tc:
                        continue
                    if (first_concept in concept_up or
                            concept_up in first_concept or
                            any(word in concept_up for word in first_concept.split()[:3]
                                if len(word) > 4)):
                        print(f"  [{step}] FACB {fnum} (TC {tc:g})")
                        add_pdf(writer, fp_fn(ffname))
                        step += 1
                        tc_facb_inserted.add(tc)
                        break

        # Voucher
        port_v = port.replace(" Port", "").replace(" port", "")
        display = concept
        if concept in ("TOLL DUES (AGP)", "TOLL DUES (CARP)"):
            display = "TOLL DUES"
        print(f"  [{step}] Voucher: {display} (TC {tc:g})")
        for pg in make_voucher(display, entry["amount"], tc, vessel, sailed, port_v).pages:
            writer.add_page(pg)
        step += 1

        for (fname, pages) in entry.get("invoices", []):
            full = fp_fn(fname)
            if os.path.exists(full):
                n = add_pdf(writer, full, pages)
                print(f"    + {fname} ({n} pgs)")
            else:
                print(f"    ⚠ {fname}")

    with open(output_path, "wb") as f:
        writer.write(f)

    total_pages = len(list(writer.pages))
    total_exp = sum(
        amt for tc in tc_groups_summary.values()
        for (num, lbl, amt) in tc
        if not _is_ncb(lbl)
    )
    balance = total_exp - advance
    return {
        "pages":     total_pages,
        "total":     total_exp,
        "advance":   advance,
        "balance":   abs(balance),
        "direction": "due to ISA" if balance >= 0 else f"due to {client}",
        "vessel":    vessel,
        "client":    client,
    }











































