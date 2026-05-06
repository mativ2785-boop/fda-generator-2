"""
classifier.py  —  ISA FDA Generator · Bahia Blanca
Detecta qué es cada PDF leyendo su contenido (no el nombre).
ZIPs con PDFs siempre en la raíz (sin subcarpetas).
"""

import os, re, zipfile
import fitz  # PyMuPDF


# ══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════════════════════

def read_text(pdf_path, max_pages=3):
    """Devuelve texto concatenado de las primeras N páginas."""
    try:
        doc = fitz.open(pdf_path)
        n   = min(doc.page_count, max_pages)
        return " ".join(doc[i].get_text() for i in range(n))
    except Exception:
        return ""


def read_page(pdf_path, idx):
    """Devuelve texto de una página específica (0-based)."""
    try:
        doc = fitz.open(pdf_path)
        if idx >= doc.page_count:
            return ""
        return doc[idx].get_text()
    except Exception:
        return ""


def page_count(pdf_path):
    try:
        return fitz.open(pdf_path).page_count
    except Exception:
        return 0


def is_image_page(pdf_path, idx):
    """True si la página tiene imagen pero casi sin texto (ej: scan de mooring)."""
    try:
        doc  = fitz.open(pdf_path)
        page = doc[idx]
        return len(page.get_images()) > 0 and len(page.get_text().strip()) < 60
    except Exception:
        return False


def extract_zip(zip_path, dest_dir):
    """Extrae los PDFs del ZIP (siempre en raíz) al directorio destino."""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            fname = os.path.basename(member)
            if not fname or not fname.lower().endswith(".pdf"):
                continue
            dst = os.path.join(dest_dir, fname)
            with z.open(member) as src, open(dst, "wb") as out:
                out.write(src.read())
    return [f for f in os.listdir(dest_dir) if f.lower().endswith(".pdf")]


# ══════════════════════════════════════════════════════════════════════════════
#  CLASIFICADOR DE DOCUMENTOS (nivel PDF completo)
# ══════════════════════════════════════════════════════════════════════════════

# Cada tipo: lista de strings que deben aparecer en las primeras páginas
DOC_TYPES = [
    # Orden importa: más específico primero
    ("sof",           ["DETAILS OF DAILY WORKING"]),
    ("sof",           ["Standard Statement on Fact"]),
    ("sof",           ["Statement of Facts"]),
    ("bna",           ["Cotizaciones históricas", "Dolar U.S.A"]),
    ("bna",           ["Banco de la Naci", "Cotizaciones"]),
    # FACB ISA: chequeo doble para evitar falsos positivos
    ("facb_isa",      ["INDEPENDENT SHIP AGENTS", "FACTURA", "INVOICE"]),
    ("facb_isa",      ["INDEPENDENT SHIP AGENTS", "B00003"]),
    ("consorcio",     ["Consorcio de Gestión del Puerto de Bahia Blanca"]),
    ("consorcio",     ["CONSORCIO DE GESTION DEL PUERTO DE BAHIA BLANCA"]),
    ("donmar",        ["DONMAR S.A."]),
    ("puerto_mariel", ["PUERTO MARIEL"]),
    ("puerto_mariel", ["ARGENTINA TOWAGE"]),
    ("maritime",      ["MARITIME SHIPPING AGENCY"]),
    ("amarradores",   ["AMARRADORES DEL PUERTO DE BAHIA BLANCA"]),
    ("ammoca",        ["AMMOCA S.A."]),
    ("centro_nav",    ["Centro de Navegación Asociación Civil"]),
    ("centro_nav",    ["cnav.org.ar"]),
]


def classify_doc(pdf_path):
    """Devuelve el tipo del documento o 'unknown'."""
    text = read_text(pdf_path, max_pages=3)
    for (dtype, keywords) in DOC_TYPES:
        if all(kw in text for kw in keywords):
            return dtype
    return "unknown"


# ══════════════════════════════════════════════════════════════════════════════
#  CLASIFICADOR DE PÁGINAS DE MARITIME
# ══════════════════════════════════════════════════════════════════════════════

# Reglas: (categoría, [keywords requeridos])
# Se evalúan en orden — primera que matchea gana
MARITIME_PAGE_RULES = [
    ("skip",              ["FACT CRED ELECT"]),
    ("skip",              ["MiPyME"]),
    ("skip",              ["Disbursement Account"]),
    ("headclerk_break",   ["HEAD CLERK", "Breakdown"]),
    ("headclerk_liq",     ["LIQUIDACION DE PAGO A ENCARGADOS"]),
    ("watchmen_break",    ["WATCHMEN", "Breakdown"]),
    ("watchmen_liq",      ["LIQUIDACION DE PAGO", "SERENO"]),
    ("afip_lman",         ["LMAN", "ADMINISTRACION FEDERAL DE INGRESOS"]),
    ("se_inward",         ["SOLICITUD DE HABILITACION", "FORMALIZACION DE ENTRADA"]),
    ("se_inward",         ["SOLICITUD DE HABILITACION", "FEVA"]),
    ("se_permanencia",    ["SOLICITUD DE HABILITACION", "permanencia"]),
    ("se_permanencia",    ["SOLICITUD DE HABILITACION", "PERMANENCIA"]),
    ("se_rancho",         ["SOLICITUD DE HABILITACION", "RANCHO"]),
    ("se_rancho",         ["SOLICITUD DE HABILITACION", "VLSFO"]),
    ("migraciones_liq",   ["Migraciones", "quincena"]),
    ("migraciones_liq",   ["Migraciones", "Liquidaci"]),
    ("migraciones_sol",   ["Servicios Marítimos y Fluviales", "Solicitud de Servicio"]),
    ("orden_transporte",  ["ORDEN DE TRANSPORTE"]),
    ("sanidad_cert",      ["Libre Plática"]),
    ("sanidad_cert",      ["Certificado de Libre"]),
    ("sanidad_transf",    ["MINISTERIO DE SALUD", "COMPULSORY SANITARY"]),
    ("sanidad_transf",    ["MINISTERIO DE SALUD"]),
    ("sanidad_recibo",    ["FREE PRACTIQUE", "Recib"]),
    ("senasa",            ["SENASA", "BOLETA DE PAGO"]),
    ("senasa",            ["DNO004"]),
    ("amarradores_pag",   ["AMARRADORES"]),
    ("osro",              ["OSRO", "BARRERAS FLOTANTES"]),
    ("osro",              ["COMPULSORY BARRIER"]),
    ("pest_pag",          ["AMMOCA"]),
]

# Mapa: categoría de página → voucher destino
PAGE_TO_VOUCHER = {
    "headclerk_break":   "HEADCLERK COMPULSORY SERVICES",
    "headclerk_liq":     "HEADCLERK COMPULSORY SERVICES",
    "watchmen_break":    "WATCHMEN COMPULSORY SERVICES",
    "watchmen_liq":      "WATCHMEN COMPULSORY SERVICES",
    "afip_lman":         "CUSTOM HOUSE EXPENSES",
    "se_inward":         "CUSTOM HOUSE EXPENSES",
    "se_permanencia":    "CUSTOM HOUSE PERMANENCE",
    "se_rancho":         "CUSTOM HOUSE (BUNKERING)",
    "migraciones_liq":   "MIGRATION EXPENSES",
    "migraciones_sol":   "MIGRATION EXPENSES",
    "orden_transporte":  "MIGRATION EXPENSES",
    "sanidad_cert":      "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_transf":    "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_recibo":    "SANITARY DUES AND FREE PRATIQUE",
    "senasa":            "GARBAGE COMPULSORY INSPECTION",
    "amarradores_pag":   "MOORING & UNMOORING SERVICES",
    "mooring_img":       "MOORING & UNMOORING SERVICES",
    "osro":              "OSRO ANNEX 18",
    "pest_pag":          "PEST CONTROL",
    "skip":              None,
    "skip_dup":          None,
    "unknown":           None,
}


def classify_maritime_pages(pdf_path):
    """
    Analiza cada página de un PDF de Maritime.
    Devuelve lista de dicts: [{page, category, voucher}]
    """
    n      = page_count(pdf_path)
    result = []
    seen_lman = set()   # evitar duplicar AFIP LMAN con misma referencia

    for i in range(n):
        text = read_page(pdf_path, i)

        # Imagen pura → mooring scan
        if is_image_page(pdf_path, i):
            result.append({"page": i, "category": "mooring_img",
                           "voucher": "MOORING & UNMOORING SERVICES"})
            continue

        # Aplicar reglas
        cat = "unknown"
        for (category, keywords) in MARITIME_PAGE_RULES:
            if all(kw in text for kw in keywords):
                cat = category
                break

        # Deduplicar AFIP LMAN por referencia
        if cat == "afip_lman":
            m   = re.search(r"LMAN(\w+)", text)
            ref = m.group(1) if m else f"p{i}"
            if ref in seen_lman:
                cat = "skip_dup"
            else:
                seen_lman.add(ref)

        voucher = PAGE_TO_VOUCHER.get(cat, None)
        result.append({"page": i, "category": cat, "voucher": voucher})

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACCIÓN DE DATOS DE FACB ISA
# ══════════════════════════════════════════════════════════════════════════════

def extract_facb(pdf_path):
    """Extrae número, TC, monto, tipo, cliente y buque de una FACB ISA."""
    text = read_text(pdf_path, max_pages=2)
    d    = {}

    m = re.search(r"B0+3-0*(\d+)", text)
    if m:
        d["number"] = m.group(1)

    m = re.search(r"ARS/USD\s*=\s*([\d,.]+)", text)
    if m:
        d["tc"] = float(m.group(1).replace(",", ""))

    m = re.search(r"TOTAL\s+USD\s+([\d,]+\.?\d*)", text)
    if m:
        d["total"] = float(m.group(1).replace(",", ""))

    if "AGENCY FEE" in text.upper():
        d["type"]  = "agency"
        d["label"] = "Agency fee"
    elif "NCB" in text or "NOTA DE CREDITO" in text.upper():
        d["type"]  = "ncb"
        d["label"] = "Nota de crédito"
    else:
        d["type"]  = "port_expenses"
        d["label"] = "Port expenses"

    m = re.search(r"SEÑORES/CUSTOMER\s*:\s*(.+?)(?:DOMICILIO|CUIT|\n|$)", text)
    if m:
        d["client"] = m.group(1).strip()

    # Buque desde la línea "M/V NOMBRE  DD-MM-YYYY"
    m = re.search(r"M/V\s+([A-Z][A-Z\s]+?)\s+\d{2}[-/]\d{2}[-/]", text)
    if m:
        d["vessel"] = "M/V " + m.group(1).strip()

    return d


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACCIÓN DE DATOS DEL SOF
# ══════════════════════════════════════════════════════════════════════════════

MONTH_MAP = {
    "01":"January","02":"February","03":"March","04":"April",
    "05":"May","06":"June","07":"July","08":"August",
    "09":"September","10":"October","11":"November","12":"December",
}

def extract_sof(pdf_path):
    """Extrae vessel, sailed, port del SOF."""
    text = read_text(pdf_path, max_pages=2)
    d    = {}

    # Vessel: línea "m.v. "THE ETERNAL""
    m = re.search(r'm\.v\.\s*["\']?([A-Z][A-Z0-9\s"\']+?)["\']?\s*[\r\n]', text)
    if m:
        d["vessel"] = "M/V " + m.group(1).strip().strip("\"'")

    # Sailed: fecha en formato DD/MM/YYYY o similar
    m = re.search(r'Sailed?\s*[\r\n\s:]+(\d{1,2})/(\d{2})/(\d{4})', text)
    if m:
        day, mon, yr = m.group(1), m.group(2), m.group(3)
        d["sailed"] = f"{MONTH_MAP.get(mon, mon)} {int(day)}, {yr}"

    if "Bahia Blanca" in text or "BAHIA BLANCA" in text:
        d["port"] = "Bahia Blanca Port"

    return d


# ══════════════════════════════════════════════════════════════════════════════
#  ANÁLISIS COMPLETO DEL DIRECTORIO
# ══════════════════════════════════════════════════════════════════════════════

def analyze(work_dir):
    """
    Escanea todos los PDFs del directorio y devuelve un dict completo.
    """
    pdfs = sorted(f for f in os.listdir(work_dir) if f.lower().endswith(".pdf"))

    result = {
        # Archivos por tipo
        "sof":           None,
        "bna":           None,
        "facbs":         [],      # [{filename, number, tc, total, type, label, client, vessel}]
        "consorcio":     [],
        "donmar":        [],
        "puerto_mariel": [],
        "maritime":      [],      # [{filename, pages:[{page, category, voucher}]}]
        "amarradores":   [],
        "ammoca":        [],
        "centro_nav":    [],
        "unknown":       [],
        # Datos inferidos
        "vessel":    None,
        "client":    None,
        "sailed":    None,
        "port":      None,
        "tc_groups": {},  # {tc: [(number, label, amount)]}
    }

    for fname in pdfs:
        fpath = os.path.join(work_dir, fname)
        dtype = classify_doc(fpath)

        if dtype == "sof":
            result["sof"] = fname
            sof = extract_sof(fpath)
            result["vessel"] = result["vessel"] or sof.get("vessel")
            result["sailed"] = result["sailed"] or sof.get("sailed")
            result["port"]   = result["port"]   or sof.get("port")

        elif dtype == "bna":
            result["bna"] = fname

        elif dtype == "facb_isa":
            d = extract_facb(fpath)
            d["filename"] = fname
            result["facbs"].append(d)
            result["client"] = result["client"] or d.get("client")
            result["vessel"] = result["vessel"] or d.get("vessel")
            tc  = d.get("tc", 0)
            num = d.get("number", "?")
            lbl = d.get("label", "Port expenses")
            amt = d.get("total", 0.0)
            if tc:
                result["tc_groups"].setdefault(tc, []).append((num, lbl, amt))

        elif dtype == "consorcio":
            result["consorcio"].append(fname)
        elif dtype == "donmar":
            result["donmar"].append(fname)
        elif dtype == "puerto_mariel":
            result["puerto_mariel"].append(fname)
        elif dtype == "maritime":
            pages = classify_maritime_pages(fpath)
            result["maritime"].append({"filename": fname, "pages": pages})
        elif dtype == "amarradores":
            result["amarradores"].append(fname)
        elif dtype == "ammoca":
            result["ammoca"].append(fname)
        elif dtype == "centro_navegacion":
            result["centro_nav"].append(fname)
        else:
            result["unknown"].append(fname)

    # Orden: agency primero en FACBs y en tc_groups
    type_order = {"agency": 0, "ncb": 1, "port_expenses": 2}
    result["facbs"].sort(key=lambda f: (type_order.get(f.get("type",""), 9), f.get("number","")))
    for tc in result["tc_groups"]:
        result["tc_groups"][tc].sort(
            key=lambda x: 0 if x[1]=="Agency fee" else (1 if "crédito" in x[1] else 2)
        )

    result["consorcio"].sort()
    result["donmar"].sort()
    result["puerto_mariel"].sort()

    return result
