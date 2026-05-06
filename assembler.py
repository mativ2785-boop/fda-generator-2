"""
assembler.py  —  ISA FDA Generator · Bahia Blanca
Construye el invoice_map y ensambla el PDF final.
"""

import os, io, re, sys
import fitz  # PyMuPDF
from pypdf import PdfWriter, PdfReader

# Importar sistema de puertos — funciona tanto en local como en Render
def _detect_port(analysis):
    """Detecta el puerto y retorna la config correspondiente."""
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    from ports import detect_port
    return detect_port(analysis)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

PW, PH   = A4
ISA_BLUE = colors.HexColor("#1428B4")
LOGO     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_isa.png")

# Orden canónico de vouchers en Bahia Blanca
VOUCHER_ORDER = [
    "AGENCY FEE",
    "PORT DUES",
    "PERMANENCE DUES",
    "TOLL DUES",
    "PORT PILOTAGE",
    "PORT PILOTAGE (DELAY)",
    "MOORING & UNMOORING SERVICES",
    "TOWAGE SERVICES",
    "CUSTOM HOUSE EXPENSES",
    "CUSTOM HOUSE PERMANENCE",
    "CUSTOM HOUSE (BUNKERING)",
    "MIGRATION EXPENSES",
    "SANITARY DUES AND FREE PRATIQUE",
    "GARBAGE COMPULSORY INSPECTION",
    "WATCHMEN COMPULSORY SERVICES",
    "HEADCLERK COMPULSORY SERVICES",
    "PEST CONTROL",
    "OSRO ANNEX 18",
    "TAX ON CREDIT/DEBIT LAW 25.413",
]

MONTHS_ABBR = {
    "January":"Jan","February":"Feb","March":"Mar","April":"Apr",
    "May":"May","June":"Jun","July":"Jul","August":"Aug",
    "September":"Sep","October":"Oct","November":"Nov","December":"Dec",
}


# ── PDF helpers ───────────────────────────────────────────────────────────────

def fmt_amt(v):
    """Enteros sin .00, decimales con 2 cifras (THE ETERNAL style)."""
    return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"


def add_pdf(writer, path, pages=None):
    """Agrega páginas de un PDF al writer. pages=None → todas."""
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


# ── Voucher page ──────────────────────────────────────────────────────────────

def make_voucher(concept, amount, tc, vessel, sailed, port="BAHIA BLANCA"):
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)

    # Logo centrado
    lw = lh = 120
    if os.path.exists(LOGO):
        c.drawImage(LOGO, (PW-lw)/2, PH-20-lh, width=lw, height=lh,
                    preserveAspectRatio=True, mask="auto")

    port_label = port.upper().replace(" PORT", "")
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.black)
    c.drawString(80, PH-182, port_label)

    c.setLineWidth(1)
    c.line(80, PH-232, 520, PH-232)

    vessel_short = vessel.replace("M/V ","").replace("m/v ","")
    c.setFont("Helvetica-Bold", 24)
    c.drawString(80, PH-257, f"VESSEL: {vessel_short}")

    sailed_s = sailed
    for full, abbr in MONTHS_ABBR.items():
        sailed_s = sailed_s.replace(full, abbr)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(80, PH-277, f"SAILED: {sailed_s}")
    c.drawString(80, PH-297, f"RATE OF EXCHANGE: {tc:g}")

    c.line(80, PH-302, 520, PH-302)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(80, PH-382, concept)

    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(PW/2, PH-482, f"USD {fmt_amt(amount)}")

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawCentredString(PW/2, PH-742,
        "Av. del Libertador 602 - 9th Floor - C1001ABT - Buenos Aires - Argentina")
    c.drawCentredString(PW/2, PH-752,
        "Phone (+54 11) 4819-4100 - Fax (+54 11) 4819-4101 - disbursements@isa-agents.com.ar")

    c.save(); buf.seek(0)
    return PdfReader(buf)


# ── Summary page ──────────────────────────────────────────────────────────────

def make_summary(vessel, port, sailed, date, client, advance, tc_groups):
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)

    # Header
    lw = lh = 95
    if os.path.exists(LOGO):
        c.drawImage(LOGO, 40, PH-20-lh, width=lw, height=lh,
                    preserveAspectRatio=True, mask="auto")
    c.setFont("Helvetica-Bold", 16); c.setFillColor(ISA_BLUE)
    c.drawString(145, PH-45, "INDEPENDENT SHIP AGENTS S.A.")
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(145, PH-60, "www.isa-agents.com.ar")
    c.setFont("Helvetica-Oblique", 11); c.setFillColor(ISA_BLUE)
    c.drawRightString(555, PH-42, "Disbursement Summary")

    c.setStrokeColor(ISA_BLUE)
    c.setLineWidth(3); c.line(40, PH-125, 555, PH-125)
    c.setLineWidth(1); c.line(40, PH-129, 555, PH-129)

    # Vessel data
    y0 = PH-148; RH = 20
    for i, (lbl, val) in enumerate([("To:", client), ("Vessel:", vessel), ("Port:", port)]):
        bg = colors.HexColor("#F2F2F2") if i%2==0 else colors.white
        c.setFillColor(bg); c.rect(40, y0-RH*(i+1), 260, RH, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9); c.drawString(47, y0-RH*(i+1)+6, lbl)
        c.setFont("Helvetica-Bold" if lbl=="To:" else "Helvetica", 9)
        c.drawString(95, y0-RH*(i+1)+6, val)
    for i, (lbl, val) in enumerate([("Sailed:", sailed), ("Date:", date)]):
        bg = colors.HexColor("#F2F2F2") if i%2==0 else colors.white
        c.setFillColor(bg); c.rect(310, y0-RH*(i+1), 245, RH, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9); c.drawString(317, y0-RH*(i+1)+6, lbl)
        c.setFont("Helvetica", 9);      c.drawString(360, y0-RH*(i+1)+6, val)

    # Intro
    ty = y0-RH*3-18
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawString(40, ty, "Dear Sir / Madam,")
    c.drawString(40, ty-14,
        "Please find our final disbursement account for the operations of the concerning vessel during the call at ref. port.")

    # Invoice table
    tbl_top = ty-35; HDR_H = ROW_H = 18
    c.setFillColor(ISA_BLUE)
    c.rect(40, tbl_top-HDR_H, 515, HDR_H, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
    for lbl, x in zip(["Invoice Number","Concept","Port","USD Amount"],
                       [44, 174, 374, 474]):
        c.drawString(x, tbl_top-HDR_H+5, lbl)

    ry = tbl_top-HDR_H; total = 0.0; row_i = 0
    for tc, facbs in sorted(tc_groups.items()):
        for (num, lbl, amt) in facbs:
            bg = colors.white if row_i%2==0 else colors.HexColor("#F2F2F2")
            c.setFillColor(bg); c.rect(40, ry-ROW_H, 515, ROW_H, fill=1, stroke=0)
            is_ncb = "crédito" in lbl.lower() or "ncb" in lbl.lower()
            c.setFillColor(colors.red if is_ncb else colors.black)
            c.setFont("Helvetica", 9)
            c.drawString(44,  ry-ROW_H+5, f"Invoice {num}")
            c.drawString(174, ry-ROW_H+5, lbl)
            c.drawString(374, ry-ROW_H+5, "Bahia Blanca")
            c.drawRightString(555, ry-ROW_H+5, f"{amt:,.2f}")
            total += amt; ry -= ROW_H; row_i += 1

    # Total
    c.setFillColor(colors.white); c.rect(40, ry-ROW_H, 515, ROW_H, fill=1, stroke=0)
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 9)
    c.drawRightString(469, ry-ROW_H+5, "Total Expenses")
    c.drawRightString(555, ry-ROW_H+5, f"{total:,.2f}"); ry -= ROW_H

    # Advance
    if advance > 0:
        c.setFillColor(colors.white); c.rect(40, ry-ROW_H, 515, ROW_H, fill=1, stroke=0)
        c.setFont("Helvetica", 9); c.setFillColor(colors.black)
        c.drawString(174, ry-ROW_H+5, f"Less advanced by {client}")
        c.setFillColor(colors.red)
        c.drawRightString(555, ry-ROW_H+5, f"({advance:,.2f})"); ry -= ROW_H

    # Balance
    balance = total - advance
    label   = "Total due to ISA" if balance >= 0 else f"Total due to {client}"
    c.setFillColor(ISA_BLUE if balance >= 0 else colors.red)
    c.rect(40, ry-ROW_H, 515, ROW_H, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10)
    c.drawString(44, ry-ROW_H+5, label)
    c.drawRightString(555, ry-ROW_H+5, f"{abs(balance):,.2f}"); ry -= ROW_H

    # Closing
    c.setFillColor(colors.black); c.setFont("Helvetica", 9)
    c.drawString(40, ry-18,
        "Please do not hesitate to contact us if you need to elaborate on this disbursement.")
    c.drawString(40, ry-36,
        "We thank you very much for having chosen us as agents. We trust our performance has reached your requirements, and we look")
    c.drawString(40, ry-48, "forward to be of assistance to you in the future.")

    # Bank details
    bk_y = ry-80; bk_w = 275; bk_x = (PW-bk_w)/2
    c.setFillColor(ISA_BLUE); c.rect(bk_x, bk_y, bk_w, 18, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
    c.drawString(bk_x+8, bk_y+5, "Bank Details"); bk_y -= 18
    for lbl, val in [
        ("Bank:",        "Citibank N.A., New York Branch"),
        ("Address:",     "111 Wall Street, New York, NY 10043"),
        ("ABA #:",       "21000089"),
        ("SWIFT:",       "CITIUS33"),
        ("Account No:",  "36404074"),
        ("Beneficiary:", "INDEPENDENT SHIP AGENTS S.A."),
    ]:
        c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor("#CCCCCC"))
        c.rect(bk_x, bk_y-16, bk_w, 16, fill=1, stroke=1)
        c.setFillColor(colors.black); c.setFont("Helvetica", 8)
        c.drawString(bk_x+8, bk_y-11, lbl)
        c.setFont("Helvetica-Bold" if lbl=="Beneficiary:" else "Helvetica", 8)
        c.drawString(bk_x+80, bk_y-11, val); bk_y -= 16

    c.save(); buf.seek(0)
    return PdfReader(buf)


# ── Invoice map ───────────────────────────────────────────────────────────────

def extract_facb_line_amounts(pdf_path):
    """
    Extrae montos por concepto de una FACB de port expenses.
    El formato del PDF tiene cada campo en una línea separada:
    N° / CONCEPTO / 1.00 / MONTO / MONTO_FORMATEADO
    Devuelve dict {CONCEPTO: monto}
    """
    import re
    amounts = {}
    try:
        doc   = fitz.open(pdf_path)
        text  = doc[0].get_text()
        lines = [l.strip() for l in text.split("\n")]
        i = 0
        while i < len(lines):
            # Buscar número de línea standalone (1, 2, 3...)
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

def build_invoice_map(analysis, work_dir):
    """
    Construye lista ordenada de vouchers [{concept, amount, tc, invoices, solo}].
    """
    tc_keys   = sorted(analysis["tc_groups"].keys())
    tc_agency = next((f["tc"] for f in analysis["facbs"] if f.get("type")=="agency"),
                     tc_keys[0] if tc_keys else 1373.5)
    tc_port   = next((f["tc"] for f in analysis["facbs"] if f.get("type")=="port_expenses"),
                     tc_agency)

    # Extraer montos individuales de la FACB de port expenses
    port_facb = next((f for f in analysis["facbs"] if f.get("type")=="port_expenses"), None)
    line_amounts = {}
    if port_facb and port_facb.get("filename"):
        line_amounts = extract_facb_line_amounts(os.path.join(work_dir, port_facb["filename"]))

    def amt(concept_key):
        return line_amounts.get(concept_key.upper(), 0)

    # Agrupar páginas Maritime por voucher — excluir mooring_img de Mooring
    mar_pages = {}
    for m in analysis["maritime"]:
        for pg in m["pages"]:
            v   = pg.get("voucher")
            cat = pg.get("category", "")
            if v == "MOORING & UNMOORING SERVICES" and cat == "mooring_img":
                continue  # Solo incluir página de Amarradores, no imágenes de scan
            if v:
                mar_pages.setdefault(v, []).append((m["filename"], pg["page"]))

    def mar_inv(voucher):
        """Convierte lista plana en [(filename, [sorted_pages])]."""
        raw = mar_pages.get(voucher, [])
        merged = {}
        for fname, pg in raw:
            merged.setdefault(fname, []).append(pg)
        return [(f, sorted(set(pgs))) for f, pgs in merged.items()]

    agency_amt = next((f.get("total", 0) for f in analysis["facbs"]
                       if f.get("type")=="agency"), 0)

    entries = {}

    # Agency Fee
    entries["AGENCY FEE"] = {
        "concept": "AGENCY FEE", "amount": agency_amt,
        "tc": tc_agency, "invoices": [], "solo": True,
    }

    # Port Dues — primera factura del Consorcio
    if analysis["consorcio"]:
        entries["PORT DUES"] = {
            "concept": "PORT DUES", "amount": amt("PORT DUES"), "tc": tc_port,
            "invoices": [(analysis["consorcio"][0], None)],
        }

    # Toll Dues — todas las facturas del Consorcio
    if analysis["consorcio"]:
        entries["TOLL DUES"] = {
            "concept": "TOLL DUES", "amount": amt("TOLL DUES"), "tc": tc_port,
            "invoices": [(f, None) for f in analysis["consorcio"]],
        }

    # Port Pilotage — Donmar
    if analysis["donmar"]:
        entries["PORT PILOTAGE"] = {
            "concept": "PORT PILOTAGE", "amount": amt("PORT PILOTAGE"), "tc": tc_port,
            "invoices": [(f, None) for f in analysis["donmar"]],
        }

    # Mooring — páginas Maritime + facturas de Amarradores separadas
    mooring_inv = mar_inv("MOORING & UNMOORING SERVICES")
    ama_inv     = [(f, None) for f in analysis["amarradores"]]
    if mooring_inv or ama_inv:
        entries["MOORING & UNMOORING SERVICES"] = {
            "concept": "MOORING & UNMOORING SERVICES", "amount": amt("MOORING & UNMOORING SERVICES"), "tc": tc_port,
            "invoices": mooring_inv + ama_inv,
        }

    # Towage — Puerto Mariel
    if analysis["puerto_mariel"]:
        entries["TOWAGE SERVICES"] = {
            "concept": "TOWAGE SERVICES", "amount": amt("TOWAGE SERVICES"), "tc": tc_port,
            "invoices": [(f, None) for f in analysis["puerto_mariel"]],
        }

    # Maritime vouchers en orden
    for voucher in [
        "CUSTOM HOUSE EXPENSES",
        "CUSTOM HOUSE PERMANENCE",
        "CUSTOM HOUSE (BUNKERING)",
        "MIGRATION EXPENSES",
        "SANITARY DUES AND FREE PRATIQUE",
        "GARBAGE COMPULSORY INSPECTION",
        "WATCHMEN COMPULSORY SERVICES",
        "HEADCLERK COMPULSORY SERVICES",
    ]:
        inv = mar_inv(voucher)
        if inv:
            entries[voucher] = {
                "concept": voucher, "amount": amt(voucher), "tc": tc_port,
                "invoices": inv,
            }

    # Pest Control — Maritime + ammoca standalone
    pest_inv  = mar_inv("PEST CONTROL")
    pest_ama  = [(f, None) for f in analysis["ammoca"]]
    if pest_inv or pest_ama:
        entries["PEST CONTROL"] = {
            "concept": "PEST CONTROL", "amount": amt("PEST CONTROL"), "tc": tc_port,
            "invoices": pest_inv + pest_ama,
        }

    # OSRO
    osro_inv = mar_inv("OSRO ANNEX 18")
    if osro_inv:
        entries["OSRO ANNEX 18"] = {
            "concept": "OSRO ANNEX 18", "amount": amt("OSRO ANNEX 18"), "tc": tc_port,
            "invoices": osro_inv,
        }

    # Tax — siempre último
    entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
        "concept": "TAX ON CREDIT/DEBIT LAW 25.413", "amount": amt("TAX ON CREDIT/DEBIT LAW 25.413"),
        "tc": tc_port, "invoices": [], "solo": True,
    }

    # Ordenar según VOUCHER_ORDER
    return [entries[v] for v in VOUCHER_ORDER if v in entries]


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

    fp = lambda f: os.path.join(work_dir, f)
    facb_files = {f["number"]: f["filename"]
                  for f in analysis["facbs"] if f.get("number")}

    # Extraer montos por línea de la FACB de port expenses
    port_facb = next((f for f in analysis["facbs"] if f.get("type")=="port_expenses"), None)
    line_amounts = {}
    if port_facb and port_facb.get("filename"):
        line_amounts = extract_facb_line_amounts(fp(port_facb["filename"]))

    # 1. Sumario
    print("  [1] Sumario...")
    for pg in make_summary(vessel, port, sailed, date, client, advance, tc_groups).pages:
        writer.add_page(pg)

    # 2. SOF
    if analysis["sof"]:
        print("  [2] SOF...")
        add_pdf(writer, fp(analysis["sof"]))

    # 3. BNA
    if analysis["bna"]:
        print("  [3] BNA...")
        add_pdf(writer, fp(analysis["bna"]))

    # 4+. FACBs y vouchers — detectar puerto automáticamente
    port_config = _detect_port(analysis)
    invoice_map = port_config.build_invoice_map(analysis, work_dir, line_amounts)
    tc_inserted = set()
    step = 4

    for entry in invoice_map:
        tc = entry["tc"]

        # Insertar FACBs del TC (una sola vez)
        if tc not in tc_inserted:
            for (num, lbl, amt) in tc_groups.get(tc, []):
                fname = facb_files.get(num)
                if fname and os.path.exists(fp(fname)):
                    print(f"  [{step}] FACB {num} — {lbl}  (TC {tc:g})")
                    add_pdf(writer, fp(fname))
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

        # Facturas debajo
        for (fname, pages) in entry.get("invoices", []):
            full = fp(fname)
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



