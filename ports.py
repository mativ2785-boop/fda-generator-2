"""
ports.py — ISA FDA Generator v3.3 (Jun 2026)

PRINCIPIO FUNDAMENTAL:
  Las FACBs ISA son la fuente de verdad del orden y cantidad de vouchers.
  Cada línea de la FACB → 1 voucher ISA + 1 comprobante de proveedor.
"""

import os, re as _re


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _mar_inv_shared(analysis, exclude_mooring_img=True):
    mar_pages = {}
    for m in analysis.get("maritime", []):
        for pg in m["pages"]:
            v   = pg.get("voucher")
            cat = pg.get("category", "")
            if exclude_mooring_img and cat == "mooring_img":
                continue
            if v:
                mar_pages.setdefault(v, []).append((m["filename"], pg["page"]))
    result = {}
    for v, pairs in mar_pages.items():
        merged = {}
        for fname, pg in pairs:
            merged.setdefault(fname, []).append(pg)
        result[v] = [(f, sorted(set(pgs))) for f, pgs in merged.items()]
    return result


def _only_original(fname, work_dir):
    """
    Para archivos con más de 1 página, retorna solo las páginas útiles:
    - Si tiene DUPLICADO/TRIPLICADO en el texto → solo p0
    - Si todas las páginas son idénticas → solo p0 (COPRAC LASKARO)
    - Si p1 dice ORIGINAL y p2+ son imágenes sin texto → solo p0
    - Sino → incluir todo (None)
    """
    try:
        import fitz as _fz
        doc = _fz.open(os.path.join(work_dir, fname))
        if doc.page_count <= 1:
            return None
        texts = [doc[i].get_text() for i in range(doc.page_count)]
        text_all = "".join(texts).upper()
        # Flag explícito de duplicado
        if "DUPLICADO" in text_all or "TRIPLICADO" in text_all:
            return [0]
        # Páginas completamente idénticas
        if len(set(texts)) == 1:
            return [0]
        # p1 tiene ORIGINAL y p2+ son imágenes sin texto
        if "ORIGINAL" in texts[0].upper():
            rest_are_images = all(not texts[i].strip() for i in range(1, doc.page_count))
            if rest_are_images:
                return [0]
        return None
    except Exception:
        return None


def _dedup_by_invoice_number(file_list, work_dir):
    """
    Deduplica por número de factura. Si dos archivos tienen el mismo número → solo el primero.
    También aplica _only_original a cada archivo.
    """
    import fitz as _fz

    seen_numbers = set()
    result = []

    for fname, pages in file_list:
        fpath = os.path.join(work_dir, fname)
        try:
            doc = _fz.open(fpath)
            text_all = "".join(pg.get_text() for pg in doc).upper()

            # Aplicar _only_original
            if pages is None:
                pages = _only_original(fname, work_dir)

            # Extraer número de factura
            p0_text = doc[0].get_text()
            num_match = _re.search(
                r'(?:CÓD|COD|NRO|N°|Nro\.?)\s*[\s:]*([\w][\w\-/]+[\d]{4,})'
                r'|(\d{4}-\d{4,})'
                r'|(B-\d{5}-\d{6,})'
                r'|(\d{3}-\d{5}-\d{5,})',
                p0_text, _re.IGNORECASE
            )
            if num_match:
                inv_num = next(g for g in num_match.groups() if g)
                inv_key = _re.sub(r'[\s\-]', '', inv_num).upper()
                if inv_key in seen_numbers:
                    continue
                seen_numbers.add(inv_key)

            result.append((fname, pages))
        except Exception:
            result.append((fname, pages))

    return result


# ══════════════════════════════════════════════════════════════════════════════
# ORDENAMIENTO DE FACBs POR CONTENIDO
# ══════════════════════════════════════════════════════════════════════════════

def _facb_sort_key(facb_dict, analysis):
    """
    Orden de las FACBs en el FDA:
      grupo 0 — gastos de puerto base (PORT DUES, ENTRANCE, PILOTAJE, etc.)
      grupo 1 — TOLL DUES (CARP) y/o PILOT LAUNCH (Glatil)
      grupo 2 — TOLL DUES (AGP) — siempre el último
    """
    from assembler import extract_facb_line_amounts

    fpath = facb_dict.get("_fpath", "")
    try:
        la = extract_facb_line_amounts(fpath) if fpath and os.path.exists(fpath) else {}
    except Exception:
        la = {}

    keys_up   = [k.upper() for k in la.keys()]
    has_port  = any("PORT DUES"    in k for k in keys_up)
    has_entr  = any("ENTRANCE"     in k for k in keys_up)
    has_pilot = any("PILOT LAUNCH" in k for k in keys_up)
    has_toll  = any("TOLL DUES"    in k for k in keys_up)
    has_rp    = any("RIVER PLATE PILOTAGE" in k for k in keys_up)
    has_glatil = bool(analysis.get("glatil"))
    has_agp    = bool(analysis.get("agp"))
    has_carp   = bool(analysis.get("carp"))
    num        = facb_dict.get("number", "")

    if has_port or has_entr:
        return (0, num)
    if has_pilot:
        return (1, num)
    tc_base = min(
        (f["tc"] for f in analysis.get("facbs", [])
         if f.get("type") == "port_expenses" and f.get("tc")),
        default=0
    )
    if has_rp and facb_dict.get("tc", 0) > tc_base and has_glatil:
        return (1, num)
    if has_toll:
        # Si hay ambos AGP y CARP: TC mínimo → AGP (último), resto → CARP (grupo 1)
        if has_agp and has_carp:
            tc = facb_dict.get("tc", 0)
            if tc == tc_base:
                return (2, num)
            else:
                return (1, num)
        if has_agp and not has_carp:
            return (2, num)   # solo AGP → último
        return (1, num)       # CARP o desconocido → grupo 1
    return (0, num)


# ══════════════════════════════════════════════════════════════════════════════
# NORMALIZACIÓN CONTEXTUAL DE CONCEPTOS
# ══════════════════════════════════════════════════════════════════════════════

CONCEPT_ALIASES = {
    "RIVER PARANA PILOTAGE ANCHORAG":  "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
    "RIVER PLATE PILOTAGE ANCHORAGE":  "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER",
    "MANDATORY HOLDS INSPECTION AT":   "MANDATORY HOLDS INSPECTION",
    "LAUNCH SERVICES FOR CLEARENCE":   "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
    "LAUNCH SERV FOR INWARD/OUTWAR":   "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
    "MOORING & UNMORING SERVICES":     "MOORING & UNMOORING SERVICES",
    "PILOT LAUNCH TRANSPORTATION RI":  "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
    "TOLL DUES":                       "TOLL DUES",
}


def normalize_concept(raw):
    k = raw.upper().strip().replace("PRACTIQUE", "PRATIQUE")
    return CONCEPT_ALIASES.get(k, k)


def _normalize_concept_with_context(raw_concept, tc, tc_base, analysis):
    """
    Normaliza concepto FACB al nombre de voucher con contexto.
    - RIVER PLATE PILOTAGE en TC alto + Glatil → PILOT LAUNCH
    - TOLL DUES → TOLL DUES (CARP) o TOLL DUES (AGP) según comprobantes
    """
    concept = normalize_concept(raw_concept)

    if (concept == "RIVER PLATE PILOTAGE"
            and tc > tc_base
            and analysis.get("glatil")):
        concept = "PILOT LAUNCH TRANSPORTATION RIVER PLATE"

    if concept == "TOLL DUES":
        has_agp  = bool(analysis.get("agp"))
        has_carp = bool(analysis.get("carp"))
        if has_agp and has_carp:
            # TC mínimo → AGP; resto → CARP
            toll_tcs = sorted(
                f["tc"] for f in analysis.get("facbs", [])
                if f.get("type") == "port_expenses" and f.get("tc")
            )
            concept = "TOLL DUES (AGP)" if (toll_tcs and tc == min(toll_tcs)) else "TOLL DUES (CARP)"
        elif has_agp:
            concept = "TOLL DUES (AGP)"
        elif has_carp:
            concept = "TOLL DUES (CARP)"
        # Si no hay ni AGP ni CARP: dejar como TOLL DUES genérico
        # El comprobante se resolverá por el contexto

    return concept


# ══════════════════════════════════════════════════════════════════════════════
# MAPEADOR CONCEPTO → COMPROBANTE DE PROVEEDOR
# ══════════════════════════════════════════════════════════════════════════════

def _get_invoices_for_concept(concept_canonical, analysis, work_dir, mar_pages):
    """Retorna [(filename, pages_or_None)] para el comprobante del concepto."""
    c = concept_canonical

    # Sin comprobante
    if "TAX ON CREDIT/DEBIT" in c or "AGENCY FEE" in c:
        return []

    # PILOT LAUNCH — solo Glatil USD 4,440
    if "PILOT LAUNCH" in c:
        inv = []
        for fname in analysis.get("glatil", []):
            try:
                import fitz as _fz
                text = "".join(pg.get_text()
                               for pg in _fz.open(os.path.join(work_dir, fname)))
                invalid = ("5,234" in text or "5.234" in text or
                           "6,154" in text or "6.154" in text or "6.15" in text)
                valid   = "4,440" in text or "4.440" in text
                if invalid and not valid:
                    print(f"  ⚠ Glatil excluido: {fname}")
                    continue
            except Exception:
                pass
            inv.append((fname, None))
        return inv

    # TOLL DUES — AGP o CARP según lo que haya disponible
    if c in ("TOLL DUES", "TOLL DUES (AGP)"):
        agp = [(f, None) for f in analysis.get("agp", [])]
        if agp:
            return agp
        # Si no hay AGP, intentar con CARP como fallback
        return [(f, None) for f in analysis.get("carp", [])]

    if c == "TOLL DUES (CARP)":
        carp = [(f, None) for f in analysis.get("carp", [])]
        if carp:
            return carp
        # Fallback a AGP si no hay CARP
        return [(f, None) for f in analysis.get("agp", [])]

    # PORT DUES → terminal portuario
    if c == "PORT DUES":
        return [(f, _only_original(f, work_dir))
                for f in analysis.get("terminal_portuario", [])]

    # ENTRANCE AND LIGHT DUES → ENAPRO de Maritime
    if c == "ENTRANCE AND LIGHT DUES":
        return mar_pages.get("ENTRANCE AND LIGHT DUES", [])

    # RIVER PLATE PILOTAGE → Ripla p1
    if c == "RIVER PLATE PILOTAGE":
        return [(r["filename"], [0]) for r in analysis.get("practicaje_rp", [])]

    if c == "RIVER PLATE PILOTAGE (DELAY)":
        return [(r["filename"], [0]) for r in analysis.get("practicaje_rp", [])
                if r.get("has_demora")]

    if c == "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER":
        return [(r["filename"], [0]) for r in analysis.get("practicaje_rp", [])
                if r.get("has_maniobra") and r.get("maniobra_amount", 0) > 0]

    # RIVER PARANA PILOTAGE → COPRAC/Multipar — deduplicado
    if c == "RIVER PARANA PILOTAGE":
        raw = [(r["filename"], None) for r in analysis.get("coprac", [])]
        return _dedup_by_invoice_number(raw, work_dir)

    if c == "RIVER PARANA PILOTAGE (DELAY)":
        raw = [(r["filename"], None) for r in analysis.get("coprac", [])
               if r.get("has_demora")]
        return _dedup_by_invoice_number(raw, work_dir)

    if c == "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER":
        raw = [(r["filename"], None) for r in analysis.get("coprac", [])
               if r.get("has_maniobra") and r.get("maniobra_amount", 0) > 0]
        return _dedup_by_invoice_number(raw, work_dir)

    # PORT PILOTAGE → Coop Practicos del Parana — deduplicado
    if c == "PORT PILOTAGE":
        raw = [(r["filename"], None) for r in analysis.get("rosario_pilots", [])]
        return _dedup_by_invoice_number(raw, work_dir)

    if c == "PORT PILOTAGE (DELAY)":
        raw = [(r["filename"], None) for r in analysis.get("rosario_pilots", [])
               if r.get("has_demora")]
        return _dedup_by_invoice_number(raw, work_dir)

    # LAUNCH SERVICES FOR CLEARANCE — deduplicado
    if "LAUNCH SERVICES" in c and "ZONA" not in c:
        raw = [(r["filename"], _only_original(r["filename"], work_dir))
               for r in analysis.get("amarre_coral", [])
               if r.get("is_clearance")]
        return _dedup_by_invoice_number(raw, work_dir)

    # LAUNCH SERVICES AT ZONA COMUN
    if "ZONA COMUN" in c:
        return [(r["filename"], _only_original(r["filename"], work_dir))
                for r in analysis.get("amarre_coral", [])
                if "LANCHAS DEL ESTE" in r["filename"].upper()]

    # MOORING & UNMOORING — deduplicado
    if "MOORING" in c and "ANCHORAGE" not in c:
        raw  = [(r["filename"], _only_original(r["filename"], work_dir))
                for r in analysis.get("amarre_coral", [])
                if r.get("is_mooring")]
        raw += mar_pages.get("MOORING & UNMOORING SERVICES", [])
        return _dedup_by_invoice_number(raw, work_dir)

    # CUSTOM HOUSE EXPENSES → Centro Nav + Maritime
    if c == "CUSTOM HOUSE EXPENSES":
        nav = [(f, None) for f in analysis.get("centro_nav", [])]
        mar = mar_pages.get("CUSTOM HOUSE EXPENSES", [])
        return nav + mar

    if c == "CUSTOM HOUSE PERMANENCE":
        return mar_pages.get("CUSTOM HOUSE PERMANENCE", [])

    if "CARGO" in c and "CUSTOM HOUSE" in c:
        return mar_pages.get("CUSTOM HOUSE EXPENSE (CARGO)", [])

    # COAST GUARD
    if "COAST GUARD" in c:
        return mar_pages.get("COAST GUARD EXPENSES", [])

    # MIGRATION
    if "MIGRATION" in c:
        return mar_pages.get("MIGRATION EXPENSES", [])

    # SANITARY
    if "SANITARY" in c or "PRATIQUE" in c or "PRACTIQUE" in c:
        return mar_pages.get("SANITARY DUES AND FREE PRATIQUE", [])

    # GARBAGE
    if "GARBAGE" in c:
        return mar_pages.get("GARBAGE COMPULSORY INSPECTION", [])

    # MANDATORY HOLDS
    if "MANDATORY HOLDS" in c and "RE" not in c:
        ext = [(f, None) for f in analysis.get("mandatory_insp_ext", [])]
        mar = mar_pages.get("MANDATORY HOLDS INSPECTION", [])
        return mar + ext

    if "MANDATORY HOLDS" in c and "RE" in c:
        return mar_pages.get("MANDATORY HOLDS RE-INSPECTION", [])

    # HEADCLERK
    if "HEADCLERK" in c:
        return mar_pages.get("HEADCLERK COMPULSORY SERVICES", [])

    # WATCHMEN
    if "WATCHMEN" in c:
        return mar_pages.get("WATCHMEN COMPULSORY SERVICES", [])

    # FULL ON HIRE / BQS
    if "FULL ON HIRE" in c or "BQS" in c:
        return [(f, [0]) for f in analysis.get("edi_separovic", [])]

    # PEST CONTROL
    if "PEST" in c:
        inv  = mar_pages.get("PEST CONTROL", [])
        inv += [(f, None) for f in analysis.get("ammoca", [])]
        return inv

    # OSRO
    if "OSRO" in c:
        return mar_pages.get("OSRO ANNEX 18", [])

    # TOWAGE
    if "TOWAGE" in c:
        inv  = [(f, None) for f in analysis.get("puerto_mariel", [])]
        inv += [(f, None) for f in analysis.get("towage_sl", [])]
        return inv

    return []


# ══════════════════════════════════════════════════════════════════════════════
# LÓGICA COMÚN DE BUILD
# ══════════════════════════════════════════════════════════════════════════════

def _build_entries(analysis, work_dir, mar_pages):
    from assembler import extract_facb_line_amounts

    facbs_raw = [
        {**f, "_fpath": os.path.join(work_dir, f["filename"])}
        for f in analysis.get("facbs", [])
        if f.get("type") == "port_expenses" and f.get("tc") and f.get("filename")
    ]

    facbs_sorted = sorted(facbs_raw, key=lambda f: _facb_sort_key(f, analysis))

    tc_base = 0
    for f in facbs_sorted:
        if _facb_sort_key(f, analysis)[0] == 0:
            tc_base = f["tc"]
            break
    if tc_base == 0:
        tc_base = min((f["tc"] for f in facbs_sorted), default=0)

    result = []
    for facb in facbs_sorted:
        tc    = facb["tc"]
        fpath = facb.get("_fpath") or os.path.join(work_dir, facb["filename"])
        if not os.path.exists(fpath):
            continue

        la = extract_facb_line_amounts(fpath)
        for raw_concept, amount in la.items():
            if amount <= 0:
                continue
            concept = _normalize_concept_with_context(raw_concept, tc, tc_base, analysis)
            if "AGENCY FEE" in concept:
                continue
            invoices = _get_invoices_for_concept(concept, analysis, work_dir, mar_pages)
            result.append({
                "concept":  concept,
                "amount":   amount,
                "tc":       tc,
                "invoices": invoices,
            })

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CLASES DE PUERTO
# ══════════════════════════════════════════════════════════════════════════════

class PortBase:
    name       = ""
    short_name = ""

    def build_invoice_map(self, analysis, work_dir, line_amounts=None):
        mar_pages = _mar_inv_shared(analysis)
        return _build_entries(analysis, work_dir, mar_pages)


class SanLorenzoPort(PortBase):
    name       = "San Lorenzo Port"
    short_name = "SAN LORENZO"


class BahiaBlancaPort(PortBase):
    name       = "Bahia Blanca Port"
    short_name = "BAHIA BLANCA"


class NecocheaPort(PortBase):
    name       = "Necochea Port"
    short_name = "NECOCHEA"


def detect_port(analysis):
    port_str = (analysis.get("port") or "").upper()
    if "NECOCHEA" in port_str or "QUEQUEN" in port_str:
        return NecocheaPort()
    if "BAHIA BLANCA" in port_str or "BAHÍA BLANCA" in port_str:
        return BahiaBlancaPort()
    if any(p in port_str for p in ("SAN LORENZO", "ARROYO SECO", "GRAL. LAGOS")):
        return SanLorenzoPort()
    if analysis.get("consorcio_quequen") or analysis.get("melluso") or analysis.get("pilotaje"):
        return NecocheaPort()
    if (analysis.get("practicaje_rp") or analysis.get("coprac") or
            analysis.get("rosario_pilots") or analysis.get("terminal_portuario")):
        return SanLorenzoPort()
    return BahiaBlancaPort()
