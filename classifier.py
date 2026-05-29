"""
classifier.py  —  ISA FDA Generator · San Lorenzo / Bahia Blanca / Necochea
Detecta qué es cada PDF por contenido + nombre como fallback.
Soporta SOFs escaneados (sin texto extraíble).

FIXES aplicados:
  - orden_transporte SENASA (viaje a SE.NA.SA) → clasificado como parte de GARBAGE,
    no de MIGRATION. Nuevo tipo "orden_transporte_senasa" → GARBAGE COMPULSORY INSPECTION.
  - Páginas de Libre Plática (sanidad_cert): reglas mejoradas para capturar
    "Certificado de Libre Plática Cablegráfica" y variantes.
  - Mandatory Holds: comprobante interno ahora incluye facturas de servicio de inspección
    (Fides Control / LCI Report / agentes de inspección).
  - Páginas de Maritime: la carátula (FACT CRED ELECT) y el Disbursement Account
    siempre se saltean (skip).
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
# ══════════════════════════════════════════════════════════════════════════════

DOC_TYPES_CONTENT = [
    ("sof",           ["DETAILS OF DAILY WORKING"]),
    ("sof",           ["Standard Statement on Fact"]),
    ("sof",           ["Statement of Facts"]),
    ("sof",           ["Exceeding expectations", "VESSEL"]),
    # Maritime MUST come before bna
    ("maritime",      ["SUCURSAL: Bahía Blanca", "FACT CRED ELECT"]),
    ("maritime",      ["SUCURSAL: Necochea", "FACT CRED ELECT"]),
    ("maritime",      ["San Lorenzo", "FACT CRED ELECT MiPyME"]),
    ("maritime",      ["Maritime Shipping Agency", "San Lorenzo", "FACT CRED ELECT"]),
    ("bna",           ["Cotizaciones históricas", "Dolar U.S.A"]),
    ("bna",           ["Banco de la Naci", "Cotizaciones"]),
    ("bna",           ["Dolar U.S.A", "Compra", "Venta", "Fecha"]),
    ("facb_isa",      ["B00003", "INDEPENDENT SHIP AGENTS"]),
    ("facb_isa",      ["B00003", "AGENCY FEE"]),
    ("facb_isa",      ["B00003", "NOTA DE CREDITO"]),
    ("facb_isa",      ["B00003", "CREDIT NOTE"]),
    ("facb_isa",      ["B00003", "PORT DUES"]),
    ("facb_isa",      ["A00003", "Cod.001"]),
    ("facb_isa",      ["A00003", "SAN LORENZO PORT"]),
    ("facb_isa",      ["A00003", "BAHIA BLANCA PORT"]),
    ("facb_isa",      ["A00003", "NECOCHEA PORT"]),
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
    # Necochea
    ("consorcio_quequen", ["Consorcio de Gestión del Puerto Quequén"]),
    ("consorcio_quequen", ["Puerto Quequén", "Juan de Garay"]),
    ("consorcio_quequen", ["30-66634948-9"]),
    ("pilotaje",      ["MEYER", "ARANA", "Necochea"]),
    ("melluso",       ["MELLUSO S.A."]),
    ("melluso",       ["SERVICIO DE LANCHAS Y AMARRADORES PUERTO QUEQUEN"]),
    ("shore_gangway", ["SHORE GANGWAY", "30716643685"]),
    ("shore_gangway", ["SHORE GANGWAY", "CRANE SERVICE"]),
    # San Lorenzo
    # Terminal portuario (Port Dues) — todos los proveedores del Excel
    ("terminal_portuario", ["TERMINAL 6 S.A."]),
    ("terminal_portuario", ["COFCO INTERNATIONAL ARGENTINA"]),
    ("terminal_portuario", ["COFCO ARGENTINA"]),
    ("terminal_portuario", ["MOLINOS AGRO S.A."]),
    ("terminal_portuario", ["MOLINOS RIO DE LA PLATA"]),
    ("terminal_portuario", ["CARGILL S.A.C. I."]),
    ("terminal_portuario", ["CARGILL S.A.C.I."]),
    ("terminal_portuario", ["BUNGE ARGENTINA"]),
    ("terminal_portuario", ["VICENTIN S.A.I.C."]),
    ("terminal_portuario", ["LDC ARGENTINA"]),
    ("terminal_portuario", ["ASOC. DE COOP. ARGENTINAS"]),
    ("terminal_portuario", ["ADM AGRO SRL"]),
    ("terminal_portuario", ["TERMINAL PUERTO ROSARIO"]),
    ("terminal_portuario", ["TERMINAL DE FERTILIZANTES ARGENTINOS"]),
    ("terminal_portuario", ["RENOVA S.A."]),
    ("terminal_portuario", ["ACEITERA GENERAL DEHEZA"]),
    ("terminal_portuario", ["PROFERTIL S.A."]),
    ("terminal_portuario", ["CARBOCLOR S.A."]),
    ("terminal_portuario", ["ARAUCO ARGENTINA"]),
    ("terminal_portuario", ["POBATER S.A."]),
    ("terminal_portuario", ["CONSORCIO DE GESTION DEL PUERTO SAN PEDRO"]),
    ("terminal_portuario", ["DEL GUAZU S.A."]),
    ("terminal_portuario", ["ENTE ADMINISTRADOR VILLA CONSTITUCION"]),
    ("terminal_portuario", ["SERVICIOS PORTUARIOS SA"]),
    ("terminal_portuario", ["MINERA ALUMBRERA LIMITED"]),
    ("terminal_portuario", ["MOLINO CAÑUELAS"]),
    # Practicaje Río de la Plata (River Plate Pilotage)
    ("practicaje_rp",      ["Practicaje", "Río de la Plata", "ripla.com.ar"]),
    ("practicaje_rp",      ["PRACTICAJE RIO DE LA PLATA CT"]),
    ("practicaje_rp",      ["33-70776769-9"]),
    ("practicaje_rp",      ["SIPSA PILOTS"]),
    ("practicaje_rp",      ["PRACTICAJE INDEPENDIENTE S.A."]),
    ("practicaje_rp",      ["COOPERATIVA DE TRABAJO COMANDANTE AZOPARDO"]),
    ("practicaje_rp",      ["TAGUA PILOT S.A"]),
    # Practicaje Río Paraná (River Parana Pilotage) — COPRAC y otros
    ("coprac",             ["C.O.P.R.A.C."]),
    ("coprac",             ["COPRAC"]),
    ("coprac",             ["30-64926021-0"]),
    ("coprac",             ["MULTIPAR S.A."]),
    ("coprac",             ["PRACTICAJE INTEGRAL S.A."]),
    ("coprac",             ["RIVER PILOT S.A"]),
    ("coprac",             ["COOPERATIVA DE TRABAJO CPI PILOTS"]),
    ("coprac",             ["PILOTAGE SA"]),
    ("coprac",             ["PRACTICOS DE PUERTO S A"]),
    ("coprac",             ["TAGUA PILOT S.A"]),
    # Port Pilotage — Rosario Pilots y otros prácticos de puerto
    ("rosario_pilots",     ["ROSARIO PILOTS COOP DE TRAB"]),
    ("rosario_pilots",     ["rosariopilots.com"]),
    ("rosario_pilots",     ["30-64794073-7"]),
    ("rosario_pilots",     ["COOP DE TRABAJO PRACTICOS DEL PARANA"]),
    ("rosario_pilots",     ["COOP TRAB PRAC D PTO LA PLATA"]),
    ("rosario_pilots",     ["CORPI COOP TRAB PRACT P PARANA"]),
    ("rosario_pilots",     ["PRACTICAJE DEL LITORAL S.R.L."]),
    ("rosario_pilots",     ["LITORAL HARBOURS PILOTS"]),
    ("rosario_pilots",     ["RIO PARANA PILOTS S"]),
    ("rosario_pilots",     ["UP RIVER PILOTS SRL"]),
    ("rosario_pilots",     ["TRANSPILOT SA"]),
    ("rosario_pilots",     ["PILOTOS DE PUERTO S.R.L."]),
    ("rosario_pilots",     ["DONMAR S.A."]),
    # Launch Services / Mooring — Amarre Coral y otros proveedores de amarre
    ("amarre_coral",       ["AMARRE CORAL S.A."]),
    ("amarre_coral",       ["30711479879"]),
    ("amarre_coral",       ["GENTE DE RIO SERVICIOS FLUVIALES"]),
    ("amarre_coral",       ["PLATE AMARRES S. A."]),
    ("amarre_coral",       ["PLUS ULTRA AMARRES"]),
    ("amarre_coral",       ["AMARRES Y LOGISTICA SRL"]),
    ("amarre_coral",       ["NORMAN HNOS S.A."]),
    ("amarre_coral",       ["LANCHAS DEL ESTE S.A."]),
    ("amarre_coral",       ["NAUTICA DEL SUR SA"]),
    ("amarre_coral",       ["DELTA BLUE LANCHAS SRL"]),
    ("amarre_coral",       ["PROBYP S.A."]),
    ("amarre_coral",       ["CLEAN SEA SA"]),
    ("amarre_coral",       ["MARITIMA MARSA S.R.L."]),
    # Glatil SA — Pilot Launch Transportation River Plate (solo USD 4,440)
    ("glatil",             ["GLATIL SA"]),
    ("glatil",             ["GLATIL"]),
    ("glatil",             ["213452850015"]),
    # Toll Dues CARP
    ("carp",               ["Comisión Administradora del Río de la Plata"]),
    ("carp",               ["COMISION ADM DEL RIO DE LP"]),
    ("carp",               ["peaje@comisionriodelaplata.org"]),
    # Toll Dues AGP
    ("agp",                ["ADMINISTRACION GENERAL DE PUERTOS S. A. U."]),
    ("agp",                ["ADMINISTRACION GENERAL DE PUERTOS"]),
    ("agp",                ["30-54670628-8"]),
    # Hidrovia / RIOVIA (también van bajo Toll Dues)
    ("agp",                ["HIDROVIA S.A."]),
    ("agp",                ["RIOVIA S.A."]),
    # Full On Hire / BQS Survey — EDI Separovic y otros surveyors
    ("edi_separovic",      ["SEPAROVIC EDI"]),
    ("edi_separovic",      ["EDI SEPAROVIC"]),
    ("edi_separovic",      ["20937939907"]),
    ("edi_separovic",      ["AUSTRAL MARINE SERVICES SRL"]),
    ("edi_separovic",      ["COOPER BROTHERS SRL"]),
    ("edi_separovic",      ["MASTER MARINER SURVEYOR"]),
    ("edi_separovic",      ["SAB MARINE SURVEYS"]),
    ("edi_separovic",      ["SURVEYS NICKMANN Y ASOCIADOS"]),
    ("edi_separovic",      ["UP RIVER MARINE S. R. L."]),
    ("edi_separovic",      ["RUIZ DIAZ PABLO MARTIN"]),
]

DOC_TYPES_NAME = [
    ("sof",           ["SOF", "Statement"]),
    ("bna",           ["Banco", "BNA", "Naci"]),
    ("facb_isa",      ["FACB"]),
    ("facb_isa",      ["FACA"]),
    ("facb_isa",      ["N_CB"]),
    ("facb_isa",      ["NCB"]),
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
    ("terminal_portuario",  ["TERMINAL 6", "COFCO", "MOLINOS", "CARGILL"]),
    ("terminal_portuario",  ["BUNGE", "VICENTIN", "LDC ARGENTINA", "RENOVA"]),
    ("terminal_portuario",  ["PROFERTIL", "CARBOCLOR", "TERMINAL PUERTO ROSARIO"]),
    ("terminal_portuario",  ["ACEITERA GENERAL DEHEZA", "TERMINAL DE FERTILIZANTES"]),
    ("practicaje_rp",       ["PRACTICAJE RIO", "RIPLA", "120002"]),
    ("practicaje_rp",       ["SIPSA PILOTS", "PRACTICAJE INDEPENDIENTE"]),
    ("practicaje_rp",       ["TAGUA PILOT"]),
    ("coprac",              ["COPRAC", "120083"]),
    ("coprac",              ["MULTIPAR", "RIVER PILOT", "PRACTICAJE INTEGRAL"]),
    ("coprac",              ["CPI PILOTS", "PILOTAGE SA"]),
    ("rosario_pilots",      ["ROSARIO PILOTS", "120033"]),
    ("rosario_pilots",      ["PRACTICAJE DEL LITORAL", "LITORAL HARBOURS"]),
    ("rosario_pilots",      ["UP RIVER PILOTS", "RIO PARANA PILOTS"]),
    ("rosario_pilots",      ["COOP DE TRABAJO PRACTICOS DEL PARANA"]),
    ("rosario_pilots",      ["PILOTOS DE PUERTO"]),
    ("amarre_coral",        ["AMARRE CORAL", "401604"]),
    ("amarre_coral",        ["GENTE DE RIO", "PLATE AMARRES", "PLUS ULTRA AMARRES"]),
    ("amarre_coral",        ["AMARRES Y LOGISTICA", "NORMAN HNOS", "NAUTICA DEL SUR"]),
    ("amarre_coral",        ["LANCHAS DEL ESTE", "DELTA BLUE LANCHAS"]),
    ("amarre_coral",        ["MARITIMA MARSA", "PROBYP", "CLEAN SEA"]),
    ("glatil",              ["GLATIL", "300361"]),
    ("carp",                ["CARP", "400477"]),
    ("agp",                 ["ADMINISTRACION GENERAL DE PUERTOS", "401262"]),
    ("edi_separovic",       ["SEPAROVIC", "EDI", "300391"]),
    ("edi_separovic",       ["AUSTRAL MARINE SERVICES", "COOPER BROTHERS"]),
    ("edi_separovic",       ["MASTER MARINER SURVEYOR", "SAB MARINE SURVEYS"]),
    ("edi_separovic",       ["UP RIVER MARINE", "SURVEYS NICKMANN"]),
]


def detect_pilotaje_flags(pdf_path):
    """
    Detecta si una factura de pilotaje tiene DEMORA y/o línea MANIOBRA con monto.
    Retorna (has_demora, has_maniobra, maniobra_amount)
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for pg in doc:
            text += pg.get_text()
    except Exception:
        return False, False, 0.0

    text_up = text.upper()
    has_demora = "DEMORA" in text_up or "DELAY" in text_up

    has_maniobra = False
    maniobra_amount = 0.0
    lines = text.split("\n")
    for i, line in enumerate(lines):
        lu = line.upper()
        if "MANIOBRA" in lu:
            # Formato 1a: "1 MANIOBRAS EN ZC USD 2,520.00" (USD en la misma línea)
            m = re.search(r"USD\s*([\d,\.]+)", line)
            if m:
                has_maniobra = True
                maniobra_amount += float(m.group(1).replace(",", ""))
                continue

            # Formato 1b: Ripla — "1 MANIOBRAS EN ZC" y el monto en la línea siguiente
            # como "USD 2.520,00" (punto como miles, coma como decimal)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                m_next = re.match(r"^USD\s*([\d\.]+,\d{2})$", next_line)
                if m_next:
                    try:
                        raw = m_next.group(1).replace(".", "").replace(",", ".")
                        val = float(raw)
                        if val > 0:
                            has_maniobra = True
                            maniobra_amount += val
                            continue
                    except ValueError:
                        pass
                # También formato "USD 2,520.00" (coma miles, punto decimal)
                m_next2 = re.match(r"^USD\s*([\d,]+\.\d{2})$", next_line)
                if m_next2:
                    try:
                        val = float(m_next2.group(1).replace(",", ""))
                        if val > 0:
                            has_maniobra = True
                            maniobra_amount += val
                            continue
                    except ValueError:
                        pass

            # Formato 2 COPRAC: "||1 MANIOBRAS DE FONDEO" y monto "2.520,00||" en siguiente línea
            for j in range(i + 1, min(i + 4, len(lines))):
                # Limpiar pipes y espacios
                clean = lines[j].replace("|", "").strip()
                if not clean:
                    continue
                # Formato COPRAC: "2.520,00" (punto=miles, coma=decimal)
                m3 = re.match(r"^([\d]+\.[\d]{3},[\d]{2})$", clean)
                if m3:
                    try:
                        raw = m3.group(1).replace(".", "").replace(",", ".")
                        val = float(raw)
                        if val > 100:
                            has_maniobra = True
                            maniobra_amount += val
                    except ValueError:
                        pass
                    break
                # Formato alternativo: número simple "2520.00" o "2,520.00"
                m4 = re.match(r"^([\d,]+\.[\d]{2})$", clean)
                if m4:
                    try:
                        val = float(m4.group(1).replace(",", ""))
                        if val > 100:
                            has_maniobra = True
                            maniobra_amount += val
                    except ValueError:
                        pass
                    break
    return has_demora, has_maniobra, maniobra_amount


def classify_doc(pdf_path):
    """
    Clasifica el PDF. Primero por contenido, luego por nombre si no hay texto.
    """
    fname = os.path.basename(pdf_path).upper()
    text  = read_text(pdf_path, max_pages=3)

    if text.strip():
        for (dtype, keywords) in DOC_TYPES_CONTENT:
            if all(kw in text for kw in keywords):
                return dtype

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
    # BNA interno dentro de Maritime → skip (usar BNA externo)
    ("skip",              ["Cotizaciones históricas", "Dolar U.S.A"]),
    ("skip",              ["Banco de la Naci", "Cotizaciones"]),
    ("headclerk_break",   ["HEAD CLERK", "Breakdown"]),
    ("headclerk_liq",     ["LIQUIDACION DE PAGO A ENCARGADOS"]),
    ("watchmen_break",    ["WATCHMEN", "Breakdown"]),
    ("watchmen_liq",      ["LIQUIDACION DE PAGO", "SERENO"]),
    ("watchmen_liq",      ["Employee Sales", "Jornales / Wages", "GRAND TOTAL"]),
    ("watchmen_liq",      ["Jornales / Wages", "Movilidad / Travel"]),
    ("afip_lman",         ["LMAN", "ADMINISTRACION FEDERAL DE INGRESOS"]),
    ("afip_lman",         ["LMAN", "DATOS AFIP"]),
    ("se_inward",         ["SOLICITUD DE HABILITACION", "FORMALIZACION DE ENTRADA"]),
    ("se_inward",         ["SOLICITUD DE HABILITACION", "FEVA"]),
    ("se_permanencia",    ["SOLICITUD DE HABILITACION", "permanencia"]),
    ("se_permanencia",    ["SOLICITUD DE HABILITACION", "PERMANENCIA"]),
    ("se_permanencia",    ["SOLICITUD DE HABILITACION DE", "SERVICIOS EXTRAORDINARIOS", "09:"]),
    ("se_rancho",         ["SOLICITUD DE HABILITACION", "RANCHO"]),
    ("se_rancho",         ["SOLICITUD DE HABILITACION", "VLSFO"]),
    # se_cargo: exportacion zona primaria / carga
    ("se_cargo",          ["SOLICITUD DE HABILITACION", "ZONA PRIMARIA"]),
    ("se_cargo",          ["SOLICITUD DE HABILITACION", "ECZP"]),
    ("se_cargo",          ["SOLICITUD DE HABILITACION", "HARINA"]),
    ("se_cargo",          ["SOLICITUD DE HABILITACION", "CARGO"]),
    ("se_cargo",          ["SOLICITUD DE HABILITACION", "carga"]),
    # SSEE generico fallback -> Custom House Expenses
    ("se_inward",         ["SOLICITUD DE HABILITACION DE", "SERVICIOS EXTRAORDINARIOS"]),
    ("migraciones_liq",   ["Migraciones", "quincena"]),
    ("migraciones_liq",   ["Migraciones", "Liquidaci"]),
    ("migraciones_sol",   ["Servicios Marítimos y Fluviales", "Solicitud de Servicio"]),
    # FIX #6/#8: Orden de transporte — distinguir Migration vs SENASA
    # Si el detalle del viaje menciona SE.NA.SA → Garbage; si menciona MIGRATION → Migration
    ("orden_transporte_senasa", ["ORDEN DE TRANSPORTE", "SE.NA.SA"]),
    ("orden_transporte_senasa", ["ORDEN DE TRANSPORTE", "SENASA OFFICE"]),
    ("orden_transporte",  ["ORDEN DE TRANSPORTE"]),
    # FIX #7: Libre Plática — todas las variantes
    ("sanidad_cert",      ["Certificado de Libre Plática Cablegráfica"]),
    ("sanidad_cert",      ["CERTIFICADO DE LIBRE PLÁTICA CABLEGRÁFICA"]),
    ("sanidad_cert",      ["Libre Plática"]),
    ("sanidad_cert",      ["Certificado de Libre"]),
    ("sanidad_eval",      ["EVALUACIÓN DE RIESGOS"]),          # página 2 del certificado
    ("sanidad_eval",      ["Evaluación de Libre Plática"]),
    ("sanidad_transf",    ["MINISTERIO DE SALUD", "COMPULSORY SANITARY"]),
    ("sanidad_transf",    ["MINISTERIO DE SALUD"]),
    ("sanidad_recibo",    ["FREE PRACTIQUE", "Recib"]),
    ("nav_center",        ["Centro de Navegación", "cnav.org.ar"]),
    ("nav_center",        ["centrodenavegaci", "FACTURA"]),
    ("senasa",            ["SENASA", "BOLETA DE PAGO"]),
    ("senasa",            ["DNO004"]),
    ("senasa",            ["BOLETA DE PAGO", "Barreras Sanitarias"]),
    ("senasa",            ["BOLETA DE PAGO", "66960672"]),
    ("senasa",            ["BOLETA DE PAGO", "MARITIME SHIPPING"]),
    ("senasa",            ["BOLETA DE PAGO", "MARITIME"]),
    ("senasa",            ["Barreras Sanitarias", "BOLETA"]),
    ("senasa",            ["Barreras Sanitarias", "ARANCEL"]),
    # FIX #9: Compulsory Inspection — incluye el comprobante interno Y facturas de inspección
    ("compulsory_insp",   ["COMPULSORY INSPECTION BY PRIVATE SURVEYORS"]),
    ("compulsory_insp",   ["COMPULSORY INSPECTION", "PRIVATE SURVEYORS"]),
    # Facturas de servicio de inspección (Fides Control, etc.)
    ("compulsory_insp",   ["LCI REPORT"]),
    ("compulsory_insp",   ["Fides Control", "INSPECTION"]),
    # Factura electrónica del servicio de inspección (+)))))): texto característico
    ("compulsory_insp",   ["FACTURA SERV.ELECTR"]),
    ("compulsory_insp",   ["FACTURA SERV", "INSPEC"]),
    ("compulsory_reinsp", ["RE-INSPECTION", "PRIVATE SURVEYORS"]),
    ("compulsory_reinsp", ["REINSPECTION", "PRIVATE SURVEYORS"]),
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
    ("enapro",            ["Ente Administrador Puerto Rosario"]),
    ("enapro",            ["enapro.com.ar"]),
    ("enapro",            ["ENAPRO"]),
]

PAGE_TO_VOUCHER = {
    "headclerk_break":        "HEADCLERK COMPULSORY SERVICES",
    "headclerk_liq":          "HEADCLERK COMPULSORY SERVICES",
    "watchmen_break":         "WATCHMEN COMPULSORY SERVICES",
    "watchmen_liq":           "WATCHMEN COMPULSORY SERVICES",
    "afip_lman":              "CUSTOM HOUSE EXPENSES",
    "se_inward":              "CUSTOM HOUSE EXPENSES",
    "se_permanencia":         "CUSTOM HOUSE PERMANENCE",
    "se_rancho":              "CUSTOM HOUSE (BUNKERING)",
    "se_cargo":               "CUSTOM HOUSE EXPENSE (CARGO)",
    "migraciones_liq":        "MIGRATION EXPENSES",
    "migraciones_sol":        "MIGRATION EXPENSES",
    "orden_transporte":       "MIGRATION EXPENSES",
    # FIX #6/#8: orden de transporte SENASA → Garbage
    "orden_transporte_senasa": "GARBAGE COMPULSORY INSPECTION",
    "sanidad_cert":           "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_eval":           "SANITARY DUES AND FREE PRATIQUE",   # FIX #7
    "sanidad_transf":         "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_recibo":         "SANITARY DUES AND FREE PRATIQUE",
    "senasa":                 "GARBAGE COMPULSORY INSPECTION",
    "amarradores_pag":        "MOORING & UNMOORING SERVICES",
    "nav_center":             "NAVIGATION CENTER CONTRIBUTION",
    "mooring_img":            None,
    "meyer_arana":            "PORT PILOTAGE",
    "melluso_pag":            "MOORING & UNMOORING SERVICES",
    "melluso":                "MOORING & UNMOORING SERVICES",
    "shore_gangway_pag":      "SHORE GANGWAY",
    "osro":                   "OSRO ANNEX 18",
    "pest_pag":               "PEST CONTROL",
    "enapro":                 "ENTRANCE AND LIGHT DUES",
    "compulsory_insp":        "MANDATORY HOLDS INSPECTION",    # FIX #9
    "compulsory_reinsp":      "MANDATORY HOLDS RE-INSPECTION",
    "skip":                   None,
    "skip_dup":               None,
    "disbursement":           None,
    "unknown":                None,
}


def _classify_image_page_by_context(previous_pages, pdf_path, idx):
    """
    Clasifica una página imagen basándose en el contexto de páginas previas.
    Si las páginas anteriores son migraciones o sanidad → probablemente Libre Plática.
    Si las páginas anteriores son mooring → mooring_img.
    """
    if not previous_pages:
        return "mooring_img"
    
    # Revisar las últimas páginas clasificadas
    recent_vouchers = [p.get("voucher") for p in previous_pages[-5:] if p.get("voucher")]
    recent_cats     = [p.get("category") for p in previous_pages[-5:]]
    
    # Si la página anterior fue compulsory_insp → esta imagen también es parte de inspección
    if recent_cats and recent_cats[-1] in ["compulsory_insp"]:
        return "compulsory_insp"  # → MANDATORY HOLDS INSPECTION
    
    # Si las páginas anteriores son migration o sanidad → esta es Libre Plática (sanidad_cert)
    sanidad_context = any(v in ["MIGRATION EXPENSES", "SANITARY DUES AND FREE PRATIQUE"]
                          for v in recent_vouchers)
    # Si hay páginas de mooring cercanas y NO hay contexto sanidad → mooring
    if sanidad_context:
        return "sanidad_cert"  # → SANITARY DUES AND FREE PRATIQUE
    
    # Si la página anterior fue mooring o también imagen sin contexto especial → mooring
    if recent_cats and recent_cats[-1] in ["mooring_img", "amarradores_pag"]:
        return "mooring_img"
    
    # Si el texto de páginas cercanas sugiere sanidad
    try:
        doc = fitz.open(pdf_path)
        # Verificar páginas siguientes para ver si hay sanidad_transf
        for j in range(idx + 1, min(idx + 3, doc.page_count)):
            next_text = doc[j].get_text()
            if "MINISTERIO DE SALUD" in next_text or "FREE PRACTIQUE" in next_text:
                return "sanidad_cert"
    except Exception:
        pass
    
    return "mooring_img"


def classify_maritime_pages(pdf_path):
    n      = page_count(pdf_path)
    result = []
    seen_lman = set()

    for i in range(n):
        text = read_page(pdf_path, i)

        if is_image_page(pdf_path, i):
            # Detectar si la imagen es parte de Sanitary (Libre Plática) o Mandatory Holds
            # basándose en las páginas que la rodean
            category = _classify_image_page_by_context(result, pdf_path, i)
            voucher = PAGE_TO_VOUCHER.get(category, "MOORING & UNMOORING SERVICES")
            result.append({"page": i, "category": category, "voucher": voucher})
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

    m = re.search(r"[AB]0+3-0*(\d+)", text)
    if m:
        d["number"] = m.group(1)

    m = re.search(r"ARS/USD\s*=?\s*([\d,.]+)", text)
    if m:
        d["tc"] = float(m.group(1).replace(",", ""))

    if "A00003" in text:
        nums = [l.strip() for l in text.split("\n") if re.match(r"^[\d,]+\.\d{2}$", l.strip())]
        if nums:
            d["total"] = float(nums[-1].replace(",", ""))
    else:
        m = re.search(r"(?:TOTAL|SubTotal)\s+USD\s+([\d,]+\.?\d*)", text)
        if m:
            d["total"] = float(m.group(1).replace(",", ""))

    if "AGENCY FEE" in text.upper():
        d["type"]  = "agency"
        d["label"] = "Agency fee"
    elif ("NCB" in text or
          "NOTA DE CREDITO" in text.upper() or
          "NOTA DE CRÉDITO" in text.upper() or
          "CREDIT NOTE" in text.upper() or
          "Cod.008" in text):
        # FIX B4: detectar NCB con y sin tilde, y por código de comprobante
        d["type"]  = "ncb"
        d["label"] = "Nota de crédito"
    else:
        d["type"]  = "port_expenses"
        d["label"] = "Port expenses"

    m = re.search(r"SEÑORES(?:/CUSTOMER)?\s*:?\s*(.+?)(?:DOMICILIO|CUIT|\n|$)", text)
    if m:
        d["client"] = m.group(1).strip()

    m = re.search(r"M/V\s+([A-Z][A-Z0-9\s\-]+?)\s+\d{2}[-/]\d{2}[-/]", text)
    if m:
        d["vessel"] = "M/V " + m.group(1).strip()

    if "Santander" in text:
        d["bank_name"] = "Santander Argentina"
        m_acct = re.search(r"Account Number:\s*\$?([\d\-/]+)", text)
        m_cbu  = re.search(r"CBU:\s*([\d]+)", text)
        m_bene = re.search(r"Beneficiary: ([^\n]+)", text)
        m_cuit = re.search(r"CUIT:\s*([\d\-]+)", text)
        if m_acct: d["bank_account"]     = m_acct.group(1).strip()
        if m_cbu:  d["bank_cbu"]         = m_cbu.group(1).strip()
        if m_bene: d["bank_beneficiary"] = m_bene.group(1).strip()
        if m_cuit: d["bank_cuit"]        = m_cuit.group(1).strip()
    elif "Citibank" in text:
        d["bank_name"]        = "Citibank N.A., New York Branch"
        d["bank_aba"]         = "21000089"
        d["bank_swift"]       = "CITIUS33"
        d["bank_account"]     = "36404074"
        d["bank_beneficiary"] = "INDEPENDENT SHIP AGENTS S.A."

    if "NECOCHEA PORT" in text.upper():
        d["port"] = "Necochea Port"
    elif "BAHIA BLANCA PORT" in text.upper():
        d["port"] = "Bahia Blanca Port"
    elif "SAN LORENZO PORT" in text.upper():
        d["port"] = "San Lorenzo Port"
    elif "ARROYO SECO PORT" in text.upper():
        d["port"] = "San Lorenzo Port"
    elif "GRAL. LAGOS PORT" in text.upper() or "GENERAL LAGOS PORT" in text.upper():
        d["port"] = "San Lorenzo Port"

    return d


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACCIÓN DE DATOS DEL SOF
# ══════════════════════════════════════════════════════════════════════════════

MONTH_MAP = {
    "01": "January", "02": "February", "03": "March",    "04": "April",
    "05": "May",     "06": "June",     "07": "July",     "08": "August",
    "09": "September","10": "October", "11": "November", "12": "December",
}


def extract_sof(pdf_path):
    """Extrae vessel, sailed, port. Funciona con texto y con PDFs escaneados."""
    text = read_text(pdf_path, max_pages=3)
    d    = {}

    m = re.search(r'm\.v\.\s*["\']?([A-Z][A-Z0-9\s"\']+ ?)["\']?\s*[\r\n]', text)
    if m:
        d["vessel"] = "M/V " + m.group(1).strip().strip("\"'")

    m = re.search(r'Sailed?\s*[\r\n\s:]+(\d{1,2})/(\d{2})/(\d{4})', text)
    if m:
        day, mon, yr = m.group(1), m.group(2), m.group(3)
        d["sailed"] = f"{MONTH_MAP.get(mon, mon)} {int(day)}, {yr}"

    if "Bahia Blanca" in text or "BAHIA BLANCA" in text:
        d["port"] = "Bahia Blanca Port"
    elif "Necochea" in text or "NECOCHEA" in text or "Quequén" in text or "QUEQUEN" in text:
        d["port"] = "Necochea Port"
    elif "San Lorenzo" in text or "SAN LORENZO" in text:
        d["port"] = "San Lorenzo Port"
    elif "Arroyo Seco" in text or "ARROYO SECO" in text:
        d["port"] = "San Lorenzo Port"

    return d


# ══════════════════════════════════════════════════════════════════════════════
#  ANÁLISIS COMPLETO DEL DIRECTORIO
# ══════════════════════════════════════════════════════════════════════════════

def _extract_sailed_from_maritime(pdf_path):
    """Extrae la fecha de salida del Disbursement Account interno de Maritime."""
    try:
        doc = fitz.open(pdf_path)
        for i in range(min(3, doc.page_count)):
            text = doc[i].get_text()
            if "SAILED" in text.upper() and "DISBURSEMENT" in text.upper():
                m = re.search(r"SAILED[\s\r\n]+(\d{1,2})/(\d{2})/(\d{4})", text)
                if m:
                    day, mon, yr = m.group(1), m.group(2), m.group(3)
                    return f"{MONTH_MAP.get(mon, mon)} {int(day)}, {yr}"
    except Exception:
        pass
    return None


def analyze(work_dir):
    pdfs = sorted(f for f in os.listdir(work_dir) if f.lower().endswith(".pdf"))

    result = {
        "sof": None, "bna": None,
        "facbs": [], "consorcio": [], "donmar": [],
        "puerto_mariel": [], "maritime": [],
        "amarradores": [], "ammoca": [], "centro_nav": [],
        "consorcio_quequen": [], "pilotaje": [], "melluso": [], "shore_gangway": [],
        "terminal_portuario": [], "practicaje_rp": [], "coprac": [],
        "rosario_pilots": [], "amarre_coral": [], "glatil": [],
        "carp": [], "agp": [], "edi_separovic": [],
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
            # Puede haber múltiples BNAs (uno por TC). Guardar lista completa.
            result.setdefault("bna_list", []).append(fname)

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
        elif dtype == "consorcio_quequen":
            result["consorcio_quequen"].append(fname)
            result["consorcio"].append(fname)
        elif dtype == "pilotaje":
            result["pilotaje"].append(fname)
        elif dtype == "melluso":
            result["melluso"].append(fname)
        elif dtype == "shore_gangway":
            result["shore_gangway"].append(fname)
        elif dtype == "terminal_portuario":
            result["terminal_portuario"].append(fname)
        elif dtype == "practicaje_rp":
            flags = detect_pilotaje_flags(fpath)
            result["practicaje_rp"].append({
                "filename": fname,
                "has_demora": flags[0], "has_maniobra": flags[1], "maniobra_amount": flags[2]
            })
        elif dtype == "coprac":
            flags = detect_pilotaje_flags(fpath)
            result["coprac"].append({
                "filename": fname,
                "has_demora": flags[0], "has_maniobra": flags[1], "maniobra_amount": flags[2]
            })
        elif dtype == "rosario_pilots":
            flags = detect_pilotaje_flags(fpath)
            result["rosario_pilots"].append({
                "filename": fname,
                "has_demora": flags[0], "has_maniobra": flags[1], "maniobra_amount": flags[2]
            })
        elif dtype == "amarre_coral":
            import fitz as _fitz
            try:
                _text = ""
                for _pg in _fitz.open(fpath):
                    _text += _pg.get_text()
            except Exception:
                _text = ""
            _tu = _text.upper()
            is_clearance = (("DISEMBARK" in _tu and "INSPECTOR" in _tu) or
                            ("EMBARK" in _tu and "INSPECTOR" in _tu))
            is_mooring   = "MOORING" in _tu and ("UNMOORING" in _tu)
            result["amarre_coral"].append({
                "filename": fname,
                "is_clearance": is_clearance, "is_mooring": is_mooring
            })
        elif dtype == "glatil":
            result["glatil"].append(fname)
        elif dtype == "carp":
            result["carp"].append(fname)
        elif dtype == "agp":
            result["agp"].append(fname)
        elif dtype == "edi_separovic":
            result["edi_separovic"].append(fname)
        else:
            result["unknown"].append(fname)

    # Post-proceso: ordenar BNAs por TC (el de menor TC es el principal)
    bna_list = result.get("bna_list", [])
    if bna_list:
        import fitz as _fitz, re as _re
        def _get_bna_tc_quick(fname):
            try:
                doc = _fitz.open(os.path.join(work_dir, fname))
                text = doc[0].get_text()
                vals = [float(m.replace(",",".")) for m in _re.findall(r"[\d]+[,.][\d]{4}", text)]
                return max(vals) if vals else 9999
            except Exception:
                return 9999
        bna_list_sorted = sorted(bna_list, key=_get_bna_tc_quick)
        result["bna"]       = bna_list_sorted[0] if bna_list_sorted else None
        result["bna_extra"] = bna_list_sorted[1:] if len(bna_list_sorted) > 1 else []

    # Post-proceso: si sailed sigue vacío, buscarlo en Maritime
    if not result.get("sailed"):
        for m in result.get("maritime", []):
            _s = _extract_sailed_from_maritime(os.path.join(work_dir, m["filename"]))
            if _s:
                result["sailed"] = _s
                break

    # Ordenar: agency primero
    type_order = {"agency": 0, "ncb": 1, "port_expenses": 2}
    result["facbs"].sort(key=lambda f: (type_order.get(f.get("type", ""), 9), f.get("number", "")))
    for tc in result["tc_groups"]:
        result["tc_groups"][tc].sort(
            key=lambda x: 0 if x[1] == "Agency fee" else (1 if "crédito" in x[1] else 2)
        )

    result["consorcio"].sort()
    result["donmar"].sort()
    result["puerto_mariel"].sort()

    return result























