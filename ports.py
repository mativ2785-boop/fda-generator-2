"""
ports.py — ISA FDA Generator
Version: 3.0 (Jun 2026) — REESCRITURA COMPLETA

PRINCIPIO FUNDAMENTAL:
  Las FACBs ISA son la fuente de verdad del orden y cantidad de vouchers.
  Cada línea de la FACB → 1 voucher ISA + 1 comprobante de proveedor.
  El orden de los vouchers = el orden de las líneas en las FACBs.
  Los TCs se ordenan de mayor a menor (descendente).

  AGENCY FEE tiene su FACB pero NO genera voucher en el cuerpo del FDA.
  TAX ON CREDIT/DEBIT LAW 25.413 genera voucher pero sin comprobante.
"""

import os, re


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS COMPARTIDOS
# ══════════════════════════════════════════════════════════════════════════════

def _build_with_extra_taxes(base_result, entries):
    """Inserta Tax extras (claves _TC{n}) después del último voucher de su TC."""
    extra_taxes = {
        entry["tc"]: entry
        for k, entry in entries.items()
        if "_TC" in k and k.startswith("TAX ON CREDIT/DEBIT LAW 25.413")
    }
    if not extra_taxes:
        return base_result
    final, inserted = [], set()
    for idx, entry in enumerate(base_result):
        final.append(entry)
        tc = entry.get("tc", 0)
        if tc in extra_taxes and tc not in inserted:
            remaining = [e for e in base_result[idx+1:] if e.get("tc", 0) == tc]
            if not remaining:
                final.append(extra_taxes[tc])
                inserted.add(tc)
    for tc_e, entry in sorted(extra_taxes.items()):
        if tc_e not in inserted:
            final.append(entry)
    return final


def _mar_inv_shared(analysis, exclude_mooring_img=True):
    """Construye dict voucher → [(filename, [page_indices])] desde Maritime."""
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


# ══════════════════════════════════════════════════════════════════════════════
# MAPEADOR DE CONCEPTOS → COMPROBANTES
# Dado un nombre de concepto de la FACB, retorna los archivos del proveedor.
# ══════════════════════════════════════════════════════════════════════════════

CONCEPT_ALIASES = {
    # Variantes de nombres en FACBs → nombre canónico
    "RIVER PARANA PILOTAGE ANCHORAG":      "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
    "RIVER PLATE PILOTAGE ANCHORAGE":      "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER",
    "MANDATORY HOLDS INSPECTION AT":       "MANDATORY HOLDS INSPECTION",
    "LAUNCH SERVICES FOR CLEARENCE":       "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
    "LAUNCH SERV FOR INWARD/OUTWAR":       "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
    "MOORING & UNMORING SERVICES":         "MOORING & UNMOORING SERVICES",
    "PILOT LAUNCH TRANSPORTATION RI":      "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
    "TOLL DUES":                           "TOLL DUES",   # se resuelve por TC en normalize
}



def _normalize_concept_with_context(raw_concept, tc, tc_base, analysis):
    """
    Normaliza el concepto de la FACB al nombre canónico del voucher,
    teniendo en cuenta el TC y el contexto del análisis.

    Reglas contextuales:
    - RIVER PLATE PILOTAGE en TC != base Y hay Glatil → PILOT LAUNCH
      (la FACB agrupa bajo ese nombre el costo del servicio de lancha)
    - TOLL DUES con comprobante CARP → TOLL DUES (CARP)
    - TOLL DUES con comprobante AGP  → TOLL DUES (AGP)
    - Si hay ambos CARP y AGP: el TC más bajo → AGP, el más alto → CARP
    """
    concept = normalize_concept(raw_concept)

    # RIVER PLATE PILOTAGE en TC alto con Glatil disponible → PILOT LAUNCH
    if (concept == "RIVER PLATE PILOTAGE"
            and tc > tc_base
            and analysis.get("glatil")):
        concept = "PILOT LAUNCH TRANSPORTATION RIVER PLATE"

    # TOLL DUES → distinguir AGP vs CARP
    if concept == "TOLL DUES":
        has_agp  = bool(analysis.get("agp"))
        has_carp = bool(analysis.get("carp"))
        if has_agp and has_carp:
            # Determinar qué TC corresponde a cada uno leyendo las FACBs
            # Por convención ISA: el TC más bajo → AGP, el más alto → CARP
            toll_tcs = sorted(
                f["tc"] for f in analysis.get("facbs", [])
                if f.get("type") == "port_expenses" and f.get("tc")
            )
            if toll_tcs and tc == min(toll_tcs):
                concept = "TOLL DUES (AGP)"
            else:
                concept = "TOLL DUES (CARP)"
        elif has_agp:
            concept = "TOLL DUES (AGP)"
        elif has_carp:
            concept = "TOLL DUES (CARP)"

    return concept


def normalize_concept(raw):
    """Normaliza el nombre del concepto de la FACB al nombre canónico del voucher."""
    k = raw.upper().strip().replace("PRACTIQUE", "PRATIQUE")
    return CONCEPT_ALIASES.get(k, k)


def _get_invoices_for_concept(concept_canonical, analysis, work_dir, mar_pages):
    """
    Retorna [(filename, pages_or_None)] para el comprobante que corresponde
    al concepto dado. Reglas:
    - TAX, AGENCY FEE → sin comprobante
    - PILOT LAUNCH → Glatil USD 4,440 únicamente
    - TOLL DUES → AGP o CARP según TC
    - RIVER PLATE PILOTAGE → Ripla (solo p1 de cada archivo)
    - RIVER PARANA PILOTAGE → Multipar/COPRAC/River Pilot (todos, maniobra o no)
    - RIVER PARANA PILOTAGE ANCHORAGE MANEUVER → solo Multipar con maniobra
    - PORT PILOTAGE → COOP Practicos del Parana
    - LAUNCH SERVICES FOR CLEARANCE → Gente de Rio is_clearance=True
    - MOORING → Plate Amarres + Gente de Rio is_mooring=True
    - PORT DUES → Terminal portuario
    - ENTRANCE AND LIGHT DUES → ENAPRO (páginas de Maritime)
    - CUSTOM HOUSE EXPENSES → Centro Nav + Maritime AFIP/SSEE
    - COAST GUARD EXPENSES → páginas de Maritime (SSEE permanencia)
    - MIGRATION EXPENSES / MIGRATION EXPENSES - OUTWARD → Maritime Migration
    - GARBAGE → Maritime SENASA
    - MANDATORY HOLDS → Maritime compulsory_insp
    - HEADCLERK → Maritime headclerk
    - SANITARY → Maritime sanitary
    """
    c = concept_canonical

    # Sin comprobante
    if "TAX ON CREDIT/DEBIT" in c or "AGENCY FEE" in c:
        return []

    # PILOT LAUNCH — solo Glatil USD 4,440 (excluir 5,234.80 y 6,154.80)
    if "PILOT LAUNCH" in c:
        inv = []
        for fname in analysis.get("glatil", []):
            try:
                import fitz as _fz
                text = "".join(pg.get_text()
                               for pg in _fz.open(os.path.join(work_dir, fname)))
                # Detectar montos inválidos en cualquier formato numérico
                # Formato UY: "6.154,80" o "6.154,00" o texto "6.15" truncado
                # Formato AR: "6,154.80"
                invalid = (
                    "5,234" in text or "5.234" in text or
                    "6,154" in text or "6.154" in text or
                    "6.15" in text   # formato truncado UY
                )
                # Confirmar que tiene 4,440
                valid = "4,440" in text or "4.440" in text
                if invalid and not valid:
                    print(f"  ⚠ Glatil excluido: {fname}")
                    continue
            except Exception:
                pass
            inv.append((fname, None))
        return inv

    # TOLL DUES → AGP
    if c in ("TOLL DUES", "TOLL DUES (AGP)"):
        return [(f, None) for f in analysis.get("agp", [])]

    # TOLL DUES (CARP)
    if c == "TOLL DUES (CARP)":
        return [(f, None) for f in analysis.get("carp", [])]

    # PORT DUES → terminal portuario
    if c == "PORT DUES":
        return [(f, None) for f in analysis.get("terminal_portuario", [])]

    # ENTRANCE AND LIGHT DUES → ENAPRO de Maritime
    if c == "ENTRANCE AND LIGHT DUES":
        return mar_pages.get("ENTRANCE AND LIGHT DUES", [])

    # RIVER PLATE PILOTAGE → Ripla, solo p1
    if c == "RIVER PLATE PILOTAGE":
        return [(r["filename"], [0]) for r in analysis.get("practicaje_rp", [])]

    # RIVER PLATE DELAY → Ripla con demora
    if c == "RIVER PLATE PILOTAGE (DELAY)":
        return [(r["filename"], [0]) for r in analysis.get("practicaje_rp", [])
                if r.get("has_demora")]

    # RIVER PLATE ANCHORAGE → Ripla con maniobra
    if c == "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER":
        return [(r["filename"], [0]) for r in analysis.get("practicaje_rp", [])
                if r.get("has_maniobra") and r.get("maniobra_amount", 0) > 0]

    # RIVER PARANA PILOTAGE → todos los Multipar/COPRAC/River Pilot
    if c == "RIVER PARANA PILOTAGE":
        return [(r["filename"], None) for r in analysis.get("coprac", [])]

    # RIVER PARANA DELAY
    if c == "RIVER PARANA PILOTAGE (DELAY)":
        return [(r["filename"], None) for r in analysis.get("coprac", [])
                if r.get("has_demora")]

    # RIVER PARANA ANCHORAGE → solo con maniobra real
    if c == "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER":
        return [(r["filename"], None) for r in analysis.get("coprac", [])
                if r.get("has_maniobra") and r.get("maniobra_amount", 0) > 0]

    # PORT PILOTAGE → Coop Practicos del Parana (Rosario Pilots)
    if c == "PORT PILOTAGE":
        return [(r["filename"], None) for r in analysis.get("rosario_pilots", [])]

    if c == "PORT PILOTAGE (DELAY)":
        return [(r["filename"], None) for r in analysis.get("rosario_pilots", [])
                if r.get("has_demora")]

    # LAUNCH SERVICES FOR CLEARANCE → facturas con is_clearance=True
    if "LAUNCH SERVICES" in c and "ZONA" not in c:
        return [(r["filename"], None) for r in analysis.get("amarre_coral", [])
                if r.get("is_clearance")]

    # LAUNCH SERVICES AT ZONA COMUN → Lanchas del Este
    if "ZONA COMUN" in c:
        return [(r["filename"], None) for r in analysis.get("amarre_coral", [])
                if "LANCHAS DEL ESTE" in r["filename"].upper()]

    # MOORING & UNMOORING → facturas con is_mooring=True
    if "MOORING" in c and "ANCHORAGE" not in c:
        inv  = [(r["filename"], None) for r in analysis.get("amarre_coral", [])
                if r.get("is_mooring")]
        inv += mar_pages.get("MOORING & UNMOORING SERVICES", [])
        return inv

    # CUSTOM HOUSE EXPENSES → Centro Nav + páginas afip_lman de Maritime (incluyendo imágenes)
    if c == "CUSTOM HOUSE EXPENSES":
        nav = [(f, None) for f in analysis.get("centro_nav", [])]
        mar_ch = mar_pages.get("CUSTOM HOUSE EXPENSES", [])
        return nav + mar_ch

    # CUSTOM HOUSE PERMANENCE
    if c == "CUSTOM HOUSE PERMANENCE":
        return mar_pages.get("CUSTOM HOUSE PERMANENCE", [])

    # CUSTOM HOUSE EXPENSE (CARGO)
    if "CARGO" in c and "CUSTOM HOUSE" in c:
        return mar_pages.get("CUSTOM HOUSE EXPENSE (CARGO)", [])

    # COAST GUARD EXPENSES → páginas de Maritime clasificadas como coast_guard
    if "COAST GUARD" in c:
        return mar_pages.get("COAST GUARD EXPENSES", [])

    # MIGRATION EXPENSES y variantes
    if "MIGRATION" in c:
        return mar_pages.get("MIGRATION EXPENSES", [])

    # SANITARY
    if "SANITARY" in c or "PRATIQUE" in c or "PRACTIQUE" in c:
        return mar_pages.get("SANITARY DUES AND FREE PRATIQUE", [])

    # GARBAGE
    if "GARBAGE" in c:
        return mar_pages.get("GARBAGE COMPULSORY INSPECTION", [])

    # MANDATORY HOLDS INSPECTION (no reinspection)
    if "MANDATORY HOLDS" in c and "RE" not in c:
        ext = [(f, None) for f in analysis.get("mandatory_insp_ext", [])]
        mar = mar_pages.get("MANDATORY HOLDS INSPECTION", [])
        return mar + ext

    # MANDATORY HOLDS RE-INSPECTION
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
        inv = mar_pages.get("PEST CONTROL", [])
        inv += [(f, None) for f in analysis.get("ammoca", [])]
        return inv

    # OSRO
    if "OSRO" in c:
        return mar_pages.get("OSRO ANNEX 18", [])

    # Towage
    if "TOWAGE" in c:
        inv = [(f, None) for f in analysis.get("puerto_mariel", [])]
        inv += [(f, None) for f in analysis.get("towage_sl", [])]
        return inv

    return []


# ══════════════════════════════════════════════════════════════════════════════
# CLASE BASE PARA TODOS LOS PUERTOS
# ══════════════════════════════════════════════════════════════════════════════

class PortBase:
    name       = ""
    short_name = ""

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type") == "agency"),
                    keys[0] if keys else 1366.5)

    def _tc_port_min(self, a):
        tcs = [f["tc"] for f in a["facbs"]
               if f.get("type") == "port_expenses" and f.get("tc")]
        return min(tcs) if tcs else self._tc_agency(a)


# ══════════════════════════════════════════════════════════════════════════════
# SAN LORENZO / ARROYO SECO / GRAL. LAGOS
# ══════════════════════════════════════════════════════════════════════════════

class SanLorenzoPort(PortBase):
    name       = "San Lorenzo Port"
    short_name = "SAN LORENZO"

    def build_invoice_map(self, analysis, work_dir, line_amounts=None):
        """
        LÓGICA NUEVA:
        1. Lee cada FACB port_expenses en orden de TC descendente.
        2. Por cada línea de la FACB, crea un entry de voucher.
        3. Busca el comprobante de proveedor correspondiente.
        4. El orden = orden de las líneas en las FACBs.

        line_amounts se ignora — se usa directamente de las FACBs.
        """
        from assembler import extract_facb_line_amounts

        mar_pages = _mar_inv_shared(analysis)

        # Ordenar FACBs: TC descendente, dentro de cada TC agency→port_exp
        facbs_sorted = sorted(
            [f for f in analysis.get("facbs", [])
             if f.get("type") == "port_expenses" and f.get("tc") and f.get("filename")],
            key=lambda f: -f["tc"]   # descendente
        )

        # TC base = el TC más bajo de las FACBs port_expenses
        tc_base = min((f["tc"] for f in facbs_sorted), default=0)

        result = []

        for facb in facbs_sorted:
            tc       = facb["tc"]
            fpath    = os.path.join(work_dir, facb["filename"])
            if not os.path.exists(fpath):
                continue

            la = extract_facb_line_amounts(fpath)

            for raw_concept, amount in la.items():
                if amount <= 0:
                    continue

                # Normalización contextual: usa tc, tc_base y analysis
                concept = _normalize_concept_with_context(
                    raw_concept, tc, tc_base, analysis
                )

                # AGENCY FEE: no genera voucher en el cuerpo
                if "AGENCY FEE" in concept:
                    continue

                # Buscar comprobante
                invoices = _get_invoices_for_concept(
                    concept, analysis, work_dir, mar_pages
                )

                result.append({
                    "concept":  concept,
                    "amount":   amount,
                    "tc":       tc,
                    "invoices": invoices,
                })

        return result


# ══════════════════════════════════════════════════════════════════════════════
# BAHIA BLANCA
# ══════════════════════════════════════════════════════════════════════════════

class BahiaBlancaPort(PortBase):
    name       = "Bahia Blanca Port"
    short_name = "BAHIA BLANCA"

    def build_invoice_map(self, analysis, work_dir, line_amounts=None):
        from assembler import extract_facb_line_amounts

        mar_pages = _mar_inv_shared(analysis)

        facbs_sorted = sorted(
            [f for f in analysis.get("facbs", [])
             if f.get("type") == "port_expenses" and f.get("tc") and f.get("filename")],
            key=lambda f: -f["tc"]
        )

        tc_base = min((f["tc"] for f in facbs_sorted), default=0)
        result = []
        for facb in facbs_sorted:
            tc    = facb["tc"]
            fpath = os.path.join(work_dir, facb["filename"])
            if not os.path.exists(fpath):
                continue
            la = extract_facb_line_amounts(fpath)
            for raw_concept, amount in la.items():
                if amount <= 0:
                    continue
                concept = _normalize_concept_with_context(
                    raw_concept, tc, tc_base, analysis
                )
                if "AGENCY FEE" in concept:
                    continue
                invoices = _get_invoices_for_concept(
                    concept, analysis, work_dir, mar_pages
                )
                result.append({
                    "concept":  concept,
                    "amount":   amount,
                    "tc":       tc,
                    "invoices": invoices,
                })
        return result


# ══════════════════════════════════════════════════════════════════════════════
# NECOCHEA
# ══════════════════════════════════════════════════════════════════════════════

class NecocheaPort(PortBase):
    name       = "Necochea Port"
    short_name = "NECOCHEA"

    def build_invoice_map(self, analysis, work_dir, line_amounts=None):
        from assembler import extract_facb_line_amounts

        mar_pages = _mar_inv_shared(analysis)

        facbs_sorted = sorted(
            [f for f in analysis.get("facbs", [])
             if f.get("type") == "port_expenses" and f.get("tc") and f.get("filename")],
            key=lambda f: -f["tc"]
        )

        tc_base = min((f["tc"] for f in facbs_sorted), default=0)
        result = []
        for facb in facbs_sorted:
            tc    = facb["tc"]
            fpath = os.path.join(work_dir, facb["filename"])
            if not os.path.exists(fpath):
                continue
            la = extract_facb_line_amounts(fpath)
            for raw_concept, amount in la.items():
                if amount <= 0:
                    continue
                concept = _normalize_concept_with_context(
                    raw_concept, tc, tc_base, analysis
                )
                if "AGENCY FEE" in concept:
                    continue
                invoices = _get_invoices_for_concept(
                    concept, analysis, work_dir, mar_pages
                )
                result.append({
                    "concept":  concept,
                    "amount":   amount,
                    "tc":       tc,
                    "invoices": invoices,
                })
        return result


# ══════════════════════════════════════════════════════════════════════════════
# DETECCIÓN DE PUERTO
# ══════════════════════════════════════════════════════════════════════════════

def detect_port(analysis):
    port_str = (analysis.get("port") or "").upper()
    if "NECOCHEA" in port_str or "QUEQUEN" in port_str:
        return NecocheaPort()
    if "BAHIA BLANCA" in port_str or "BAHÍA BLANCA" in port_str:
        return BahiaBlancaPort()
    if any(p in port_str for p in ("SAN LORENZO","ARROYO SECO","GRAL. LAGOS")):
        return SanLorenzoPort()
    if analysis.get("consorcio_quequen") or analysis.get("melluso") or analysis.get("pilotaje"):
        return NecocheaPort()
    if (analysis.get("practicaje_rp") or analysis.get("coprac") or
            analysis.get("rosario_pilots") or analysis.get("terminal_portuario")):
        return SanLorenzoPort()
    return BahiaBlancaPort()
