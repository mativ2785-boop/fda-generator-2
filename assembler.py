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

    Orden de inserción de FACBs (REGLA ISA):
      Para cada TC, en orden ascendente:
        FACB Agency Fee  (si TC == tc_base)
        NCB(s) del TC
        FACB(s) port_expenses del TC
      Todo esto se inserta ANTES del primer voucher que pertenece a ese TC.

    El tc_groups que se pasa a make_summary es una copia — nunca se muta.
    """
    writer = PdfWriter()

    vessel = analysis.get("vessel") or "M/V VESSEL"
    port   = analysis.get("port")   or "Bahia Blanca Port"
    sailed = analysis.get("sailed") or ""
    client = analysis.get("client") or "CLIENT"

    # Copia inmutable para el sumario
    tc_groups_summary = copy.deepcopy(analysis["tc_groups"])

    # Copia de trabajo para el assembler (puede reordenarse)
    tc_groups = copy.deepcopy(analysis["tc_groups"])

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

    # Construir line_amounts
    line_amounts = normalize_line_amounts_with_tc(analysis, work_dir)

    def _is_ncb(lbl):
        ll = lbl.lower()
        return any(k in ll for k in ("crédito","credito","ncb","credit note","nota de cr"))

    # ── Reordenar tc_groups: NCB → Agency → Port_expenses (orden del modelo correcto)
    for tc in tc_groups:
        rows     = tc_groups[tc]
        ncbs     = [(n,l,a) for (n,l,a) in rows if _is_ncb(l)]
        agency   = [(n,l,a) for (n,l,a) in rows if "agency" in l.lower()]
        port_exp = [(n,l,a) for (n,l,a) in rows
                    if not _is_ncb(l) and "agency" not in l.lower()]
        tc_groups[tc] = ncbs + agency + port_exp

    # ── Construir mapa TC → [archivos a insertar ANTES del primer voucher de ese TC]
    # Regla: TODAS las FACBs/NCBs de un TC van antes del PRIMER voucher de ese TC.
    # NO hay inserción parcial ni en dos pasos.
    tc_base = min(tc_groups.keys()) if tc_groups else None

    def _facb_block_for_tc(tc):
        """Retorna lista de (fname) a insertar para el bloque TC."""
        block = []
        for (num, lbl, amt) in tc_groups.get(tc, []):
            fname = facb_files.get(num)
            if fname and os.path.exists(fp_fn(fname)):
                block.append((num, lbl, fname))
        return block

    # ── 1. Sumario ────────────────────────────────────────────────────────
    print("  [1] Sumario...")
    bank_info = next(
        (f for f in analysis.get("facbs", []) if f.get("bank_name")),
        None
    )
    for pg in make_summary(
        vessel, port, sailed, date, client,
        advance, tc_groups_summary, bank_info
    ).pages:
        writer.add_page(pg)

    # ── 2. SOF ────────────────────────────────────────────────────────────
    if analysis["sof"]:
        print("  [2] SOF...")
        add_pdf(writer, fp_fn(analysis["sof"]))

    # ── 3. BNA (solo Bahia Blanca) ────────────────────────────────────────
    port_config = _detect_port(analysis)
    _port_upper = (analysis.get("port") or "").upper()
    _is_bb      = "BAHIA BLANCA" in _port_upper or "BAHÍA BLANCA" in _port_upper

    if analysis["bna"] and _is_bb:
        print("  [3] BNA TC base...")
        add_pdf(writer, fp_fn(analysis["bna"]))

    # ── 4+. Vouchers y FACBs ─────────────────────────────────────────────
    invoice_map = port_config.build_invoice_map(analysis, work_dir, line_amounts)
    tc_inserted = set()   # TCs cuyo bloque FACB ya fue insertado (nunca se repite)
    step        = 4

    for entry in invoice_map:
        tc      = entry["tc"]
        concept = entry["concept"]

        # ── Insertar bloque FACB del TC — exactamente UNA VEZ por TC
        if tc not in tc_inserted and tc in tc_groups:

            # BNA extra para TCs distintos al base (solo Bahia Blanca)
            if _is_bb and tc != tc_base:
                for bna_extra in analysis.get("bna_extra", []):
                    bna_tc = _get_bna_tc(fp_fn(bna_extra))
                    if bna_tc and abs(bna_tc - tc) < 1:
                        print(f"  [{step}] BNA TC {tc:g}")
                        add_pdf(writer, fp_fn(bna_extra))
                        step += 1

            # Insertar todas las FACBs/NCBs de este TC (ya ordenadas: NCB→Agency→Port)
            for (num, lbl, fname) in _facb_block_for_tc(tc):
                print(f"  [{step}] FACB {num} — {lbl} (TC {tc:g})")
                add_pdf(writer, fp_fn(fname))
                step += 1

            tc_inserted.add(tc)  # marcar TC como insertado — nunca más se toca

        # Voucher
        amount          = entry["amount"]
        port_v          = port.replace(" Port", "").replace(" port", "")
        display_concept = concept
        if concept in ("TOLL DUES (AGP)", "TOLL DUES (CARP)"):
            display_concept = "TOLL DUES"

        print(f"  [{step}] Voucher: {display_concept}")
        for pg in make_voucher(display_concept, amount, tc, vessel, sailed, port_v).pages:
            writer.add_page(pg)
        step += 1

        # Facturas debajo del voucher
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











































