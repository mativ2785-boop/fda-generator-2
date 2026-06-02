"""
classifier.py — ISA FDA Generator · San Lorenzo / Bahia Blanca / Necochea
Version: 2.1 (Jun 2026)

Cambios respecto a v1:
- DOC_TYPES_CONTENT reconstruido desde el Excel isa_prestaciones_san_lorenzo.xlsx
  Criterio: solo proveedores DIRECTOS (emiten factura propia al FDA).
  Las agencias intermediarias se excluyen del clasificador — sus facturas
  son FACBs ISA o páginas de Maritime, nunca documentos clasificables.
- Glatil queda como tipo propio 'glatil' (alta prioridad) — no se mezcla
  con practicaje_rp aunque el Excel lo liste bajo RIVER PLATE PILOTAGE.
- Towage en San Lorenzo: nuevo tipo 'towage_sl' → TOWAGE SERVICES.
- Mandatory Holds externos: nuevo tipo 'mandatory_insp_ext' → MANDATORY HOLDS.
- _classify_image_page_deterministic: lookahead, no depende de estado.
- Deduplicación ORIGINAL: DUPLICADO/TRIPLICADO siempre se saltean.
"""

import os, re, zipfile
import fitz  # PyMuPDF

# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════════════════════════════════════

def read_text(pdf_path, max_pages=3):
    try:
        doc = fitz.open(pdf_path)
        n = min(doc.page_count, max_pages)
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
        doc = fitz.open(pdf_path)
        page = doc[idx]
        return len(page.get_images()) > 0 and len(page.get_text().strip()) < 60
    except Exception:
        return False

def is_duplicate_page(text):
    """Detecta páginas marcadas DUPLICADO o TRIPLICADO — siempre se saltean."""
    t = text.upper()
    for marker in ("DUPLICADO", "TRIPLICADO", "DUPLICATA", "COPIA"):
        if marker in t:
            return True
    return False

MAX_UNCOMPRESSED_SIZE = 300 * 1024 * 1024
MAX_FILE_SIZE         = 50  * 1024 * 1024
MAX_PDF_COUNT         = 200

def extract_zip(zip_path, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        total_size = sum(info.file_size for info in z.infolist())
        if total_size > MAX_UNCOMPRESSED_SIZE:
            raise ValueError(
                f"ZIP demasiado grande: {total_size/1024/1024:.0f} MB "
                f"(máximo {MAX_UNCOMPRESSED_SIZE//1024//1024} MB descomprimido)"
            )
        pdf_count = 0
        for member in z.infolist():
            fname = os.path.basename(member.filename)
            if not fname or not fname.lower().endswith(".pdf"):
                continue
            if member.file_size > MAX_FILE_SIZE:
                continue
            pdf_count += 1
            if pdf_count > MAX_PDF_COUNT:
                break
            dst = os.path.join(dest_dir, fname)
            with z.open(member) as src_f, open(dst, "wb") as out:
                out.write(src_f.read())
    return [f for f in os.listdir(dest_dir) if f.lower().endswith(".pdf")]


# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS DE PROVEEDORES
# Fuente: isa_prestaciones_san_lorenzo.xlsx (Jun 2026)
#
# CRITERIO DE INCLUSIÓN:
#   Solo proveedores que emiten factura PROPIA al FDA.
#   Las agencias intermediarias (Alpemar, B&G, AT Port, Supermar, etc.) se
#   excluyen — sus facturas son FACBs ISA o páginas de Maritime, no
#   documentos clasificables como proveedor de servicio.
#
# PRIORIDAD: las entradas se evalúan en orden. Glatil va ANTES de
#   practicaje_rp para que GLATIL SA no se clasifique como pilotaje RP.
#   Maritime va ANTES de los proveedores específicos para atrapar carátulas.
# ══════════════════════════════════════════════════════════════════════════════

DOC_TYPES_CONTENT = [
    # ── Documentos propios ISA (máxima prioridad) ─────────────────────────
    ("sof",      ["DETAILS OF DAILY WORKING"]),
    ("sof",      ["Standard Statement on Fact"]),
    ("sof",      ["Statement of Facts"]),
    ("sof",      ["Exceeding expectations", "VESSEL"]),

    # Maritime — carátulas y disbursement siempre skip
    # IMPORTANTE: Plate Amarres tiene 'FACT CRED ELECT MiPyME' pero NO es Maritime
    # → verificar que el nombre del proveedor no sea de amarre
    ("maritime", ["FACT CRED ELECT MiPyME", "MARITIME SHIPPING"]),
    ("maritime", ["FACT CRED ELECT", "MARITIME SHIPPING"]),
    ("maritime", ["Maritime Shipping Agency", "Disbursement"]),
    ("maritime", ["MARITIME SHIPPING AGENCY"]),

    # BNA
    ("bna", ["Cotizaciones históricas", "Dolar U.S.A"]),
    ("bna", ["Banco de la Naci", "Cotizaciones"]),
    ("bna", ["Dolar U.S.A", "Compra", "Venta", "Fecha"]),

    # FACBs ISA
    ("facb_isa", ["B00003", "INDEPENDENT SHIP AGENTS"]),
    ("facb_isa", ["B00003", "AGENCY FEE"]),
    ("facb_isa", ["B00003", "NOTA DE CREDITO"]),
    ("facb_isa", ["B00003", "CREDIT NOTE"]),
    ("facb_isa", ["A00003", "Cod.001"]),
    ("facb_isa", ["A00003", "SAN LORENZO PORT"]),
    ("facb_isa", ["A00003", "BAHIA BLANCA PORT"]),
    ("facb_isa", ["A00003", "NECOCHEA PORT"]),

    # ── ENTRANCE AND LIGHT DUES — solo ENAPRO ────────────────────────────
    ("enapro_standalone", ["Ente Administrador Puerto Rosario", "enapro.com.ar"]),
    ("enapro_standalone", ["ENAPRO", "ENTRADA"]),
    ("enapro_standalone", ["enapro.com.ar"]),
    # El Excel lista Glatil bajo RIVER PLATE PILOTAGE pero emite factura
    # propia de transporte (Pilot Launch). Monto válido: solo USD 4,440.
    ("glatil", ["GLATIL SA"]),
    ("glatil", ["GLATIL"]),
    ("glatil", ["213452850015"]),   # RUC Uruguay de Glatil

    # ── PORT DUES — terminales portuarios directos (fuente Excel) ─────────
    # Excluidas las agencias intermediarias que también aparecen en PORT DUES
    ("terminal_portuario", ["TERMINAL 6 S.A."]),
    ("terminal_portuario", ["COFCO INTERNATIONAL ARGENTINA"]),
    ("terminal_portuario", ["MOLINOS AGRO S.A."]),
    ("terminal_portuario", ["MOLINOS RIO DE LA PLATA S.A."]),
    ("terminal_portuario", ["CARGILL S.A.C. I.", "USO DE MUELLE"]),
    ("terminal_portuario", ["BUNGE ARGENTINA S.A."]),
    ("terminal_portuario", ["VICENTIN S.A.I.C.", "USO DE MUELLE"]),
    ("terminal_portuario", ["LDC ARGENTINA S.A.", "USO DE MUELLE"]),
    ("terminal_portuario", ["ADM AGRO SRL", "USO DE MUELLE"]),
    ("terminal_portuario", ["RENOVA S.A.", "USO DE MUELLE"]),
    ("terminal_portuario", ["ACEITERA GENERAL DEHEZA S A"]),
    ("terminal_portuario", ["PROFERTIL S.A."]),
    ("terminal_portuario", ["CARBOCLOR S.A."]),
    ("terminal_portuario", ["ARAUCO ARGENTINA S.A"]),
    ("terminal_portuario", ["POBATER S.A."]),
    ("terminal_portuario", ["TERMINAL PUERTO ROSARIO S.A."]),
    ("terminal_portuario", ["TERMINAL DE FERTILIZANTES ARGENTINOS SA"]),
    ("terminal_portuario", ["MINERA ALUMBRERA LIMITED"]),
    ("terminal_portuario", ["CONSORCIO DE GESTION DEL PUERTO SAN PEDRO"]),
    ("terminal_portuario", ["DEL GUAZU S.A."]),
    ("terminal_portuario", ["ENTE ADMINISTRADOR VILLA CONSTITUCION"]),
    ("terminal_portuario", ["SERVICIOS PORTUARIOS SA"]),
    ("terminal_portuario", ["MOLINO CAÑUELAS S.A.C.I.F.I.A."]),
    ("terminal_portuario", ["VITCO S.R.L."]),
    ("terminal_portuario", ["ASOC. DE COOP. ARGENTINAS CL"]),
    ("terminal_portuario", ["SERVICIOS PORTUARIOS ECOLOGICO"]),
    ("terminal_portuario", ["HELLAS MAR S A"]),

    # ── RIVER PLATE PILOTAGE — pilotos directos (fuente Excel) ───────────
    ("practicaje_rp", ["Practicaje", "Río de la Plata", "ripla.com.ar"]),
    ("practicaje_rp", ["PRACTICAJE RIO DE LA PLATA CT"]),
    ("practicaje_rp", ["33-70776769-9"]),          # CUIT Ripla
    ("practicaje_rp", ["PRACTICAJE INDEPENDIENTE S.A."]),
    ("practicaje_rp", ["SIPSA PILOTS"]),
    ("practicaje_rp", ["COOPERATIVA DE TRABAJO COMANDANTE AZOPARDO"]),
    # TAGUA PILOT solo si viene con señal de Ripla (para no confundir con Parana)
    ("practicaje_rp", ["TAGUA PILOT", "Río de la Plata"]),
    ("practicaje_rp", ["TAGUA PILOT", "ripla"]),

    # ── RIVER PARANA PILOTAGE — COPRAC y asociados (fuente Excel) ─────────
    ("coprac", ["C.O.P.R.A.C."]),
    ("coprac", ["30-64926021-0"]),                  # CUIT COPRAC
    ("coprac", ["MULTIPAR S.A."]),
    ("coprac", ["PRACTICAJE INTEGRAL S.A."]),
    ("coprac", ["RIVER PILOT S.A"]),
    ("coprac", ["COOPERATIVA DE TRABAJO CPI PILOTS LTDA"]),
    ("coprac", ["PRACTICOS DE PUERTO S A"]),
    # TAGUA PILOT / PILOTAGE SA sin señal RP → Parana
    ("coprac", ["TAGUA PILOT S.A"]),
    ("coprac", ["PILOTAGE SA"]),

    # ── PORT PILOTAGE — Rosario Pilots y asociados (fuente Excel) ─────────
    ("rosario_pilots", ["ROSARIO PILOTS COOP DE TRAB"]),
    ("rosario_pilots", ["rosariopilots.com"]),
    ("rosario_pilots", ["30-64794073-7"]),          # CUIT Rosario Pilots
    ("rosario_pilots", ["COOP DE TRABAJO PRACTICOS DEL PARANA LTDA"]),
    ("rosario_pilots", ["COOPERATIVA PRACTICOS DEL PARANA LTDA"]),  # variante real
    ("rosario_pilots", ["COOPERATIVA PRACTICOS DEL PARANA"]),
    ("rosario_pilots", ["30-71704735-0"]),           # CUIT COOP PRACTICOS DEL PARANA
    ("rosario_pilots", ["COOP TRAB PRAC D PTO LA PLATA"]),
    ("rosario_pilots", ["CORPI COOP TRAB PRACT P PARANA LTDA"]),
    ("rosario_pilots", ["PRACTICAJE DEL LITORAL S.R.L."]),
    ("rosario_pilots", ["LITORAL HARBOURS PILOTS S.A"]),
    ("rosario_pilots", ["RIO PARANA PILOTS S .A."]),
    ("rosario_pilots", ["UP RIVER PILOTS SRL"]),
    ("rosario_pilots", ["TRANSPILOT SA"]),
    ("rosario_pilots", ["PILOTOS DE PUERTO S.R.L."]),

    # ── LAUNCH SERVICES / MOORING — amarradores directos (fuente Excel) ───
    ("amarre_coral", ["AMARRE CORAL S.A."]),
    ("amarre_coral", ["30711479879"]),              # CUIT Amarre Coral
    ("amarre_coral", ["GENTE DE RIO SERVICIOS FLUVIALES SA"]),
    ("amarre_coral", ["PLATE AMARRES S. A."]),
    ("amarre_coral", ["PLUS ULTRA AMARRES S.A"]),
    ("amarre_coral", ["AMARRES Y LOGISTICA SRL"]),
    ("amarre_coral", ["NORMAN HNOS S.A."]),
    ("amarre_coral", ["LANCHAS DEL ESTE S.A."]),
    ("amarre_coral", ["NAUTICA DEL SUR SA"]),
    ("amarre_coral", ["DELTA BLUE LANCHAS SRL"]),
    ("amarre_coral", ["PROBYP S.A."]),
    ("amarre_coral", ["CLEAN SEA SA"]),
    ("amarre_coral", ["MARITIMA MARSA S.R.L."]),
    ("amarre_coral", ["WAVE AGENCIA MARITIMA S A"]),
    ("amarre_coral", ["ARROYOS S.A."]),
    ("amarre_coral", ["CN NAVEGACION S.R.L."]),
    ("amarre_coral", ["RAUL A NEGRO Y CIA SA"]),
    ("amarre_coral", ["BULK MARITIME SHIPPING S.R.L.", "MOORING"]),
    ("amarre_coral", ["COMPLEJO PORTUARIO EUROAMERICA SA"]),

    # ── TOLL DUES — CARP y AGP (fuente Excel: exactamente estos dos) ──────
    ("carp", ["Comisión Administradora del Río de la Plata"]),
    ("carp", ["COMISION ADM DEL RIO DE LP"]),
    ("carp", ["peaje@comisionriodelaplata.org"]),

    ("agp",  ["ADMINISTRACION GENERAL DE PUERTOS S. A. U."]),
    ("agp",  ["ADMINISTRACION GENERAL DE PUERTOS"]),
    ("agp",  ["30-54670628-8"]),
    # Hidrovia/Riovia también cobran peaje AGP
    ("agp",  ["HIDROVIA S.A."]),
    ("agp",  ["RIOVIA S.A."]),

    # ── FULL ON HIRE / BQS SURVEY — fuente Excel ─────────────────────────
    ("edi_separovic", ["SEPAROVIC EDI"]),
    ("edi_separovic", ["EDI SEPAROVIC"]),
    ("edi_separovic", ["20937939907"]),             # CUIT Separovic
    ("edi_separovic", ["BIANCHI EZEQUIEL MARIANO"]),
    ("edi_separovic", ["AUSTRAL MARINE SERVICES SRL"]),
    ("edi_separovic", ["COOPER BROTHERS SRL"]),
    ("edi_separovic", ["SAB MARINE SURVEYS"]),
    ("edi_separovic", ["SURVEYS NICKMANN Y ASOCIADOS"]),
    ("edi_separovic", ["UP RIVER MARINE S. R. L."]),
    ("edi_separovic", ["RUIZ DIAZ PABLO MARTIN"]),

    # ── MANDATORY HOLDS — inspectores externos (fuente Excel) ─────────────
    # Estos llegan como archivos separados cuando no vienen dentro de Maritime
    ("mandatory_insp_ext", ["SGS ARGENTINA S.A."]),
    ("mandatory_insp_ext", ["COTECNA INSPECCION ARGENTINA"]),
    ("mandatory_insp_ext", ["HL CONTROL SERVICES S.A."]),
    ("mandatory_insp_ext", ["CONTROL UNION ARG. S.A."]),
    ("mandatory_insp_ext", ["BUREAU VERITAS ARGENTINA"]),
    ("mandatory_insp_ext", ["ENVIRO CONTROLAR S R L"]),
    ("mandatory_insp_ext", ["COMETEC ARGENTINA S.A."]),
    ("mandatory_insp_ext", ["ECOTEC INTEROCEANICA S A"]),
    ("mandatory_insp_ext", ["PERALTA FEDERICO"]),

    # ── TOWAGE en San Lorenzo (fuente Excel: TOWAGE SERVICES) ─────────────
    # Remolcadores que operan en zona San Lorenzo / río Paraná
    ("towage_sl", ["ANTARES NAVIERA SA"]),
    ("towage_sl", ["SVITZER ARGENTINA SAU"]),
    ("towage_sl", ["REMOLCADORES ARTUG S.A."]),
    ("towage_sl", ["LOGISTICA Y SERVICIOS MARITIMOS S.A."]),
    ("towage_sl", ["SATECNA COSTA AFUERA SA"]),
    ("towage_sl", ["SIP PILOTAJE Y PRACTICAJE S.A."]),
    ("towage_sl", ["PETRO TANK S.A."]),
    ("towage_sl", ["FAGAL S.A."]),
    ("towage_sl", ["MADERO 802 S.A."]),
    ("towage_sl", ["LAUTA S.A."]),
    ("towage_sl", ["ARDENT MARITIME NETHERLANDS BV"]),
    ("towage_sl", ["RESOLVE MARINE GRUOUP INC"]),
    ("towage_sl", ["STANLAS SA"]),
    ("towage_sl", ["VESSEL S A"]),
    ("towage_sl", ["VESSEL ATLANTICA S.A."]),
    ("towage_sl", ["ZAPOR SA"]),
    ("towage_sl", ["AEROSPACE CARGO S.A."]),

    # ── CENTRO DE NAVEGACIÓN ──────────────────────────────────────────────
    ("centro_nav", ["Centro de Navegación Asociación Civil"]),
    ("centro_nav", ["CENTRO DE NAVEGACION ASOCIACION CIVIL"]),
    ("centro_nav", ["cnav.org.ar"]),
    ("centro_nav", ["centrodenavegaci"]),
    ("centro_nav", ["Centro de Navegaci", "Florida 537"]),

    # ── Bahia Blanca ──────────────────────────────────────────────────────
    ("consorcio", ["Consorcio de Gestión del Puerto de Bahia Blanca"]),
    ("consorcio", ["CONSORCIO DE GESTION DEL PUERTO DE BAHIA BLANCA"]),
    ("consorcio", ["USO DE PUERTO ULTRAMAR"]),
    ("donmar",    ["DONMAR S.A."]),
    ("puerto_mariel", ["PUERTO MARIEL SA"]),
    ("puerto_mariel", ["ARGENTINA TOWAGE"]),
    ("amarradores", ["AMARRADORES DEL PUERTO DE BAHIA BLANCA"]),
    ("ammoca",    ["AMMOCA S.A."]),
    ("ammoca",    ["FUGRAN COMERCIAL E INDUSTRIAL SA"]),  # Excel: PEST CONTROL

    # ── Necochea ──────────────────────────────────────────────────────────
    ("consorcio_quequen", ["Consorcio de Gestión del Puerto Quequén"]),
    ("consorcio_quequen", ["Puerto Quequén", "Juan de Garay"]),
    ("consorcio_quequen", ["30-66634948-9"]),
    ("pilotaje",   ["MEYER", "ARANA", "Necochea"]),
    ("melluso",    ["MELLUSO S.A."]),
    ("melluso",    ["SERVICIO DE LANCHAS Y AMARRADORES PUERTO QUEQUEN"]),
    ("shore_gangway", ["SHORE GANGWAY", "30716643685"]),
]

# ── Clasificación por nombre de archivo (fallback sin texto) ──────────────────
DOC_TYPES_NAME = [
    ("sof",               ["SOF", "STATEMENT"]),
    ("bna",               ["BANCO", "BNA", "NACION"]),
    ("facb_isa",          ["FACB", "FACA", "N_CB", "NCB"]),
    ("glatil",            ["GLATIL"]),
    ("consorcio",         ["CONSORCIO", "PUERTO DE BAHIA"]),
    ("donmar",            ["DONMAR"]),
    ("puerto_mariel",     ["MARIEL"]),
    ("maritime",          ["MARITIME", "MARITIM"]),
    ("amarradores",       ["AMARRADORES"]),
    ("ammoca",            ["AMMOCA", "FUGRAN"]),
    ("centro_nav",        ["NAVEGACION", "CNAV"]),
    ("consorcio_quequen", ["QUEQUEN", "QUEQU"]),
    ("pilotaje",          ["MEYER", "ARANA"]),
    ("melluso",           ["MELLUSO"]),
    ("shore_gangway",     ["GANGWAY", "PASARELA"]),
    # Terminales — solo terminales reales en el nombre
    ("terminal_portuario", ["TERMINAL 6", "COFCO", "MOLINOS AGRO", "CARGILL",
                            "BUNGE", "VICENTIN", "LDC ARGENTINA", "RENOVA",
                            "PROFERTIL", "CARBOCLOR", "TERMINAL PUERTO ROSARIO",
                            "ADM AGRO", "ACEITERA GENERAL DEHEZA",
                            "TERMINAL DE FERTILIZANTES", "POBATER", "ARAUCO"]),
    # Pilotos — solo empresas piloto reales
    ("practicaje_rp",    ["PRACTICAJE RIO", "RIPLA", "SIPSA PILOTS",
                          "PRACTICAJE INDEPENDIENTE", "COMANDANTE AZOPARDO"]),
    ("coprac",           ["COPRAC", "MULTIPAR", "RIVER PILOT",
                          "PRACTICAJE INTEGRAL", "CPI PILOTS"]),
    ("rosario_pilots",   ["ROSARIO PILOTS", "PRACTICAJE DEL LITORAL",
                          "LITORAL HARBOURS", "UP RIVER PILOTS", "RIO PARANA PILOTS",
                          "COOP DE TRABAJO PRACTICOS DEL PARANA",
                          "COOPERATIVA PRACTICOS DEL PARANA",
                          "PILOTOS DE PUERTO", "TRANSPILOT"]),
    # Amarradores — solo empresas de amarre reales
    ("amarre_coral",     ["AMARRE CORAL", "GENTE DE RIO", "PLATE AMARRES",
                          "PLUS ULTRA AMARRES", "AMARRES Y LOGISTICA", "NORMAN HNOS",
                          "NAUTICA DEL SUR", "LANCHAS DEL ESTE", "DELTA BLUE LANCHAS",
                          "MARITIMA MARSA", "PROBYP", "CLEAN SEA", "WAVE AGENCIA",
                          "ARROYOS SA", "CN NAVEGACION"]),
    ("carp",             ["CARP", "COMISION ADM"]),
    ("agp",              ["ADMINISTRACION GENERAL DE PUERTOS", "HIDROVIA", "RIOVIA"]),
    ("edi_separovic",    ["SEPAROVIC", "BIANCHI EZEQUIEL", "AUSTRAL MARINE",
                          "COOPER BROTHERS", "SAB MARINE", "SURVEYS NICKMANN",
                          "UP RIVER MARINE"]),
    ("mandatory_insp_ext",["SGS ARGENTINA", "COTECNA", "CONTROL UNION",
                           "BUREAU VERITAS", "ENVIRO CONTROLAR", "COMETEC",
                           "ECOTEC INTEROCEANICA"]),
    ("towage_sl",        ["SVITZER", "REMOLCADORES ARTUG", "ANTARES NAVIERA",
                          "SATECNA", "LOGISTICA Y SERVICIOS MARITIMOS"]),
]


def detect_pilotaje_flags(pdf_path):
    """
    Detecta DEMORA y línea MANIOBRA con monto en facturas de pilotaje.
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
    has_demora = "DEMORA" in text_up or "PRACTICO A LA ORDEN" in text_up

    has_maniobra    = False
    maniobra_amount = 0.0
    lines = text.split("\n")

    for i, line in enumerate(lines):
        lu = line.upper()
        if "MANIOBRA" not in lu:
            continue

        # Formato A: monto USD en la misma línea — Ripla
        # "1 MANIOBRAS EN ZC USD 2,520.00"  o  "1 MANIOBRAS EN ZC USD 2.520,00"
        m = re.search(r"USD\s*([\d\.,]+)", line)
        if m:
            raw = m.group(1)
            try:
                # Formato europeo: "2.520,00" → 2520.00
                if "," in raw and raw.index(",") > raw.index(".") if "." in raw else False:
                    val = float(raw.replace(".", "").replace(",", "."))
                else:
                    val = float(raw.replace(",", ""))
                if val > 100:
                    has_maniobra = True
                    maniobra_amount += val
                    continue
            except ValueError:
                pass

        # Buscar monto en líneas siguientes (ventana de 5 líneas)
        for j in range(i + 1, min(i + 6, len(lines))):
            clean = lines[j].replace("|", "").strip()
            if not clean:
                continue

            # Saltear líneas de cantidad (1.00, 2.00, etc.) — son cantidades no montos
            qty_match = re.match(r"^\d+\.00$", clean)
            if qty_match and float(clean) < 100:
                continue

            # Formato "2.520,00" (punto=miles, coma=decimal) — COPRAC en ARS / Ripla
            m3 = re.match(r"^([\d]+\.[\d]{3},[\d]{2})$", clean)
            if m3:
                try:
                    val = float(m3.group(1).replace(".", "").replace(",", "."))
                    if val > 100:
                        has_maniobra = True
                        maniobra_amount += val
                except ValueError:
                    pass
                break

            # Formato "USD 2.520,00" (prefijo USD + punto miles + coma decimal) — Ripla LASKARO
            m_usd_eu = re.match(r"^USD\s+([\d]+\.[\d]{3},[\d]{2})$", clean)
            if m_usd_eu:
                try:
                    val = float(m_usd_eu.group(1).replace(".", "").replace(",", "."))
                    if val > 100:
                        has_maniobra = True
                        maniobra_amount += val
                except ValueError:
                    pass
                break

            # Formato "2,520.00" USD — Ripla estándar
            m4 = re.match(r"^USD\s*([\d,]+\.\d{2})$", clean)
            if m4:
                try:
                    val = float(m4.group(1).replace(",", ""))
                    if val > 100:
                        has_maniobra = True
                        maniobra_amount += val
                except ValueError:
                    pass
                break

            # Formato Multipar — precio unitario en USD sin prefijo
            # Estructura: MANIOBRA... | 2.00 (qty) | 966.00 (unit_price) | 1,932.00 (total)
            # Buscamos el primer número > 100 después de la línea MANIOBRA
            m5 = re.match(r"^([\d,]+\.\d{2})$", clean)
            if m5:
                try:
                    val = float(m5.group(1).replace(",", ""))
                    if 200 < val < 50000:
                        has_maniobra = True
                        maniobra_amount += val
                        break
                    # Si val <= 200 podría ser otro número pequeño, seguir buscando
                except ValueError:
                    pass
                continue

            # Si encontramos otra línea de concepto textual, parar búsqueda
            if re.match(r"^[A-Z][A-Z ]{3,}$", clean):
                break

    # Multipar: la detección de MANIOBRA por texto es suficiente incluso si
    # no se extrajo el monto exacto (las facturas son en ARS, el monto USD
    # se calcula por la FACB ISA). En ese caso, maniobra_amount queda en 0
    # y ports.py usará el valor de la FACB.
    return has_demora, has_maniobra, maniobra_amount


def classify_doc(pdf_path):
    """Clasifica el PDF. Primero por contenido (case-insensitive), luego por nombre."""
    fname = os.path.basename(pdf_path).upper()
    text  = read_text(pdf_path, max_pages=3)
    text_up = text.upper()

    if text.strip():
        for (dtype, keywords) in DOC_TYPES_CONTENT:
            if all(kw.upper() in text_up for kw in keywords):
                return dtype

    for (dtype, keywords) in DOC_TYPES_NAME:
        if any(kw in fname for kw in keywords):
            return dtype

    return "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# CLASIFICADOR DE PÁGINAS DE MARITIME
# ══════════════════════════════════════════════════════════════════════════════

MARITIME_PAGE_RULES = [
    # ── Siempre skip ──────────────────────────────────────────────────────
    ("skip",             ["FACT CRED ELECT"]),
    ("skip",             ["MiPyME"]),
    ("skip",             ["Disbursement Account"]),
    ("skip",             ["DISBURSEMENT ACCOUNT"]),
    ("skip",             ["Cotizaciones históricas", "Dolar U.S.A"]),
    ("skip",             ["Banco de la Naci", "Cotizaciones"]),
    # SERVICE CERTIFICATE de MSA — nunca aparece en el FDA
    ("skip",             ["SERVICE CERTIFICATE"]),
    ("skip",             ["CERTIFICATE OF SERVICE"]),

    # ── Headclerk ─────────────────────────────────────────────────────────
    ("headclerk_break",  ["HEAD CLERK", "Breakdown"]),
    ("headclerk_liq",    ["LIQUIDACION DE PAGO A ENCARGADOS"]),

    # ── Watchmen ──────────────────────────────────────────────────────────
    ("watchmen_break",   ["WATCHMEN", "Breakdown"]),
    ("watchmen_liq",     ["LIQUIDACION DE PAGO", "SERENO"]),
    ("watchmen_liq",     ["Jornales / Wages", "Movilidad / Travel"]),

    # ── Custom House ──────────────────────────────────────────────────────
    ("afip_lman",        ["LMAN", "ADMINISTRACION FEDERAL DE INGRESOS"]),
    ("afip_lman",        ["LMAN", "DATOS AFIP"]),
    ("se_inward",        ["SOLICITUD DE HABILITACION", "FORMALIZACION DE ENTRADA"]),
    ("se_inward",        ["SOLICITUD DE HABILITACION", "FEVA"]),
    ("se_permanencia",   ["SOLICITUD DE HABILITACION", "permanencia"]),
    ("se_permanencia",   ["SOLICITUD DE HABILITACION", "PERMANENCIA"]),
    ("se_rancho",        ["SOLICITUD DE HABILITACION", "RANCHO"]),
    ("se_rancho",        ["SOLICITUD DE HABILITACION", "VLSFO"]),
    ("se_cargo",         ["SOLICITUD DE HABILITACION", "ZONA PRIMARIA"]),
    ("se_cargo",         ["SOLICITUD DE HABILITACION", "ECZP"]),
    ("se_cargo",         ["SOLICITUD DE HABILITACION", "HARINA"]),
    ("se_cargo",         ["SOLICITUD DE HABILITACION", "CARGO"]),
    # Fallback SSEE genérico → Custom House Expenses
    ("se_inward",        ["SOLICITUD DE HABILITACION DE", "SERVICIOS EXTRAORDINARIOS"]),

    # ── Migration ─────────────────────────────────────────────────────────
    ("migraciones_liq",  ["Migraciones", "quincena"]),
    ("migraciones_liq",  ["Migraciones", "Liquidaci"]),
    ("migraciones_sol",  ["Servicios Marítimos y Fluviales", "Solicitud de Servicio"]),

    # ── Orden de transporte — clasificar por DETAIL OF TRIP al final ─────
    # GARBAGE/SENASA: el trip dice "SE.NA.SA OFFICE"
    ("orden_transporte_senasa",  ["ORDEN DE TRANSPORTE", "SE.NA.SA"]),
    ("orden_transporte_senasa",  ["ORDEN DE TRANSPORTE", "SENASA OFFICE"]),
    ("orden_transporte_senasa",  ["ORDEN DE TRANSPORTE", "SE.NA.SA OFFICE"]),
    # SANITARY: exclusivamente para Free Pratique con Ministerio de Salud
    ("orden_transporte_sanidad", ["ORDEN DE TRANSPORTE", "FREE PRATIQUE", "SANITARY"]),
    ("orden_transporte_sanidad", ["ORDEN DE TRANSPORTE", "LIBRE PLATICA", "MINISTERIO DE SALUD"]),
    # MIGRATION: el trip dice "MIGRATION OFFICE" (puede mencionar Libre Plática entre otros servicios)
    ("orden_transporte",         ["ORDEN DE TRANSPORTE", "MIGRATION OFFICE"]),
    # Genérico → MIGRATION (catch-all)
    ("orden_transporte",         ["ORDEN DE TRANSPORTE"]),

    # ── Sanitary / Free Pratique ─────────────────────────────────────────
    # Certificado oficial: "República Argentina - Poder Ejecutivo Nacional"
    ("sanidad_cert",     ["República Argentina", "Certificado de Libre"]),
    ("sanidad_cert",     ["PODER EJECUTIVO NACIONAL", "LIBRE PL"]),
    ("sanidad_cert",     ["Certificado de Libre Plática"]),
    ("sanidad_cert",     ["CERTIFICADO DE LIBRE PLÁTICA"]),
    ("sanidad_cert",     ["Libre Plática"]),
    ("sanidad_cert",     ["Certificado de Libre"]),
    ("sanidad_cert",     ["FREE PRACTIQUE"]),          # recibo/certificado
    ("sanidad_cert",     ["COMPULSORY SANITARY DUES"]),
    ("sanidad_eval",     ["EVALUACIÓN DE RIESGOS"]),
    ("sanidad_eval",     ["Evaluación de Libre Plática"]),
    ("sanidad_transf",   ["MINISTERIO DE SALUD", "COMPULSORY SANITARY"]),
    ("sanidad_transf",   ["MINISTERIO DE SALUD"]),
    ("sanidad_recibo",   ["FREE PRACTIQUE", "Recib"]),

    # ── Garbage ───────────────────────────────────────────────────────────
    ("senasa",           ["SENASA", "BOLETA DE PAGO"]),
    ("senasa",           ["BOLETA DE PAGO", "Barreras Sanitarias"]),
    ("senasa",           ["Barreras Sanitarias", "BOLETA"]),
    ("senasa",           ["Barreras Sanitarias", "ARANCEL"]),
    ("senasa",           ["Barreras Sanitarias", "Regional"]),

    # ── Mandatory Holds ───────────────────────────────────────────────────
    ("compulsory_insp",  ["COMPULSORY INSPECTION BY PRIVATE SURVEYORS"]),
    ("compulsory_insp",  ["COMPULSORY INSPECTION", "PRIVATE SURVEYORS"]),
    ("compulsory_insp",  ["LCI REPORT"]),
    ("compulsory_insp",  ["Fides Control", "INSPECTION"]),
    ("compulsory_insp",  ["FACTURA SERV.ELECTR", "INSPEC"]),
    ("compulsory_insp",  ["BUREAU VERITAS", "INSPECTION"]),
    ("compulsory_insp",  ["SGS ARGENTINA", "INSPECTION"]),
    ("compulsory_insp",  ["VOUCHER", "COMPULSORY INSPECTION"]),
    ("compulsory_reinsp",["RE-INSPECTION", "PRIVATE SURVEYORS"]),
    ("compulsory_reinsp",["REINSPECTION", "PRIVATE SURVEYORS"]),

    # ── ENAPRO dentro de Maritime ─────────────────────────────────────────
    ("enapro",           ["Ente Administrador Puerto Rosario"]),
    ("enapro",           ["enapro.com.ar"]),
    ("enapro",           ["ENAPRO"]),

    # ── Mooring / navigation center ──────────────────────────────────────
    ("amarradores_pag",  ["AMARRADORES"]),
    ("nav_center",       ["Centro de Navegación", "cnav.org.ar"]),
    ("nav_center",       ["centrodenavegaci", "FACTURA"]),

    # ── OSRO / Pest ────────────────────────────────────────────────────────
    ("osro",             ["OSRO", "BARRERAS FLOTANTES"]),
    ("osro",             ["COMPULSORY BARRIER"]),
    ("pest_pag",         ["AMMOCA"]),
    ("pest_pag",         ["FUGRAN COMERCIAL"]),

    # ── Necochea ──────────────────────────────────────────────────────────
    ("meyer_arana",      ["MEYER", "ARANA", "Necochea"]),
    ("melluso",          ["MELLUSO S.A."]),
    ("shore_gangway_pag",["SHORE GANGWAY", "30716643685"]),
]

PAGE_TO_VOUCHER = {
    "headclerk_break":       "HEADCLERK COMPULSORY SERVICES",
    "headclerk_liq":         "HEADCLERK COMPULSORY SERVICES",
    "watchmen_break":        "WATCHMEN COMPULSORY SERVICES",
    "watchmen_liq":          "WATCHMEN COMPULSORY SERVICES",
    "afip_lman":             "CUSTOM HOUSE EXPENSES",
    "se_inward":             "CUSTOM HOUSE EXPENSES",
    "se_permanencia":        "CUSTOM HOUSE PERMANENCE",
    "se_rancho":             "CUSTOM HOUSE (BUNKERING)",
    "se_cargo":              "CUSTOM HOUSE EXPENSE (CARGO)",
    "migraciones_liq":       "MIGRATION EXPENSES",
    "migraciones_sol":       "MIGRATION EXPENSES",
    "orden_transporte":      "MIGRATION EXPENSES",
    "orden_transporte_sanidad": "SANITARY DUES AND FREE PRATIQUE",
    "orden_transporte_senasa":"GARBAGE COMPULSORY INSPECTION",
    "sanidad_cert":          "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_eval":          "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_transf":        "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_recibo":        "SANITARY DUES AND FREE PRATIQUE",
    "senasa":                "GARBAGE COMPULSORY INSPECTION",
    "enapro":                "ENTRANCE AND LIGHT DUES",
    "amarradores_pag":       "MOORING & UNMOORING SERVICES",
    "nav_center":            "NAVIGATION CENTER CONTRIBUTION",
    "meyer_arana":           "PORT PILOTAGE",
    "melluso":               "MOORING & UNMOORING SERVICES",
    "shore_gangway_pag":     "SHORE GANGWAY",
    "osro":                  "OSRO ANNEX 18",
    "pest_pag":              "PEST CONTROL",
    "compulsory_insp":       "MANDATORY HOLDS INSPECTION",
    "compulsory_reinsp":     "MANDATORY HOLDS RE-INSPECTION",
    "coast_guard":           "COAST GUARD EXPENSES",
    "skip":                  None,
    "skip_dup":              None,
    "mooring_img":           "MOORING & UNMOORING SERVICES",
    "unknown":               None,
}


def _classify_image_page_deterministic(pdf_path, idx):
    """
    Clasifica una página imagen usando lookahead del texto de páginas cercanas.
    Determinista: no depende del estado acumulado previo.
    """
    try:
        doc   = fitz.open(pdf_path)
        total = doc.page_count

        # Buscar en las 8 páginas siguientes (ventana más amplia)
        for j in range(idx + 1, min(idx + 9, total)):
            t = doc[j].get_text().upper()
            if any(k in t for k in ("MINISTERIO DE SALUD", "FREE PRACTIQUE",
                                     "LIBRE PLÁTICA", "LIBRE PLATICA",
                                     "SANIDAD", "PRATIQUE", "LIBRE PRATICA")):
                return "sanidad_cert"
            if any(k in t for k in ("COMPULSORY INSPECTION", "LCI REPORT",
                                     "FIDES CONTROL", "VOUCHER", "BUREAU VERITAS",
                                     "DUHAU", "SGS ARGENTINA", "CONTROL UNION")):
                return "compulsory_insp"
            if any(k in t for k in ("SENASA", "BARRERAS SANITARIAS")):
                return "senasa"
            if any(k in t for k in ("LMAN", "AFIP", "ADMINISTRACION FEDERAL",
                                     "HABILITACION", "SOLICITUD DE")):
                return "afip_lman"
            if any(k in t for k in ("MIGRACION", "MIGRACIONES",
                                     "SERVICIO MIGRATORIO", "ORDEN DE TRANSPORTE")):
                return "migraciones_liq"
            if any(k in t for k in ("MOORING", "UNMOORING", "AMARRE")):
                return "mooring_img"

        # Buscar en las 5 páginas anteriores
        for j in range(idx - 1, max(idx - 6, -1), -1):
            t = doc[j].get_text().upper()
            if any(k in t for k in ("MINISTERIO DE SALUD", "FREE PRACTIQUE",
                                     "LIBRE PLÁTICA", "LIBRE PLATICA", "PRATIQUE")):
                return "sanidad_cert"
            if any(k in t for k in ("COMPULSORY INSPECTION", "LCI REPORT",
                                     "BUREAU VERITAS", "DUHAU", "SGS ARGENTINA")):
                return "compulsory_insp"
            if any(k in t for k in ("AFIP", "LMAN", "HABILITACION")):
                return "afip_lman"
            if any(k in t for k in ("MOORING", "UNMOORING", "AMARRE")):
                return "mooring_img"
    except Exception:
        pass

    return "mooring_img"


def classify_maritime_pages(pdf_path):
    n      = page_count(pdf_path)
    result = []
    seen_lman = set()

    for i in range(n):
        text = read_page(pdf_path, i)

        # Saltar páginas de DUPLICADO/TRIPLICADO
        if is_duplicate_page(text):
            result.append({"page": i, "category": "skip_dup", "voucher": None})
            continue

        if is_image_page(pdf_path, i):
            category = _classify_image_page_deterministic(pdf_path, i)
            voucher  = PAGE_TO_VOUCHER.get(category, "MOORING & UNMOORING SERVICES")
            result.append({"page": i, "category": category, "voucher": voucher})
            continue

        cat = "unknown"
        for (category, keywords) in MARITIME_PAGE_RULES:
            if all(kw in text for kw in keywords):
                cat = category
                break

        # Páginas imagen → clasificar por contexto
        if is_image_page(pdf_path, i):
            cat = _classify_image_page_deterministic(pdf_path, i)

        # Páginas "unknown" con texto: clasificar por contenido
        if cat == "unknown" and text.strip():
            tu = text.upper()
            if any(k in tu for k in ("BUREAU VERITAS", "DUHAU", "SGS ARGENTINA",
                                      "COTECNA", "CONTROL UNION", "ECOTEC",
                                      "COMETEC", "ENVIRO CONTROLAR")):
                cat = "compulsory_insp"
            elif any(k in tu for k in ("MOORING", "UNMOORING", "AMARRE")):
                cat = "amarradores_pag"
            elif any(k in tu for k in ("PREFECTURA NAVAL", "SEÑOR JEFE",
                                        "SR. JEFE", "JEFE DE LA PREF",
                                        "COAST GUARD")):
                cat = "coast_guard"
            elif "PERMANENCIA ADUANERA" in tu:
                cat = "se_permanencia"
            elif any(k in tu for k in ("LIBRE PLATIC", "FREE PRATIC", "PRATIQUE",
                                        "COMPULSORY SANITARY", "PODER EJECUTIVO NACIONAL")):
                cat = "sanidad_cert"
            # Service Certificate nunca va en FDA
            elif "SERVICE CERTIFICATE" in tu or "CERTIFICATE OF SERVICE" in tu:
                cat = "skip"

        # Excluir VOUCHER INTERNO de compulsory (recibo ISA, no factura inspector)
        if cat == "compulsory_insp" and "VOUCHER" in text.upper() and \
                ("MV:" in text.upper() or "M/V" in text.upper()):
            cat = "skip"

        # Deduplicar AFIP LMAN — solo por referencia de texto, nunca por ser imagen
        if cat == "afip_lman":
            m = re.search(r"LMAN(\w+)", text)
            ref = m.group(1) if m else f"p{i}"
            if ref in seen_lman:
                cat = "skip_dup"
            else:
                seen_lman.add(ref)

        # skip_dup con contenido útil → rescatar
        if cat == "skip_dup" and text.strip():
            tu2 = text.upper()
            if any(k in tu2 for k in ("BARRERAS SANITARIAS", "COORDINACION GENERAL",
                                       "COORDINACIÓN GENERAL", "BOLETA REQUERIDO",
                                       "BOLETA ARANCEL")):
                cat = "senasa"
            elif any(k in tu2 for k in ("LIBRE PLATIC", "FREE PRATIC", "PRATIQUE",
                                         "COMPULSORY SANITARY")):
                cat = "sanidad_cert"

        voucher = PAGE_TO_VOUCHER.get(cat, None)
        result.append({"page": i, "category": cat, "voucher": voucher})

    return result


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE DATOS DE FACB ISA
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
        nums = [l.strip() for l in text.split("\n")
                if re.match(r"^[\d,]+\.\d{2}$", l.strip())]
        if nums:
            d["total"] = float(nums[-1].replace(",", ""))
    else:
        m = re.search(r"(?:TOTAL|SubTotal)\s+USD\s+([\d,]+\.?\d*)", text)
        if m:
            d["total"] = float(m.group(1).replace(",", ""))

    text_up = text.upper()
    if "AGENCY FEE" in text_up:
        d["type"]  = "agency"
        d["label"] = "Agency fee"
    elif any(k in text_up for k in ("NCB", "NOTA DE CREDITO", "NOTA DE CRÉDITO",
                                     "CREDIT NOTE", "Cod.008".upper())):
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
        for pat, key in [(r"Account Number:\s*\$?([\d\-/]+)", "bank_account"),
                         (r"CBU:\s*([\d]+)",                  "bank_cbu"),
                         (r"Beneficiary: ([^\n]+)",            "bank_beneficiary"),
                         (r"CUIT:\s*([\d\-]+)",                "bank_cuit")]:
            mm = re.search(pat, text)
            if mm:
                d[key] = mm.group(1).strip()
    else:
        d["bank_name"]        = "Citibank N.A., New York Branch"
        d["bank_aba"]         = "21000089"
        d["bank_swift"]       = "CITIUS33"
        d["bank_account"]     = "36404074"
        d["bank_beneficiary"] = "INDEPENDENT SHIP AGENTS S.A."

    if   "NECOCHEA PORT"    in text_up: d["port"] = "Necochea Port"
    elif "BAHIA BLANCA PORT" in text_up: d["port"] = "Bahia Blanca Port"
    elif "SAN LORENZO PORT"  in text_up: d["port"] = "San Lorenzo Port"
    elif "ARROYO SECO PORT"  in text_up: d["port"] = "San Lorenzo Port"
    elif any(p in text_up for p in ("GRAL. LAGOS PORT", "GENERAL LAGOS PORT")):
        d["port"] = "San Lorenzo Port"

    return d


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE DATOS DEL SOF
# ══════════════════════════════════════════════════════════════════════════════

MONTH_MAP = {
    "01": "January",  "02": "February", "03": "March",    "04": "April",
    "05": "May",      "06": "June",     "07": "July",     "08": "August",
    "09": "September","10": "October",  "11": "November", "12": "December",
}

def extract_sof(pdf_path):
    text = read_text(pdf_path, max_pages=3)
    d    = {}

    m = re.search(r'm\.v\.\s*["\']?([A-Z][A-Z0-9\s"\']+ ?)["\']?\s*[\r\n]', text)
    if m:
        d["vessel"] = "M/V " + m.group(1).strip().strip("\"'")

    m = re.search(r'Sailed?\s*[\r\n\s:]+(\d{1,2})/(\d{2})/(\d{4})', text)
    if m:
        day, mon, yr = m.group(1), m.group(2), m.group(3)
        d["sailed"]  = f"{MONTH_MAP.get(mon, mon)} {int(day)}, {yr}"

    if   "Bahia Blanca"  in text or "BAHIA BLANCA"  in text: d["port"] = "Bahia Blanca Port"
    elif "Necochea"      in text or "QUEQUEN"        in text: d["port"] = "Necochea Port"
    elif "San Lorenzo"   in text or "SAN LORENZO"   in text: d["port"] = "San Lorenzo Port"
    elif "Arroyo Seco"   in text or "ARROYO SECO"   in text: d["port"] = "San Lorenzo Port"

    return d


# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS COMPLETO DEL DIRECTORIO
# ══════════════════════════════════════════════════════════════════════════════

def _extract_sailed_from_maritime(pdf_path):
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


def _get_bna_tc_quick(path):
    try:
        import fitz as _fitz
        doc  = _fitz.open(path)
        text = doc[0].get_text()
        vals = [float(m.replace(",", "."))
                for m in re.findall(r"[\d]+[,.][\d]{4}", text)]
        return max(vals) if vals else 9999
    except Exception:
        return 9999


def analyze(work_dir):
    pdfs = sorted(f for f in os.listdir(work_dir) if f.lower().endswith(".pdf"))

    result = {
        "sof": None, "bna": None, "bna_list": [], "bna_extra": [],
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
            result["bna_list"].append(fname)

        elif dtype == "facb_isa":
            d           = extract_facb(fpath)
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

        elif dtype in ("consorcio", "consorcio_quequen"):
            result["consorcio"].append(fname)
            if dtype == "consorcio_quequen":
                result["consorcio_quequen"].append(fname)

        elif dtype == "donmar":        result["donmar"].append(fname)
        elif dtype == "puerto_mariel": result["puerto_mariel"].append(fname)
        elif dtype == "maritime":
            pages = classify_maritime_pages(fpath)
            result["maritime"].append({"filename": fname, "pages": pages})
        elif dtype == "amarradores":   result["amarradores"].append(fname)
        elif dtype == "ammoca":        result["ammoca"].append(fname)
        elif dtype == "centro_nav":    result["centro_nav"].append(fname)
        elif dtype == "pilotaje":      result["pilotaje"].append(fname)
        elif dtype == "melluso":       result["melluso"].append(fname)
        elif dtype == "shore_gangway": result["shore_gangway"].append(fname)
        elif dtype == "terminal_portuario":
            result["terminal_portuario"].append(fname)

        elif dtype == "practicaje_rp":
            flags = detect_pilotaje_flags(fpath)
            result["practicaje_rp"].append({
                "filename": fname,
                "has_demora": flags[0], "has_maniobra": flags[1],
                "maniobra_amount": flags[2]
            })
        elif dtype == "coprac":
            flags = detect_pilotaje_flags(fpath)
            result["coprac"].append({
                "filename": fname,
                "has_demora": flags[0], "has_maniobra": flags[1],
                "maniobra_amount": flags[2]
            })
        elif dtype == "rosario_pilots":
            flags = detect_pilotaje_flags(fpath)
            result["rosario_pilots"].append({
                "filename": fname,
                "has_demora": flags[0], "has_maniobra": flags[1],
                "maniobra_amount": flags[2]
            })
        elif dtype == "amarre_coral":
            try:
                _doc  = fitz.open(fpath)
                _text = "".join(pg.get_text() for pg in _doc).upper()
            except Exception:
                _text = ""
            # REGLA: la distinción es por CONTENIDO de la factura, no por proveedor.
            # Gente de Rio, Plate Amarres, Amarre Coral, Plus Ultra, etc.
            # pueden tener facturas de los dos tipos en el mismo FDA.
            #
            # LAUNCH SERVICES FOR CLEARANCE (AT ROADS):
            #   → factura dice EMBARKING INSPECTORS AND AGENCY
            #                o DISEMBARKING INSPECTORS AND AGENCY
            #                o BOAT SERVICES EMBARKING / DISEMBARKING
            #
            # MOORING & UNMOORING SERVICES:
            #   → factura dice MOORING, UNMOORING, AMARRE, DESAMARRE
            #   → o "Boat service/people for mooring" (Amarre Coral formato inglés)
            is_clearance = (
                ("EMBARKING INSPECTORS AND AGENCY"    in _text) or
                ("DISEMBARKING INSPECTORS AND AGENCY" in _text) or
                ("EMBARKING INSPECTORS"               in _text) or
                ("DISEMBARKING INSPECTORS"            in _text) or
                ("BOAT SERVICES EMBARKING"            in _text) or
                ("BOAT SERVICES DISEMBARKING"         in _text) or
                ("BOAT SERVICE EMBARKING"             in _text) or
                ("BOAT SERVICE DISEMBARKING"          in _text) or
                ("PEOPLE FOR EMBARKING"               in _text) or
                ("PEOPLE FOR DISEMBARKING"            in _text)
            )
            is_mooring = (
                "MOORING"   in _text or
                "UNMOORING" in _text or
                "AMARRE"    in _text or
                "DESAMARRE" in _text or
                "BOAT SERVICE/PEOPLE FOR MOORING" in _text or
                "BOAT SERVICES FOR MOORING"       in _text or
                "PEOPLE FOR MOORING"              in _text
            )
            # Si una factura tiene ambas descripciones (poco común pero posible),
            # la descripción de clearance tiene prioridad sobre mooring
            if is_clearance and is_mooring:
                # Verificar cuál es la descripción principal (primer concepto)
                # Si "EMBARKING" aparece antes que "MOORING" → clearance
                pos_clear  = min(
                    (_text.find(k) for k in
                     ("EMBARKING INSPECTORS", "DISEMBARKING INSPECTORS")
                     if k in _text),
                    default=99999
                )
                pos_moor = min(
                    (_text.find(k) for k in ("MOORING", "AMARRE")
                     if k in _text),
                    default=99999
                )
                if pos_clear < pos_moor:
                    is_mooring = False
                else:
                    is_clearance = False
            # Default: si no hay señal clara en el texto (factura es imagen),
            # clasificar por nombre del proveedor como heurística
            if not is_clearance and not is_mooring:
                fname_up = fname.upper()
                # Gente de Rio históricamente provee clearance
                if "GENTE DE RIO" in fname_up:
                    is_clearance = True
                else:
                    is_mooring = True
            result["amarre_coral"].append({
                "filename": fname,
                "is_clearance": is_clearance,
                "is_mooring":   is_mooring
            })
        elif dtype == "glatil":             result["glatil"].append(fname)
        elif dtype == "carp":               result["carp"].append(fname)
        elif dtype == "agp":                result["agp"].append(fname)
        elif dtype == "edi_separovic":      result["edi_separovic"].append(fname)
        elif dtype == "towage_sl":          result.setdefault("towage_sl", []).append(fname)
        elif dtype == "mandatory_insp_ext": result.setdefault("mandatory_insp_ext", []).append(fname)
        elif dtype == "enapro_standalone":  result.setdefault("enapro_standalone", []).append(fname)
        else:                               result["unknown"].append(fname)

    # ── Post-proceso BNA ──────────────────────────────────────────────────
    bna_sorted = sorted(result["bna_list"],
                        key=lambda f: _get_bna_tc_quick(os.path.join(work_dir, f)))
    result["bna"]       = bna_sorted[0]  if bna_sorted       else None
    result["bna_extra"] = bna_sorted[1:] if len(bna_sorted) > 1 else []

    # ── Post-proceso: sailed desde múltiples fuentes ─────────────────────
    # Estrategia: recopilar todas las fechas candidatas y elegir la correcta.
    # La fecha de salida real del buque está en los disbursement más recientes
    # (los archivos W con número más alto). Si hay conflicto, la FACB gana.
    if not result.get("sailed"):
        sailed_candidates = []

        # Fuente 1: Maritime disbursement — recopilar TODAS las fechas
        for m_entry in result.get("maritime", []):
            _s = _extract_sailed_from_maritime(os.path.join(work_dir, m_entry["filename"]))
            if _s:
                sailed_candidates.append((_s, m_entry["filename"]))

        # Fuente 2: FACBs ISA — segunda fecha del período (más confiable)
        for facb in result.get("facbs", []):
            fname = facb.get("filename", "")
            if not fname:
                continue
            try:
                doc = fitz.open(os.path.join(work_dir, fname))
                text = doc[0].get_text()
                # Formato ISA: "DD-MM-YYYY / DD-MM-YYYY" — segunda fecha = sailed
                m = re.search(
                    r'\d{2}-\d{2}-\d{4}\s*/\s*(\d{2})-(\d{2})-(\d{4})', text
                )
                if m:
                    day, mon, yr = m.group(1), m.group(2), m.group(3)
                    s = f"{MONTH_MAP.get(mon, mon)} {int(day)}, {yr}"
                    sailed_candidates.append((s, fname))
            except Exception:
                continue

        # Elegir la fecha de la FACB ISA si existe (más confiable que Maritime)
        # Las FACBs tienen nombre FACB* o N_CB*
        facb_dates  = [(s, f) for s, f in sailed_candidates
                       if "FACB" in f.upper() or "N_CB" in f.upper()]
        other_dates = [(s, f) for s, f in sailed_candidates
                       if "FACB" not in f.upper() and "N_CB" not in f.upper()]

        if facb_dates:
            result["sailed"] = facb_dates[0][0]
        elif other_dates:
            # De Maritime: usar el archivo con número más alto (más reciente)
            other_dates.sort(key=lambda x: x[1], reverse=True)
            result["sailed"] = other_dates[0][0]

    # ── Ordenar FACBs: agency primero, luego ncb, luego port_expenses ────
    type_order = {"agency": 0, "ncb": 1, "port_expenses": 2}
    result["facbs"].sort(key=lambda f: (
        type_order.get(f.get("type", ""), 9),
        f.get("number", "")
    ))
    for tc in result["tc_groups"]:
        result["tc_groups"][tc].sort(
            key=lambda x: 0 if x[1] == "Agency fee"
                         else (1 if "crédito" in x[1] else 2)
        )

    result["consorcio"].sort()
    result["donmar"].sort()
    result["puerto_mariel"].sort()

    return result
