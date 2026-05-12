"""
classifier.py  —  ISA FDA Generator · Bahia Blanca
Detecta qué es cada PDF por contenido + nombre como fallback.
Soporta SOFs escaneados (sin texto extraíble).
"""

import os, re, zipfile
import fitz  # PyMuPDF


# ══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════════════════════

def read_text(pdf_path, max_pages=3):
    try:
        doc = fitz.open(pdf_path)
        n   = min(doc.page_count, max_pages)
        return " ".join(doc[i].get_text() for i in range(n))
    except Exception:
        return ""


def read_page(pdf_path, idx):
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
    try:
        doc  = fitz.open(pdf_path)
        page = doc[idx]
        return len(page.get_images()) > 0 and len(page.get_text().strip()) < 60
    except Exception:
        return False


def extract_zip(zip_path, dest_dir):
    """Extrae los PDFs del ZIP al directorio destino."""
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
#  CLASIFICADOR DE DOCUMENTOS
#  Estrategia: contenido primero, nombre como fallback
# ══════════════════════════════════════════════════════════════════════════════

# Detección por contenido (texto del PDF)
DOC_TYPES_CONTENT = [
    ("sof",           ["DETAILS OF DAILY WORKING"]),
    ("sof",           ["Standard Statement on Fact"]),
    ("sof",           ["Statement of Facts"]),
    ("sof",           ["Exceeding expectations", "VESSEL"]),  # SOF con logo ISA
    # Maritime MUST come before bna — some Maritime expedientes contain BNA pages
    ("maritime",      ["SUCURSAL: Bahía Blanca", "FACT CRED ELECT"]),
    ("maritime",      ["SUCURSAL: Necochea", "FACT CRED ELECT"]),
    ("bna",           ["Cotizaciones históricas", "Dolar U.S.A"]),
    ("bna",           ["Banco de la Naci", "Cotizaciones"]),
    ("bna",           ["Dolar U.S.A", "Compra", "Venta", "Fecha"]),
    ("facb_isa",      ["B00003", "INDEPENDENT SHIP AGENTS"]),

    ("facb_isa",      ["B00003", "AGENCY FEE"]),
    ("facb_isa",      ["B00003", "PORT DUES"]),
    ("consorcio",     ["Consorcio de Gestión del Puerto de Bahia Blanca"]),
    ("consorcio",     ["CONSORCIO DE GESTION DEL PUERTO DE BAHIA BLANCA"]),
    ("consorcio",     ["USO DE PUERTO ULTRAMAR"]),
    ("consorcio",     ["Uso de Vía Navegable", "IMPORTE"]),
    ("donmar",        ["DONMAR S.A."]),
    ("donmar",        ["Practicaje Ultramar", "BOYA 11"]),
    ("donmar",        ["Servicio de Practicaje", "Ingeniero White"]),
    ("puerto_mariel", ["PUERTO MARIEL"]),
    ("puerto_mariel", ["ARGENTINA TOWAGE"]),
    ("puerto_mariel", ["Towage Service", "COOPOR"]),
    ("maritime",      ["MARITIME SHIPPING AGENCY"]),
    ("maritime",      ["SUCURSAL: Bahía Blanca", "FACT CRED ELECT"]),
    ("maritime",      ["SUCURSAL: Necochea", "FACT CRED ELECT"]),
    ("maritime",      ["Maritime Shipping Agency", "FACT CRED ELECT"]),
    ("maritime",      ["Maritime Shipping Agency", "Disbursement"]),
    ("amarradores",   ["AMARRADORES DEL PUERTO DE BAHIA BLANCA"]),
    ("ammoca",        ["AMMOCA S.A."]),
    ("centro_nav",    ["Centro de Navegación Asociación Civil"]),
    ("centro_nav",    ["cnav.org.ar"]),
    ("centro_nav",    ["centrodenavegaci"]),
    ("centro_nav",    ["Centro de Navegaci", "Florida 537"]),
    # Necochea-specific providers
    ("consorcio_quequen", ["Consorcio de Gestión del Puerto Quequén"]),
    ("consorcio_quequen", ["Puerto Quequén", "Juan de Garay"]),
    ("consorcio_quequen", ["30-66634948-9"]),
    ("pilotaje",      ["MEYER", "ARANA", "Necochea"]),
    ("melluso",       ["MELLUSO S.A."]),
    ("melluso",       ["SERVICIO DE LANCHAS Y AMARRADORES PUERTO QUEQUEN"]),
    ("shore_gangway", ["SHORE GANGWAY", "30716643685"]),
    ("shore_gangway", ["SHORE GANGWAY", "CRANE SERVICE"]),
]

# Detección por nombre de archivo (fallback cuando el PDF es imagen/escaneado)
DOC_TYPES_NAME = [
    ("sof",           ["SOF", "Statement"]),
    ("bna",           ["Banco", "BNA", "Naci"]),
    ("facb_isa",      ["FACB"]),
    ("consorcio",     ["CONSORCIO", "PUERTO DE BAHIA"]),
    ("donmar",        ["DONMAR"]),
    ("puerto_mariel", ["MARIEL", "TOWAGE"]),
    ("maritime",      ["MARITIME"]),
    ("maritime",      ["MARITIM"]),
    ("amarradores",   ["AMARRADORES"]),
    ("ammoca",        ["AMMOCA"]),
    ("centro_nav",    ["NAVEGACION", "CNAV"]),
    ("consorcio_quequen", ["QUEQUEN", "QUEQU"]),
    ("pilotaje",      ["MEYER", "ARANA"]),
    ("melluso",       ["MELLUSO"]),
    ("shore_gangway", ["GANGWAY", "PASARELA"]),
]


def classify_doc(pdf_path):
    """
    Clasifica el PDF. Primero por contenido, luego por nombre si no hay texto.
    """
    fname = os.path.basename(pdf_path).upper()
    text  = read_text(pdf_path, max_pages=3)

    # ── Por contenido ─────────────────────────────────────────────────────────
    if text.strip():
        for (dtype, keywords) in DOC_TYPES_CONTENT:
            if all(kw in text for kw in keywords):
                return dtype

    # ── Por nombre (fallback para PDFs escaneados sin texto) ──────────────────
    for (dtype, keywords) in DOC_TYPES_NAME:
        if any(kw in fname for kw in keywords):
            return dtype

    return "unknown"


# ══════════════════════════════════════════════════════════════════════════════
#  CLASIFICADOR DE PÁGINAS DE MARITIME
# ══════════════════════════════════════════════════════════════════════════════

MARITIME_PAGE_RULES = [
    ("skip",              ["FACT CRED ELECT"]),
    ("skip",              ["MiPyME"]),
    ("skip",              ["Disbursement Account"]),
    ("skip",              ["DISBURSEMENT ACCOUNT"]),
    ("headclerk_break",   ["HEAD CLERK", "Breakdown"]),
    ("headclerk_liq",     ["LIQUIDACION DE PAGO A ENCARGADOS"]),
    ("watchmen_break",    ["WATCHMEN", "Breakdown"]),
    ("watchmen_liq",      ["LIQUIDACION DE PAGO", "SERENO"]),
    ("watchmen_liq",      ["Employee Sales", "Jornales / Wages", "GRAND TOTAL"]),
    ("watchmen_liq",      ["Jornales / Wages", "Movilidad / Travel"]),
    ("afip_lman",         ["LMAN", "ADMINISTRACION FEDERAL DE INGRESOS"]),
    ("se_inward",         ["SOLICITUD DE HABILITACION", "FORMALIZACION DE ENTRADA"]),
    ("se_inward",         ["SOLICITUD DE HABILITACION", "FEVA"]),

    ("se_permanencia",    ["SOLICITUD DE HABILITACION", "permanencia"]),
    ("se_permanencia",    ["SOLICITUD DE HABILITACION", "PERMANENCIA"]),
    ("se_permanencia",    ["SOLICITUD DE HABILITACION DE", "SERVICIOS EXTRAORDINARIOS", "09:"]),
    ("se_permanencia",    ["SOLICITUD DE HABILITACION DE", "SERVICIOS EXTRAORDINARIOS"]),
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
    ("senasa",            ["BOLETA DE PAGO", "Barreras Sanitarias"]),
    ("senasa",            ["BOLETA DE PAGO", "66960672"]),
    ("senasa",            ["BOLETA DE PAGO", "MARITIME SHIPPING"]),
    ("senasa",            ["BOLETA DE PAGO", "MARITIME"]),
    ("amarradores_pag",   ["AMARRADORES"]),
    ("meyer_arana",       ["MEYER", "ARANA", "Necochea"]),
    ("meyer_arana",       ["MEYER  ARANA", "Período Facturado"]),
    ("meyer_arana",       ["LABARTHE", "PRACTICAJE", "QUEQUEN"]),
    ("meyer_arana",       ["LABARTHE", "Período Facturado"]),
    ("melluso",           ["MELLUSO S.A."]),
    ("melluso",           ["MELLUSO", "PUERTO QUEQUEN"]),
    ("melluso",           ["MARITIMA QUEUQUEN"]),
    ("melluso",           ["MARITIMA QUEQUEN"]),
    ("shore_gangway_pag", ["SHORE GANGWAY", "30716643685"]),
    ("shore_gangway_pag", ["SHORE GANGWAY", "CRANE SERVICE"]),
    ("osro",              ["OSRO", "BARRERAS FLOTANTES"]),
    ("osro",              ["COMPULSORY BARRIER"]),
    ("pest_pag",          ["AMMOCA"]),
]

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
    "mooring_img":       None,   # imágenes de scan → omitir
    "meyer_arana":       "PORT PILOTAGE",
    "melluso_pag":       "MOORING & UNMOORING SERVICES",
    "melluso":           "MOORING & UNMOORING SERVICES",
    "shore_gangway_pag": "SHORE GANGWAY",
    "osro":              "OSRO ANNEX 18",
    "pest_pag":          "PEST CONTROL",
    "skip":              None,
    "skip_dup":          None,
    "disbursement":      None,
    "unknown":           None,
}


def classify_maritime_pages(pdf_path):
    n      = page_count(pdf_path)
    result = []
    seen_lman = set()

    for i in range(n):
        text = read_page(pdf_path, i)

        if is_image_page(pdf_path, i):
            result.append({"page": i, "category": "mooring_img",
                           "voucher": "MOORING & UNMOORING SERVICES"})
            continue

        cat = "unknown"
        for (category, keywords) in MARITIME_PAGE_RULES:
            if all(kw in text for kw in keywords):
                cat = category
                break

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
    text = read_text(pdf_path, max_pages=2)
    d    = {}

    m = re.search(r"B0+3-0*(\d+)", text)
    if m:
        d["number"] = m.group(1)

    m = re.search(r"ARS/USD\s*=\s*([\d,.]+)", text)
    if m:
        d["tc"] = float(m.group(1).replace(",", ""))

    # Total: buscar patrón TOTAL USD o SubTotal USD
    m = re.search(r"(?:TOTAL|SubTotal)\s+USD\s+([\d,]+\.?\d*)", text)
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

    # Buque desde "M/V NOMBRE  DD-MM-YYYY"
    m = re.search(r"M/V\s+([A-Z][A-Z0-9\s\-]+?)\s+\d{2}[-/]\d{2}[-/]", text)
    if m:
        d["vessel"] = "M/V " + m.group(1).strip()

    # Puerto desde FACB (línea "NECOCHEA PORT" o "BAHIA BLANCA PORT")
    if "NECOCHEA PORT" in text.upper():
        d["port"] = "Necochea Port"
    elif "BAHIA BLANCA PORT" in text.upper():
        d["port"] = "Bahia Blanca Port"

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
    """Extrae vessel, sailed, port. Funciona con texto y con PDFs escaneados."""
    text = read_text(pdf_path, max_pages=3)
    d    = {}

    # Vessel
    m = re.search(r'm\.v\.\s*["\']?([A-Z][A-Z0-9\s"\']+?)["\']?\s*[\r\n]', text)
    if m:
        d["vessel"] = "M/V " + m.group(1).strip().strip("\"'")

    # Sailed
    m = re.search(r'Sailed?\s*[\r\n\s:]+(\d{1,2})/(\d{2})/(\d{4})', text)
    if m:
        day, mon, yr = m.group(1), m.group(2), m.group(3)
        d["sailed"] = f"{MONTH_MAP.get(mon, mon)} {int(day)}, {yr}"

    if "Bahia Blanca" in text or "BAHIA BLANCA" in text:
        d["port"] = "Bahia Blanca Port"
    elif "Necochea" in text or "NECOCHEA" in text or "Quequén" in text or "QUEQUEN" in text:
        d["port"] = "Necochea Port"

    return d


# ══════════════════════════════════════════════════════════════════════════════
#  ANÁLISIS COMPLETO DEL DIRECTORIO
# ══════════════════════════════════════════════════════════════════════════════

def analyze(work_dir):
    pdfs = sorted(f for f in os.listdir(work_dir) if f.lower().endswith(".pdf"))

    result = {
        "sof": None, "bna": None,
        "facbs": [], "consorcio": [], "donmar": [],
        "puerto_mariel": [], "maritime": [],
        "amarradores": [], "ammoca": [], "centro_nav": [],
        # Necochea-specific
        "consorcio_quequen": [], "pilotaje": [], "melluso": [], "shore_gangway": [],
        "unknown": [],
        "vessel": None, "client": None, "sailed": None, "port": None,
        "tc_groups": {},
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
            result["port"]   = result["port"]   or d.get("port")
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
        elif dtype == "centro_nav":
            result["centro_nav"].append(fname)
        # Necochea-specific
        elif dtype == "consorcio_quequen":
            result["consorcio_quequen"].append(fname)
            # Also add to "consorcio" for unified port detection
            result["consorcio"].append(fname)
        elif dtype == "pilotaje":
            result["pilotaje"].append(fname)
        elif dtype == "melluso":
            result["melluso"].append(fname)
        elif dtype == "shore_gangway":
            result["shore_gangway"].append(fname)
        else:
            result["unknown"].append(fname)

    # Ordenar: agency primero
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







