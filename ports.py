"""
ports.py — Configuración multi-puerto para FDA Generator ISA
Version: 2.0 (Jun 2026)

Cambios respecto a v1:
- VOUCHER_ORDER de SanLorenzoPort corregido: el orden de los últimos
  tres vouchers ahora es Tax → Toll CARP → Pilot Launch → Toll AGP
  (conforme al manual ISA: §3 orden de vouchers San Lorenzo)
- Bloque de inserción de Tax extras refactorizado en método _build_with_extra_taxes()
  compartido entre los tres puertos (sin duplicación de código)
- _tc_for_concept: sin cambios funcionales
"""

import os


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS COMPARTIDOS
# ══════════════════════════════════════════════════════════════════════════════

def _build_with_extra_taxes(base_result, entries):
    """
    Inserta Tax extras (claves con sufijo _TC{n}) inmediatamente después
    del último voucher que comparte su TC en base_result.
    Retorna la lista final con los Tax extras correctamente posicionados.
    """
    extra_taxes = {
        entry["tc"]: entry
        for k, entry in entries.items()
        if "_TC" in k and k.startswith("TAX ON CREDIT/DEBIT LAW 25.413")
    }
    if not extra_taxes:
        return base_result

    final_result       = []
    inserted_tax_tcs   = set()

    for idx, entry in enumerate(base_result):
        final_result.append(entry)
        tc = entry.get("tc", 0)
        if tc in extra_taxes and tc not in inserted_tax_tcs:
            # ¿Este es el último voucher de este TC?
            remaining_same_tc = [e for e in base_result[idx+1:] if e.get("tc", 0) == tc]
            if not remaining_same_tc:
                final_result.append(extra_taxes[tc])
                inserted_tax_tcs.add(tc)

    # Agregar Tax extras no insertados (edge case)
    for tc_e, entry in sorted(extra_taxes.items()):
        if tc_e not in inserted_tax_tcs:
            final_result.append(entry)

    return final_result


def _mar_inv_shared(analysis, exclude_mooring_img=True):
    """Construye el dict voucher → [(filename, [page_indices])] desde Maritime."""
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
# BAHIA BLANCA
# ══════════════════════════════════════════════════════════════════════════════

class BahiaBlancaPort:
    name       = "Bahia Blanca Port"
    short_name = "BAHIA BLANCA"

    VOUCHER_ORDER = [
        "AGENCY FEE", "PORT DUES", "PERMANENCE DUES", "TOLL DUES",
        "PORT PILOTAGE", "PORT PILOTAGE (DELAY)",
        "MOORING & UNMOORING SERVICES",
        "TOWAGE SERVICES",
        "CUSTOM HOUSE EXPENSES", "CUSTOM HOUSE PERMANENCE",
        "CUSTOM HOUSE (BUNKERING)",
        "MIGRATION EXPENSES", "SANITARY DUES AND FREE PRATIQUE",
        "GARBAGE COMPULSORY INSPECTION",
        "WATCHMEN COMPULSORY SERVICES",
        "HEADCLERK COMPULSORY SERVICES",
        "PEST CONTROL", "OSRO ANNEX 18",
        "TAX ON CREDIT/DEBIT LAW 25.413",
    ]

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        la = {k.upper().replace("PRACTIQUE","PRATIQUE"): v
              for k, v in line_amounts.items()}
        def amt(k): return la.get(k.upper(), 0)

        tc_a = self._tc_agency(analysis)
        tc_p = self._tc_port(analysis)
        mar  = _mar_inv_shared(analysis)
        entries = {}

        entries["AGENCY FEE"] = {
            "concept": "AGENCY FEE",
            "amount":  next((f.get("total",0) for f in analysis["facbs"]
                             if f.get("type") == "agency"), 0),
            "tc": tc_a, "invoices": [], "solo": True
        }
        if analysis.get("consorcio"):
            entries["PORT DUES"] = {
                "concept":"PORT DUES", "amount": amt("PORT DUES"),
                "tc": tc_p, "invoices": [(analysis["consorcio"][0], None)]
            }
            entries["TOLL DUES"] = {
                "concept":"TOLL DUES", "amount": amt("TOLL DUES"),
                "tc": tc_p, "invoices": [(f, None) for f in analysis["consorcio"]]
            }
        if analysis.get("donmar"):
            entries["PORT PILOTAGE"] = {
                "concept":"PORT PILOTAGE", "amount": amt("PORT PILOTAGE"),
                "tc": tc_p, "invoices": [(f,None) for f in analysis["donmar"]]
            }
        mooring = (mar.get("MOORING & UNMOORING SERVICES",[]) +
                   [(f,None) for f in analysis.get("amarradores",[])])
        if mooring and amt("MOORING & UNMOORING SERVICES") > 0:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept":"MOORING & UNMOORING SERVICES",
                "amount": amt("MOORING & UNMOORING SERVICES"),
                "tc": tc_p, "invoices": mooring
            }
        if analysis.get("puerto_mariel") and amt("TOWAGE SERVICES") > 0:
            entries["TOWAGE SERVICES"] = {
                "concept":"TOWAGE SERVICES", "amount": amt("TOWAGE SERVICES"),
                "tc": tc_p, "invoices": [(f,None) for f in analysis["puerto_mariel"]]
            }
        for v in ["CUSTOM HOUSE EXPENSES","CUSTOM HOUSE PERMANENCE",
                  "CUSTOM HOUSE (BUNKERING)","MIGRATION EXPENSES",
                  "SANITARY DUES AND FREE PRATIQUE","GARBAGE COMPULSORY INSPECTION",
                  "WATCHMEN COMPULSORY SERVICES","HEADCLERK COMPULSORY SERVICES"]:
            inv = mar.get(v,[])
            if inv and amt(v) > 0:
                entries[v] = {"concept":v,"amount":amt(v),"tc":tc_p,"invoices":inv}
        pest = mar.get("PEST CONTROL",[]) + [(f,None) for f in analysis.get("ammoca",[])]
        if pest:
            entries["PEST CONTROL"] = {
                "concept":"PEST CONTROL","amount":amt("PEST CONTROL"),
                "tc":tc_p,"invoices":pest
            }
        osro = mar.get("OSRO ANNEX 18",[])
        if osro:
            entries["OSRO ANNEX 18"] = {
                "concept":"OSRO ANNEX 18","amount":amt("OSRO ANNEX 18"),
                "tc":tc_p,"invoices":osro
            }
        if amt("TAX ON CREDIT/DEBIT LAW 25.413") > 0:
            entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
                "concept":"TAX ON CREDIT/DEBIT LAW 25.413",
                "amount":amt("TAX ON CREDIT/DEBIT LAW 25.413"),
                "tc":tc_p,"invoices":[],"solo":True
            }
        for concept, amount in la.items():
            if concept not in entries and amount > 0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept":concept,"amount":amount,"tc":tc_p,"invoices":[]}

        base = [entries[v] for v in self.VOUCHER_ORDER if v in entries]
        return _build_with_extra_taxes(base, entries)

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="agency"),
                    keys[0] if keys else 1373.5)

    def _tc_port(self, a):
        tcs = [f["tc"] for f in a["facbs"]
               if f.get("type")=="port_expenses" and f.get("tc")]
        return min(tcs) if tcs else self._tc_agency(a)


# ══════════════════════════════════════════════════════════════════════════════
# NECOCHEA
# ══════════════════════════════════════════════════════════════════════════════

class NecocheaPort:
    name       = "Necochea Port"
    short_name = "NECOCHEA"

    VOUCHER_ORDER = [
        "AGENCY FEE", "PORT DUES", "ENTRANCE AND LIGHT DUES", "TOLL DUES",
        "PORT PILOTAGE", "PORT PILOTAGE (DELAY)",
        "MOORING & UNMOORING SERVICES",
        "SHORE GANGWAY", "TOWAGE SERVICES",
        "CUSTOM HOUSE EXPENSES", "CUSTOM HOUSE PERMANENCE",
        "MIGRATION EXPENSES", "SANITARY DUES AND FREE PRATIQUE",
        "GARBAGE COMPULSORY INSPECTION",
        "WATCHMEN COMPULSORY SERVICES",
        "HEADCLERK COMPULSORY SERVICES",
        "PEST CONTROL",
        "TAX ON CREDIT/DEBIT LAW 25.413",
    ]

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        la = {k.upper().replace("PRACTIQUE","PRATIQUE"): v
              for k, v in line_amounts.items()}
        def amt(k): return la.get(k.upper(), 0)

        tc_a = self._tc_agency(analysis)
        tc_p = self._tc_port(analysis)
        mar  = _mar_inv_shared(analysis)
        entries = {}

        entries["AGENCY FEE"] = {
            "concept":"AGENCY FEE",
            "amount": next((f.get("total",0) for f in analysis["facbs"]
                            if f.get("type")=="agency"), 0),
            "tc":tc_a,"invoices":[],"solo":True
        }
        consorcio = analysis.get("consorcio_quequen") or analysis.get("consorcio",[])
        if consorcio:
            entries["PORT DUES"] = {
                "concept":"PORT DUES","amount":amt("PORT DUES"),
                "tc":tc_p,"invoices":[(consorcio[0],None)]
            }
            el_inv = [(consorcio[1],None)] if len(consorcio)>=2 else [(consorcio[0],None)]
            entries["ENTRANCE AND LIGHT DUES"] = {
                "concept":"ENTRANCE AND LIGHT DUES",
                "amount":amt("ENTRANCE AND LIGHT DUES"),
                "tc":tc_p,"invoices":el_inv
            }
            toll_inv = consorcio[2:] if len(consorcio)>2 else consorcio
            entries["TOLL DUES"] = {
                "concept":"TOLL DUES","amount":amt("TOLL DUES"),
                "tc":tc_p,"invoices":[(f,None) for f in toll_inv]
            }
        pilotaje = ([(f,None) for f in analysis.get("pilotaje",[])]
                    + mar.get("PORT PILOTAGE",[]))
        if pilotaje:
            entries["PORT PILOTAGE"] = {
                "concept":"PORT PILOTAGE","amount":amt("PORT PILOTAGE"),
                "tc":tc_p,"invoices":pilotaje
            }
        melluso = ([(f,None) for f in analysis.get("melluso",[])]
                   + mar.get("MOORING & UNMOORING SERVICES",[]))
        if melluso:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept":"MOORING & UNMOORING SERVICES",
                "amount":amt("MOORING & UNMOORING SERVICES"),
                "tc":tc_p,"invoices":melluso
            }
        sg = ([(f,None) for f in analysis.get("shore_gangway",[])]
              + mar.get("SHORE GANGWAY",[]))
        if sg:
            entries["SHORE GANGWAY"] = {
                "concept":"SHORE GANGWAY","amount":amt("SHORE GANGWAY"),
                "tc":tc_p,"invoices":sg
            }
        if analysis.get("puerto_mariel"):
            entries["TOWAGE SERVICES"] = {
                "concept":"TOWAGE SERVICES","amount":amt("TOWAGE SERVICES"),
                "tc":tc_p,"invoices":[(f,None) for f in analysis["puerto_mariel"]]
            }
        ch = (mar.get("CUSTOM HOUSE EXPENSES",[])
              + [(f,None) for f in analysis.get("centro_nav",[])])
        if ch:
            entries["CUSTOM HOUSE EXPENSES"] = {
                "concept":"CUSTOM HOUSE EXPENSES","amount":amt("CUSTOM HOUSE EXPENSES"),
                "tc":tc_p,"invoices":ch
            }
        for v in ["CUSTOM HOUSE PERMANENCE","MIGRATION EXPENSES",
                  "SANITARY DUES AND FREE PRATIQUE","GARBAGE COMPULSORY INSPECTION",
                  "WATCHMEN COMPULSORY SERVICES","HEADCLERK COMPULSORY SERVICES"]:
            inv = mar.get(v,[])
            if inv and amt(v)>0:
                entries[v] = {"concept":v,"amount":amt(v),"tc":tc_p,"invoices":inv}
        pest = mar.get("PEST CONTROL",[])
        if pest:
            entries["PEST CONTROL"] = {
                "concept":"PEST CONTROL","amount":amt("PEST CONTROL"),
                "tc":tc_p,"invoices":pest
            }
        if amt("TAX ON CREDIT/DEBIT LAW 25.413")>0:
            entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
                "concept":"TAX ON CREDIT/DEBIT LAW 25.413",
                "amount":amt("TAX ON CREDIT/DEBIT LAW 25.413"),
                "tc":tc_p,"invoices":[],"solo":True
            }
        for concept, amount in la.items():
            if concept not in entries and amount>0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept":concept,"amount":amount,"tc":tc_p,"invoices":[]}

        base = [entries[v] for v in self.VOUCHER_ORDER if v in entries]
        return _build_with_extra_taxes(base, entries)

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="agency"),
                    keys[0] if keys else 1359.0)

    def _tc_port(self, a):
        tcs = [f["tc"] for f in a["facbs"]
               if f.get("type")=="port_expenses" and f.get("tc")]
        return min(tcs) if tcs else self._tc_agency(a)


# ══════════════════════════════════════════════════════════════════════════════
# SAN LORENZO / ARROYO SECO / GRAL. LAGOS
# ══════════════════════════════════════════════════════════════════════════════

class SanLorenzoPort:
    name       = "San Lorenzo Port"
    short_name = "SAN LORENZO"

    # ORDEN CORRECTO conforme al manual ISA (sección 3):
    # Tax 25.413 → Toll CARP → Pilot Launch → Toll AGP
    VOUCHER_ORDER = [
        "AGENCY FEE",
        "PORT DUES",
        "ENTRANCE AND LIGHT DUES",
        "RIVER PLATE PILOTAGE",
        "RIVER PLATE PILOTAGE (DELAY)",
        "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER",
        "RIVER PARANA PILOTAGE",
        "RIVER PARANA PILOTAGE (DELAY)",
        "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
        "PORT PILOTAGE",
        "PORT PILOTAGE (DELAY)",
        "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
        "LAUNCH SERVICES AT ZONA COMUN",
        "MOORING & UNMOORING SERVICES",
        "TOWAGE SERVICES",
        "CUSTOM HOUSE EXPENSES",
        "CUSTOM HOUSE PERMANENCE",
        "CUSTOM HOUSE EXPENSE (CARGO)",
        "MIGRATION EXPENSES",
        "SANITARY DUES AND FREE PRATIQUE",
        "GARBAGE COMPULSORY INSPECTION",
        "MANDATORY HOLDS INSPECTION",
        "MANDATORY HOLDS RE-INSPECTION",
        "FULL ON HIRE / BQS SURVEY",
        "BQS EXPENSES",
        "GAS FREE INSPECTION",
        "HEADCLERK COMPULSORY SERVICES",
        "PEST CONTROL",
        "WATCHMEN COMPULSORY SERVICES",
        "OSRO ANNEX 18",
        "TAX ON CREDIT/DEBIT LAW 25.413",
        "TOLL DUES (CARP)",
        "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
        "TOLL DUES (AGP)",
    ]

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        # Normalizar claves
        normalized = {}
        for k, v in line_amounts.items():
            key = k.upper().strip().replace("PRACTIQUE","PRATIQUE") \
                            .replace("CLEARENCE","CLEARANCE")
            aliases = {
                "RIVER PLATE PILOTAGE ANCHORAGE":     "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER",
                "RIVER PARANA PILOTAGE ANCHORAG":     "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
                "MANDATORY HOLDS INSPECTION AT":      "MANDATORY HOLDS INSPECTION",
                "HEADCLERK COMPULSORY":               "HEADCLERK COMPULSORY SERVICES",
                "LAUNCH SERVICES FOR CLEARANCE":      "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
                "FULL ON HIRE DELIVERY BUNKER A":     "FULL ON HIRE / BQS SURVEY",
            }
            key = aliases.get(key, key)
            normalized[key] = v
        line_amounts = normalized
        def amt(k): return line_amounts.get(k.upper(), 0)

        tc_a = self._tc_agency(analysis)
        tc_p = self._tc_port(analysis)
        mar  = _mar_inv_shared(analysis)
        entries = {}

        # Agency Fee
        entries["AGENCY FEE"] = {
            "concept":"AGENCY FEE",
            "amount": next((f.get("total",0) for f in analysis["facbs"]
                            if f.get("type")=="agency"), 0),
            "tc":tc_a,"invoices":[],"solo":True
        }

        # Port Dues
        term = [(f,None) for f in analysis.get("terminal_portuario",[])]
        if term and amt("PORT DUES")>0:
            entries["PORT DUES"] = {
                "concept":"PORT DUES","amount":amt("PORT DUES"),
                "tc":tc_p,"invoices":term
            }

        # Entrance and Light Dues — solo ENAPRO
        enapro = mar.get("ENTRANCE AND LIGHT DUES",[])
        if enapro and amt("ENTRANCE AND LIGHT DUES")>0:
            entries["ENTRANCE AND LIGHT DUES"] = {
                "concept":"ENTRANCE AND LIGHT DUES",
                "amount":amt("ENTRANCE AND LIGHT DUES"),
                "tc":tc_p,"invoices":enapro
            }

        # River Plate Pilotage
        rp_all   = analysis.get("practicaje_rp",[])
        rp_base  = [(r["filename"],None) for r in rp_all]
        rp_delay = [(r["filename"],None) for r in rp_all if r.get("has_demora")]
        rp_manio = [(r["filename"],None) for r in rp_all if r.get("has_maniobra")]
        rp_manio_amt = amt("RIVER PLATE PILOTAGE ANCHORAGE MANEUVER") or \
                       sum(r.get("maniobra_amount",0) for r in rp_all if r.get("has_maniobra"))
        if not rp_manio: rp_manio = rp_base

        if rp_base and amt("RIVER PLATE PILOTAGE")>0:
            entries["RIVER PLATE PILOTAGE"] = {
                "concept":"RIVER PLATE PILOTAGE","amount":amt("RIVER PLATE PILOTAGE"),
                "tc":tc_p,"invoices":rp_base
            }
        if rp_delay and amt("RIVER PLATE PILOTAGE (DELAY)")>0:
            entries["RIVER PLATE PILOTAGE (DELAY)"] = {
                "concept":"RIVER PLATE PILOTAGE (DELAY)",
                "amount":amt("RIVER PLATE PILOTAGE (DELAY)"),
                "tc":tc_p,"invoices":rp_delay
            }
        if rp_manio and rp_manio_amt>0:
            entries["RIVER PLATE PILOTAGE ANCHORAGE MANEUVER"] = {
                "concept":"RIVER PLATE PILOTAGE ANCHORAGE MANEUVER",
                "amount":rp_manio_amt,"tc":tc_p,"invoices":rp_manio
            }

        # River Parana Pilotage — COPRAC / Multipar / River Pilot
        cp_all   = analysis.get("coprac",[])
        cp_base  = [(r["filename"],None) for r in cp_all]
        cp_delay = [(r["filename"],None) for r in cp_all if r.get("has_demora")]
        cp_manio = [(r["filename"],None) for r in cp_all if r.get("has_maniobra")]
        cp_manio_amt = amt("RIVER PARANA PILOTAGE ANCHORAGE MANEUVER") or \
                       sum(r.get("maniobra_amount",0) for r in cp_all if r.get("has_maniobra"))
        if not cp_manio: cp_manio = cp_base

        if cp_base and amt("RIVER PARANA PILOTAGE")>0:
            entries["RIVER PARANA PILOTAGE"] = {
                "concept":"RIVER PARANA PILOTAGE","amount":amt("RIVER PARANA PILOTAGE"),
                "tc":tc_p,"invoices":cp_base
            }
        if cp_delay and amt("RIVER PARANA PILOTAGE (DELAY)")>0:
            entries["RIVER PARANA PILOTAGE (DELAY)"] = {
                "concept":"RIVER PARANA PILOTAGE (DELAY)",
                "amount":amt("RIVER PARANA PILOTAGE (DELAY)"),
                "tc":tc_p,"invoices":cp_delay
            }
        if cp_manio and cp_manio_amt>0:
            entries["RIVER PARANA PILOTAGE ANCHORAGE MANEUVER"] = {
                "concept":"RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
                "amount":cp_manio_amt,"tc":tc_p,"invoices":cp_manio
            }

        # Port Pilotage — Rosario Pilots (facturas primero, vouchers internos después)
        rsp_all      = analysis.get("rosario_pilots",[])
        rsp_facturas = []
        rsp_vouchers = []
        for r in rsp_all:
            fname      = r["filename"]
            fact_pages = []
            vouch_pages= []
            try:
                import fitz as _fitz_rsp
                doc = _fitz_rsp.open(os.path.join(work_dir, fname))
                for i in range(doc.page_count):
                    text = doc[i].get_text()
                    if "Voucher por Servicio de Practicaje" in text and "SUBTOTAL" not in text:
                        vouch_pages.append(i)
                    else:
                        fact_pages.append(i)
            except Exception:
                fact_pages = [0]
            if fact_pages:  rsp_facturas.append((fname, fact_pages))
            if vouch_pages: rsp_vouchers.append((fname, vouch_pages))

        rsp_base  = rsp_facturas + rsp_vouchers
        rsp_delay = [(r["filename"],None) for r in rsp_all if r.get("has_demora")]
        if rsp_base and amt("PORT PILOTAGE")>0:
            entries["PORT PILOTAGE"] = {
                "concept":"PORT PILOTAGE","amount":amt("PORT PILOTAGE"),
                "tc":tc_p,"invoices":rsp_base
            }
        if rsp_delay and amt("PORT PILOTAGE (DELAY)")>0:
            entries["PORT PILOTAGE (DELAY)"] = {
                "concept":"PORT PILOTAGE (DELAY)","amount":amt("PORT PILOTAGE (DELAY)"),
                "tc":tc_p,"invoices":rsp_delay
            }

        # Launch Services for Clearance
        clearance_inv = [(r["filename"],[0]) for r in analysis.get("amarre_coral",[])
                         if r.get("is_clearance")]
        if clearance_inv and amt("LAUNCH SERVICES FOR CLEARANCE (AT ROADS)")>0:
            entries["LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"] = {
                "concept":"LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
                "amount":amt("LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"),
                "tc":tc_p,"invoices":clearance_inv
            }

        # Mooring & Unmooring
        mooring_inv = [(r["filename"],None) for r in analysis.get("amarre_coral",[])
                       if r.get("is_mooring")]
        all_mooring = mooring_inv + mar.get("MOORING & UNMOORING SERVICES",[])
        if all_mooring and amt("MOORING & UNMOORING SERVICES")>0:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept":"MOORING & UNMOORING SERVICES",
                "amount":amt("MOORING & UNMOORING SERVICES"),
                "tc":tc_p,"invoices":all_mooring
            }

        # Custom House Expenses — Centro de Navegación primero, luego AFIP/SSEE
        nav_files = [(f,None) for f in analysis.get("centro_nav",[])]
        mar_ch    = mar.get("CUSTOM HOUSE EXPENSES",[])
        mar_nav   = mar.get("NAVIGATION CENTER CONTRIBUTION",[])
        ch_inv    = nav_files + mar_nav + mar_ch
        if ch_inv and amt("CUSTOM HOUSE EXPENSES")>0:
            entries["CUSTOM HOUSE EXPENSES"] = {
                "concept":"CUSTOM HOUSE EXPENSES",
                "amount":amt("CUSTOM HOUSE EXPENSES"),
                "tc":tc_p,"invoices":ch_inv
            }

        for v in ["CUSTOM HOUSE PERMANENCE","CUSTOM HOUSE EXPENSE (CARGO)"]:
            inv = mar.get(v,[])
            if inv and amt(v)>0:
                entries[v] = {"concept":v,"amount":amt(v),"tc":tc_p,"invoices":inv}

        # Migration
        mig_inv = mar.get("MIGRATION EXPENSES",[])
        if mig_inv and amt("MIGRATION EXPENSES")>0:
            entries["MIGRATION EXPENSES"] = {
                "concept":"MIGRATION EXPENSES","amount":amt("MIGRATION EXPENSES"),
                "tc":tc_p,"invoices":mig_inv
            }

        # Sanitary
        san_inv = mar.get("SANITARY DUES AND FREE PRATIQUE",[])
        if san_inv and amt("SANITARY DUES AND FREE PRATIQUE")>0:
            entries["SANITARY DUES AND FREE PRATIQUE"] = {
                "concept":"SANITARY DUES AND FREE PRATIQUE",
                "amount":amt("SANITARY DUES AND FREE PRATIQUE"),
                "tc":tc_p,"invoices":san_inv
            }

        # Garbage
        garb_inv = mar.get("GARBAGE COMPULSORY INSPECTION",[])
        if garb_inv and amt("GARBAGE COMPULSORY INSPECTION")>0:
            entries["GARBAGE COMPULSORY INSPECTION"] = {
                "concept":"GARBAGE COMPULSORY INSPECTION",
                "amount":amt("GARBAGE COMPULSORY INSPECTION"),
                "tc":tc_p,"invoices":garb_inv
            }

        # Mandatory Holds — inspectores externos (archivos fuera de Maritime)
        mand_insp_ext = [(f, None) for f in analysis.get("mandatory_insp_ext", [])]
        for v in ["MANDATORY HOLDS INSPECTION", "MANDATORY HOLDS RE-INSPECTION"]:
            inv = mar.get(v, []) + (mand_insp_ext if v == "MANDATORY HOLDS INSPECTION" else [])
            if inv and amt(v) > 0:
                entries[v] = {"concept": v, "amount": amt(v), "tc": tc_p, "invoices": inv}

        # Towage (San Lorenzo — remolcadores, ocurre ocasionalmente)
        towage_inv = [(f, None) for f in analysis.get("towage_sl", [])]
        if towage_inv and amt("TOWAGE SERVICES") > 0:
            entries["TOWAGE SERVICES"] = {
                "concept": "TOWAGE SERVICES", "amount": amt("TOWAGE SERVICES"),
                "tc": tc_p, "invoices": towage_inv
            }

        # Full On Hire / BQS Survey
        survey_inv = [(f,[0]) for f in analysis.get("edi_separovic",[])]
        if survey_inv and amt("FULL ON HIRE / BQS SURVEY")>0:
            entries["FULL ON HIRE / BQS SURVEY"] = {
                "concept":"FULL ON HIRE / BQS SURVEY",
                "amount":amt("FULL ON HIRE / BQS SURVEY"),
                "tc":tc_p,"invoices":survey_inv
            }

        # Misc
        for v in ["BQS EXPENSES","GAS FREE INSPECTION","PEST CONTROL",
                  "WATCHMEN COMPULSORY SERVICES","OSRO ANNEX 18"]:
            inv = mar.get(v,[])
            if inv and amt(v)>0:
                entries[v] = {"concept":v,"amount":amt(v),"tc":tc_p,"invoices":inv}

        # Headclerk
        headclerk = mar.get("HEADCLERK COMPULSORY SERVICES",[])
        if headclerk and amt("HEADCLERK COMPULSORY SERVICES")>0:
            entries["HEADCLERK COMPULSORY SERVICES"] = {
                "concept":"HEADCLERK COMPULSORY SERVICES",
                "amount":amt("HEADCLERK COMPULSORY SERVICES"),
                "tc":tc_p,"invoices":headclerk
            }

        # Tax TC base
        if amt("TAX ON CREDIT/DEBIT LAW 25.413")>0:
            entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
                "concept":"TAX ON CREDIT/DEBIT LAW 25.413",
                "amount":amt("TAX ON CREDIT/DEBIT LAW 25.413"),
                "tc":tc_p,"invoices":[],"solo":True
            }

        # Tax extras de TCs superiores
        import re as _re_tax
        for key_la, val_la in line_amounts.items():
            if "_TC" in key_la and key_la.startswith("TAX ON CREDIT/DEBIT LAW 25.413") \
                    and val_la > 0:
                m = _re_tax.search(r"_TC([\d.]+)$", key_la)
                if m:
                    tc_extra = float(m.group(1))
                    entries[key_la] = {
                        "concept":"TAX ON CREDIT/DEBIT LAW 25.413",
                        "amount":val_la,"tc":tc_extra,
                        "invoices":[],"solo":True
                    }

        # Toll CARP
        carp_inv = [(f,None) for f in analysis.get("carp",[])]
        if amt("TOLL DUES (CARP)")>0:
            tc_carp = self._tc_for_concept(analysis,"TOLL DUES (CARP)",work_dir)
            entries["TOLL DUES (CARP)"] = {
                "concept":"TOLL DUES (CARP)","amount":amt("TOLL DUES (CARP)"),
                "tc":tc_carp,"invoices":carp_inv
            }

        # Pilot Launch — Glatil (solo USD 4,440)
        glatil_all = analysis.get("glatil",[])
        glatil_inv = []
        for fname in glatil_all:
            fpath = os.path.join(work_dir, fname)
            try:
                import fitz as _fz
                text = "".join(pg.get_text() for pg in _fz.open(fpath))
                # Excluir Glatil 5,234.80 y 6,154.80
                if "5,234" in text or "5.234" in text or \
                   "6,154" in text or "6.154" in text:
                    print(f"  ⚠ Glatil excluido (monto incorrecto): {fname}")
                    continue
            except Exception:
                pass
            glatil_inv.append((fname, None))

        if glatil_inv and amt("PILOT LAUNCH TRANSPORTATION RIVER PLATE")>0:
            tc_glatil = self._tc_for_concept(analysis,
                                             "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
                                             work_dir)
            entries["PILOT LAUNCH TRANSPORTATION RIVER PLATE"] = {
                "concept":"PILOT LAUNCH TRANSPORTATION RIVER PLATE",
                "amount":amt("PILOT LAUNCH TRANSPORTATION RIVER PLATE"),
                "tc":tc_glatil,"invoices":glatil_inv
            }

        # Toll AGP
        agp_inv = [(f,None) for f in analysis.get("agp",[])]
        if agp_inv and amt("TOLL DUES (AGP)")>0:
            tc_agp = self._tc_for_concept(analysis,"TOLL DUES (AGP)",work_dir)
            entries["TOLL DUES (AGP)"] = {
                "concept":"TOLL DUES (AGP)","amount":amt("TOLL DUES (AGP)"),
                "tc":tc_agp,"invoices":agp_inv
            }

        # Fallback
        for concept, amount in line_amounts.items():
            if concept not in entries and amount>0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept":concept,"amount":amount,
                                    "tc":tc_p,"invoices":[]}

        base = [entries[v] for v in self.VOUCHER_ORDER if v in entries]
        return _build_with_extra_taxes(base, entries)

    # ── helpers ──────────────────────────────────────────────────────────

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="agency"),
                    keys[0] if keys else 1407.0)

    def _tc_port(self, a):
        tcs = [f["tc"] for f in a["facbs"]
               if f.get("type")=="port_expenses" and f.get("tc")]
        return min(tcs) if tcs else self._tc_agency(a)

    def _tc_for_concept(self, a, concept, work_dir):
        """TC de la FACB port_expenses que contiene el concepto."""
        from assembler import extract_facb_line_amounts
        concept_up = concept.upper()
        aliases = {
            "TOLL DUES (AGP)":                          ["TOLL DUES"],
            "TOLL DUES (CARP)":                         ["TOLL DUES"],
            "PILOT LAUNCH TRANSPORTATION RIVER PLATE":  ["RIVER PLATE PILOTAGE",
                                                          "PILOT LAUNCH"],
        }
        search_terms = aliases.get(concept_up, [concept_up])
        matching_tcs = []
        for facb in sorted(a.get("facbs",[]), key=lambda x: x.get("tc",0)):
            if facb.get("type") != "port_expenses":
                continue
            fpath = os.path.join(work_dir, facb.get("filename",""))
            if not os.path.exists(fpath):
                continue
            try:
                la     = extract_facb_line_amounts(fpath)
                la_keys= [k.upper() for k in la.keys()]
                for term in search_terms:
                    if any(term in kk for kk in la_keys):
                        matching_tcs.append(facb.get("tc",0))
                        break
            except Exception:
                pass
        if not matching_tcs:
            return self._tc_port(a)
        if concept_up == "TOLL DUES (AGP)":
            return min(matching_tcs)
        if concept_up in ("TOLL DUES (CARP)",
                          "PILOT LAUNCH TRANSPORTATION RIVER PLATE"):
            return max(matching_tcs)
        return matching_tcs[0]


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
    # Fallback por proveedores detectados
    if analysis.get("consorcio_quequen") or analysis.get("melluso") or analysis.get("pilotaje"):
        return NecocheaPort()
    if (analysis.get("practicaje_rp") or analysis.get("coprac") or
            analysis.get("rosario_pilots") or analysis.get("terminal_portuario")):
        return SanLorenzoPort()
    return BahiaBlancaPort()




















