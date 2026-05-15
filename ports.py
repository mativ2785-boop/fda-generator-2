"""
ports.py  —  Configuración multi-puerto para FDA Generator ISA
Un solo archivo — compatible con Render sin necesidad de carpetas.
"""

import os
# ══════════════════════════════════════════════════════════════════════════════
#  BAHIA BLANCA
# ══════════════════════════════════════════════════════════════════════════════

class BahiaBlancaPort:
    name       = "Bahia Blanca Port"
    short_name = "BAHIA BLANCA"

    VOUCHER_ORDER = [
        "AGENCY FEE", "PORT DUES", "PERMANENCE DUES", "TOLL DUES",
        "PORT PILOTAGE", "PORT PILOTAGE (DELAY)", "MOORING & UNMOORING SERVICES",
        "TOWAGE SERVICES", "CUSTOM HOUSE EXPENSES", "CUSTOM HOUSE PERMANENCE",
        "CUSTOM HOUSE (BUNKERING)", "MIGRATION EXPENSES",
        "SANITARY DUES AND FREE PRATIQUE", "GARBAGE COMPULSORY INSPECTION",
        "WATCHMEN COMPULSORY SERVICES", "HEADCLERK COMPULSORY SERVICES",
        "PEST CONTROL", "OSRO ANNEX 18", "TAX ON CREDIT/DEBIT LAW 25.413",
    ]

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        # Normalizar variaciones de spelling en conceptos
        normalized = {}
        for k, v in line_amounts.items():
            key = k.upper()
            key = key.replace("PRACTIQUE", "PRATIQUE")  # FACA uses Q spelling
            key = key.replace("FREE PRATIQUE", "FREE PRATIQUE")
            normalized[key] = v
        line_amounts = normalized
        def amt(k): return line_amounts.get(k.upper(), 0)
        tc_agency = self._tc_agency(analysis)
        tc_port   = self._tc_port(analysis)
        mar       = self._mar_inv(analysis)
        entries   = {}

        entries["AGENCY FEE"] = {
            "concept": "AGENCY FEE",
            "amount":  next((f.get("total",0) for f in analysis["facbs"] if f.get("type")=="agency"), 0),
            "tc": tc_agency, "invoices": [], "solo": True,
        }
        if analysis.get("consorcio"):
            entries["PORT DUES"] = {"concept":"PORT DUES","amount":amt("PORT DUES"),"tc":tc_port,
                "invoices":[(analysis["consorcio"][0], None)]}
            entries["TOLL DUES"] = {"concept":"TOLL DUES","amount":amt("TOLL DUES"),"tc":tc_port,
                "invoices":[(f,None) for f in analysis["consorcio"]]}
        if analysis.get("donmar"):
            entries["PORT PILOTAGE"] = {"concept":"PORT PILOTAGE","amount":amt("PORT PILOTAGE"),"tc":tc_port,
                "invoices":[(f,None) for f in analysis["donmar"]]}
        mooring = mar.get("MOORING & UNMOORING SERVICES",[]) + [(f,None) for f in analysis.get("amarradores",[])]
        if mooring and amt("MOORING & UNMOORING SERVICES") > 0:
            entries["MOORING & UNMOORING SERVICES"] = {"concept":"MOORING & UNMOORING SERVICES",
                "amount":amt("MOORING & UNMOORING SERVICES"),"tc":tc_port,"invoices":mooring}
        if analysis.get("puerto_mariel") and amt("TOWAGE SERVICES") > 0:
            entries["TOWAGE SERVICES"] = {"concept":"TOWAGE SERVICES","amount":amt("TOWAGE SERVICES"),
                "tc":tc_port,"invoices":[(f,None) for f in analysis["puerto_mariel"]]}
        for v in ["CUSTOM HOUSE EXPENSES","CUSTOM HOUSE PERMANENCE","CUSTOM HOUSE (BUNKERING)",
                  "MIGRATION EXPENSES","SANITARY DUES AND FREE PRATIQUE","GARBAGE COMPULSORY INSPECTION",
                  "WATCHMEN COMPULSORY SERVICES","HEADCLERK COMPULSORY SERVICES"]:
            inv = mar.get(v,[])
            if inv and amt(v) > 0: entries[v] = {"concept":v,"amount":amt(v),"tc":tc_port,"invoices":inv}
        pest = mar.get("PEST CONTROL",[]) + [(f,None) for f in analysis.get("ammoca",[])]
        if pest: entries["PEST CONTROL"] = {"concept":"PEST CONTROL","amount":amt("PEST CONTROL"),"tc":tc_port,"invoices":pest}
        osro = mar.get("OSRO ANNEX 18",[])
        if osro: entries["OSRO ANNEX 18"] = {"concept":"OSRO ANNEX 18","amount":amt("OSRO ANNEX 18"),"tc":tc_port,"invoices":osro}
        entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {"concept":"TAX ON CREDIT/DEBIT LAW 25.413",
            "amount":amt("TAX ON CREDIT/DEBIT LAW 25.413"),"tc":tc_port,"invoices":[],"solo":True}

        # Fallback: si hay monto en la FACB para un concepto que no tiene voucher → crearlo
        for concept, amount in line_amounts.items():
            if concept not in entries and amount > 0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept":concept,"amount":amount,"tc":tc_port,"invoices":[]}

        return [entries[v] for v in self.VOUCHER_ORDER if v in entries]

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="agency"), keys[0] if keys else 1373.5)
    def _tc_port(self, a):
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="port_expenses"), self._tc_agency(a))
    def _mar_inv(self, analysis, exclude_mooring_img=True):
        mar_pages = {}
        for m in analysis.get("maritime",[]):
            for pg in m["pages"]:
                v, cat = pg.get("voucher"), pg.get("category","")
                if exclude_mooring_img and cat == "mooring_img": continue
                if v: mar_pages.setdefault(v,[]).append((m["filename"], pg["page"]))
        result = {}
        for v, pairs in mar_pages.items():
            merged = {}
            for fname, pg in pairs: merged.setdefault(fname,[]).append(pg)
            result[v] = [(f, sorted(set(pgs))) for f, pgs in merged.items()]
        return result


# ══════════════════════════════════════════════════════════════════════════════
#  NECOCHEA
# ══════════════════════════════════════════════════════════════════════════════

class NecocheaPort:
    name       = "Necochea Port"
    short_name = "NECOCHEA"

    VOUCHER_ORDER = [
        "AGENCY FEE", "PORT DUES", "ENTRANCE AND LIGHT DUES", "TOLL DUES",
        "PORT PILOTAGE", "PORT PILOTAGE (DELAY)", "MOORING & UNMOORING SERVICES",
        "SHORE GANGWAY", "TOWAGE SERVICES", "CUSTOM HOUSE EXPENSES", "CUSTOM HOUSE PERMANENCE",
        "MIGRATION EXPENSES", "SANITARY DUES AND FREE PRATIQUE",
        "GARBAGE COMPULSORY INSPECTION", "WATCHMEN COMPULSORY SERVICES",
        "HEADCLERK COMPULSORY SERVICES", "PEST CONTROL",
        "TAX ON CREDIT/DEBIT LAW 25.413",
    ]

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        # Normalizar variaciones de spelling en conceptos
        normalized = {}
        for k, v in line_amounts.items():
            key = k.upper()
            key = key.replace("PRACTIQUE", "PRATIQUE")  # FACA uses Q spelling
            key = key.replace("FREE PRATIQUE", "FREE PRATIQUE")
            normalized[key] = v
        line_amounts = normalized
        def amt(k): return line_amounts.get(k.upper(), 0)
        tc_agency = self._tc_agency(analysis)
        tc_port   = self._tc_port(analysis)
        mar       = self._mar_inv(analysis)
        entries   = {}

        entries["AGENCY FEE"] = {
            "concept": "AGENCY FEE",
            "amount":  next((f.get("total",0) for f in analysis["facbs"] if f.get("type")=="agency"), 0),
            "tc": tc_agency, "invoices": [], "solo": True,
        }
        consorcio = analysis.get("consorcio_quequen") or analysis.get("consorcio", [])
        if consorcio:
            entries["PORT DUES"] = {"concept":"PORT DUES","amount":amt("PORT DUES"),"tc":tc_port,
                "invoices":[(consorcio[0], None)]}
        if len(consorcio) >= 2:
            entries["ENTRANCE AND LIGHT DUES"] = {"concept":"ENTRANCE AND LIGHT DUES",
                "amount":amt("ENTRANCE AND LIGHT DUES"),"tc":tc_port,"invoices":[(consorcio[1], None)]}
        elif consorcio:
            entries["ENTRANCE AND LIGHT DUES"] = {"concept":"ENTRANCE AND LIGHT DUES",
                "amount":amt("ENTRANCE AND LIGHT DUES"),"tc":tc_port,"invoices":[(consorcio[0], None)]}
        toll_inv = consorcio[2:] if len(consorcio) > 2 else consorcio
        if toll_inv:
            entries["TOLL DUES"] = {"concept":"TOLL DUES","amount":amt("TOLL DUES"),"tc":tc_port,
                "invoices":[(f,None) for f in toll_inv]}
        # Port Pilotage: archivo separado (pilotaje) O páginas Maritime (meyer_arana)
        pilotaje = [(f,None) for f in analysis.get("pilotaje",[])] + mar.get("PORT PILOTAGE",[])
        if pilotaje:
            entries["PORT PILOTAGE"] = {"concept":"PORT PILOTAGE","amount":amt("PORT PILOTAGE"),
                "tc":tc_port,"invoices":pilotaje}
        # Mooring: Melluso separado O páginas Maritime
        melluso = [(f,None) for f in analysis.get("melluso",[])] + mar.get("MOORING & UNMOORING SERVICES",[])
        if melluso:
            entries["MOORING & UNMOORING SERVICES"] = {"concept":"MOORING & UNMOORING SERVICES",
                "amount":amt("MOORING & UNMOORING SERVICES"),"tc":tc_port,"invoices":melluso}
        # Shore Gangway: archivo separado O página Maritime
        sg = [(f,None) for f in analysis.get("shore_gangway",[])] + mar.get("SHORE GANGWAY",[])
        if sg:
            entries["SHORE GANGWAY"] = {"concept":"SHORE GANGWAY","amount":amt("SHORE GANGWAY"),
                "tc":tc_port,"invoices":sg}
        # Towage Services — Puerto Mariel (cuando aplica en Necochea)
        if analysis.get("puerto_mariel"):
            entries["TOWAGE SERVICES"] = {"concept":"TOWAGE SERVICES",
                "amount":amt("TOWAGE SERVICES"),"tc":tc_port,
                "invoices":[(f,None) for f in analysis["puerto_mariel"]]}

        # Custom House Expenses: Maritime + Centro de Navegación
        ch = mar.get("CUSTOM HOUSE EXPENSES",[]) + [(f,None) for f in analysis.get("centro_nav",[])]
        if ch:
            entries["CUSTOM HOUSE EXPENSES"] = {"concept":"CUSTOM HOUSE EXPENSES",
                "amount":amt("CUSTOM HOUSE EXPENSES"),"tc":tc_port,"invoices":ch}
        for v in ["CUSTOM HOUSE PERMANENCE","MIGRATION EXPENSES","SANITARY DUES AND FREE PRATIQUE",
                  "GARBAGE COMPULSORY INSPECTION","WATCHMEN COMPULSORY SERVICES","HEADCLERK COMPULSORY SERVICES"]:
            inv = mar.get(v,[])
            if inv and amt(v) > 0: entries[v] = {"concept":v,"amount":amt(v),"tc":tc_port,"invoices":inv}
        pest = mar.get("PEST CONTROL",[])
        if pest: entries["PEST CONTROL"] = {"concept":"PEST CONTROL","amount":amt("PEST CONTROL"),"tc":tc_port,"invoices":pest}
        entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {"concept":"TAX ON CREDIT/DEBIT LAW 25.413",
            "amount":amt("TAX ON CREDIT/DEBIT LAW 25.413"),"tc":tc_port,"invoices":[],"solo":True}

        # Fallback: si hay monto en la FACB para un concepto que no tiene voucher → crearlo
        for concept, amount in line_amounts.items():
            if concept not in entries and amount > 0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept":concept,"amount":amount,"tc":tc_port,"invoices":[]}

        return [entries[v] for v in self.VOUCHER_ORDER if v in entries]

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="agency"), keys[0] if keys else 1359.0)
    def _tc_port(self, a):
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="port_expenses"), self._tc_agency(a))
    def _mar_inv(self, analysis, exclude_mooring_img=True):
        mar_pages = {}
        for m in analysis.get("maritime",[]):
            for pg in m["pages"]:
                v, cat = pg.get("voucher"), pg.get("category","")
                if exclude_mooring_img and cat == "mooring_img": continue
                if v: mar_pages.setdefault(v,[]).append((m["filename"], pg["page"]))
        result = {}
        for v, pairs in mar_pages.items():
            merged = {}
            for fname, pg in pairs: merged.setdefault(fname,[]).append(pg)
            result[v] = [(f, sorted(set(pgs))) for f, pgs in merged.items()]
        return result



# ══════════════════════════════════════════════════════════════════════════════
#  SAN LORENZO / ARROYO SECO / GRAL. LAGOS
# ══════════════════════════════════════════════════════════════════════════════

class SanLorenzoPort:
    name       = "San Lorenzo Port"
    short_name = "SAN LORENZO"

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
        "CUSTOM HOUSE EXPENSES",
        "CUSTOM HOUSE PERMANENCE",
        "CUSTOM HOUSE EXPENSE (CARGO)",
        "NAVIGATION CENTER CONTRIBUTION",
        "MIGRATION EXPENSES",
        "SANITARY DUES AND FREE PRATIQUE",
        "GARBAGE COMPULSORY INSPECTION",
        "MANDATORY HOLDS INSPECTION",
        "MANDATORY HOLDS RE-INSPECTION",
        "HEADCLERK COMPULSORY SERVICES",
        "FULL ON HIRE / BQS SURVEY",
        "BQS EXPENSES",
        "GAS FREE INSPECTION",
        "PEST CONTROL",
        "TAX ON CREDIT/DEBIT LAW 25.413",
        "TOLL DUES (CARP)",
        "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
        "TOLL DUES (AGP)",
    ]

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        # Normalizar variaciones de spelling en conceptos
        normalized = {}
        for k, v in line_amounts.items():
            key = k.upper().strip()
            key = key.replace("PRACTIQUE", "PRATIQUE")
            key = key.replace("CLEARENCE", "CLEARANCE")
            key = key.replace("ANCHORAGE\n", "ANCHORAGE MANEUVER")
            # Expansiones de nombres truncados en FACB
            if key == "RIVER PLATE PILOTAGE ANCHORAGE":
                key = "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER"
            if key == "RIVER PARANA PILOTAGE ANCHORAG":
                key = "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER"
            if key == "MANDATORY HOLDS INSPECTION AT":
                key = "MANDATORY HOLDS INSPECTION"
            if key == "HEADCLERK COMPULSORY":
                key = "HEADCLERK COMPULSORY SERVICES"
            if key == "LAUNCH SERVICES FOR CLEARENCE":
                key = "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"
            if key == "LAUNCH SERVICES FOR CLEARANCE":
                key = "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"
            normalized[key] = v
        line_amounts = normalized

        def amt(k): return line_amounts.get(k.upper(), 0)
        def fp(f):  return os.path.join(work_dir, f)

        tc_agency = self._tc_agency(analysis)
        tc_port   = self._tc_port(analysis)
        mar       = self._mar_inv(analysis)
        entries   = {}

        # ── 1. Agency Fee (solo voucher, sin factura) ────────────────────────
        entries["AGENCY FEE"] = {
            "concept": "AGENCY FEE",
            "amount":  next((f.get("total", 0) for f in analysis["facbs"] if f.get("type") == "agency"), 0),
            "tc": tc_agency, "invoices": [], "solo": True,
        }

        # ── 2. Port Dues — terminal portuario ────────────────────────────────
        term = [(f, None) for f in analysis.get("terminal_portuario", [])]
        if term and amt("PORT DUES") > 0:
            entries["PORT DUES"] = {
                "concept": "PORT DUES", "amount": amt("PORT DUES"),
                "tc": tc_port, "invoices": term,
            }

        # ── 3. Entrance and Light Dues — ENAPRO (pág. interna de Maritime) ──
        enapro_pages = mar.get("ENTRANCE AND LIGHT DUES", [])
        if enapro_pages and amt("ENTRANCE AND LIGHT DUES") > 0:
            entries["ENTRANCE AND LIGHT DUES"] = {
                "concept": "ENTRANCE AND LIGHT DUES",
                "amount":  amt("ENTRANCE AND LIGHT DUES"),
                "tc": tc_port, "invoices": enapro_pages,
            }

        # ── 4-6. River Plate Pilotage ────────────────────────────────────────
        rp_all  = analysis.get("practicaje_rp", [])
        rp_base = [(r["filename"], None) for r in rp_all]
        rp_delay= [(r["filename"], None) for r in rp_all if r.get("has_demora")]
        rp_manio= [(r["filename"], None) for r in rp_all if r.get("has_maniobra")]
        rp_manio_amt = sum(r.get("maniobra_amount", 0) for r in rp_all if r.get("has_maniobra"))
        # Si el monto de maniobra está en la FACB pero no se detectó en las facturas,
        # usamos el monto de la FACB y las facturas del Río de la Plata (que contienen la maniobra)
        facb_rp_manio = amt("RIVER PLATE PILOTAGE ANCHORAGE MANEUVER")
        if facb_rp_manio > 0 and rp_manio_amt == 0:
            rp_manio_amt = facb_rp_manio
            rp_manio = rp_base  # incluir todas las facturas del proveedor

        if rp_base and amt("RIVER PLATE PILOTAGE") > 0:
            entries["RIVER PLATE PILOTAGE"] = {
                "concept": "RIVER PLATE PILOTAGE",
                "amount":  amt("RIVER PLATE PILOTAGE"),
                "tc": tc_port, "invoices": rp_base,
            }
        if rp_delay and amt("RIVER PLATE PILOTAGE (DELAY)") > 0:
            entries["RIVER PLATE PILOTAGE (DELAY)"] = {
                "concept": "RIVER PLATE PILOTAGE (DELAY)",
                "amount":  amt("RIVER PLATE PILOTAGE (DELAY)"),
                "tc": tc_port, "invoices": rp_delay,
            }
        if rp_manio and rp_manio_amt > 0:
            entries["RIVER PLATE PILOTAGE ANCHORAGE MANEUVER"] = {
                "concept": "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER",
                "amount":  rp_manio_amt,
                "tc": tc_port, "invoices": rp_manio,
            }

        # ── 7-9. River Parana Pilotage (COPRAC) ──────────────────────────────
        cp_all  = analysis.get("coprac", [])
        cp_base = [(r["filename"], None) for r in cp_all]
        cp_delay= [(r["filename"], None) for r in cp_all if r.get("has_demora")]
        cp_manio= [(r["filename"], None) for r in cp_all if r.get("has_maniobra")]
        cp_manio_amt = sum(r.get("maniobra_amount", 0) for r in cp_all if r.get("has_maniobra"))
        facb_cp_manio = amt("RIVER PARANA PILOTAGE ANCHORAGE MANEUVER")
        if facb_cp_manio > 0 and cp_manio_amt == 0:
            cp_manio_amt = facb_cp_manio
            cp_manio = cp_base  # incluir todas las facturas COPRAC

        if cp_base and amt("RIVER PARANA PILOTAGE") > 0:
            entries["RIVER PARANA PILOTAGE"] = {
                "concept": "RIVER PARANA PILOTAGE",
                "amount":  amt("RIVER PARANA PILOTAGE"),
                "tc": tc_port, "invoices": cp_base,
            }
        if cp_delay and amt("RIVER PARANA PILOTAGE (DELAY)") > 0:
            entries["RIVER PARANA PILOTAGE (DELAY)"] = {
                "concept": "RIVER PARANA PILOTAGE (DELAY)",
                "amount":  amt("RIVER PARANA PILOTAGE (DELAY)"),
                "tc": tc_port, "invoices": cp_delay,
            }
        if cp_manio and cp_manio_amt > 0:
            entries["RIVER PARANA PILOTAGE ANCHORAGE MANEUVER"] = {
                "concept": "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
                "amount":  cp_manio_amt,
                "tc": tc_port, "invoices": cp_manio,
            }

        # ── 10-11. Port Pilotage (Rosario Pilots) ────────────────────────────
        rsp_all  = analysis.get("rosario_pilots", [])
        rsp_base = [(r["filename"], None) for r in rsp_all]
        rsp_delay= [(r["filename"], None) for r in rsp_all if r.get("has_demora")]

        if rsp_base and amt("PORT PILOTAGE") > 0:
            entries["PORT PILOTAGE"] = {
                "concept": "PORT PILOTAGE",
                "amount":  amt("PORT PILOTAGE"),
                "tc": tc_port, "invoices": rsp_base,
            }
        if rsp_delay and amt("PORT PILOTAGE (DELAY)") > 0:
            entries["PORT PILOTAGE (DELAY)"] = {
                "concept": "PORT PILOTAGE (DELAY)",
                "amount":  amt("PORT PILOTAGE (DELAY)"),
                "tc": tc_port, "invoices": rsp_delay,
            }

        # ── 12. Launch Services for Clearance ────────────────────────────────
        clearance_inv = [(r["filename"], None) for r in analysis.get("amarre_coral", [])
                         if r.get("is_clearance")]
        if clearance_inv and amt("LAUNCH SERVICES FOR CLEARANCE (AT ROADS)") > 0:
            entries["LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"] = {
                "concept": "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
                "amount":  amt("LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"),
                "tc": tc_port, "invoices": clearance_inv,
            }

        # ── 14. Mooring & Unmooring ───────────────────────────────────────────
        mooring_inv = [(r["filename"], None) for r in analysis.get("amarre_coral", [])
                       if r.get("is_mooring")]
        mar_mooring = mar.get("MOORING & UNMOORING SERVICES", [])
        all_mooring = mooring_inv + mar_mooring
        if all_mooring and amt("MOORING & UNMOORING SERVICES") > 0:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept": "MOORING & UNMOORING SERVICES",
                "amount":  amt("MOORING & UNMOORING SERVICES"),
                "tc": tc_port, "invoices": all_mooring,
            }

        # ── Maritime vouchers ─────────────────────────────────────────────────
        for voucher in [
            "CUSTOM HOUSE EXPENSES",
            "CUSTOM HOUSE PERMANENCE",
            "CUSTOM HOUSE EXPENSE (CARGO)",
            "MIGRATION EXPENSES",
            "SANITARY DUES AND FREE PRATIQUE",
            "GARBAGE COMPULSORY INSPECTION",
            "HEADCLERK COMPULSORY SERVICES",
            "WATCHMEN COMPULSORY SERVICES",
            "PEST CONTROL",
            "OSRO ANNEX 18",
        ]:
            inv = mar.get(voucher, [])
            if inv and amt(voucher) > 0:
                entries[voucher] = {"concept": voucher, "amount": amt(voucher),
                                    "tc": tc_port, "invoices": inv}

        # Mandatory Holds — páginas internas de Maritime (compulsory_insp)
        mand_insp   = mar.get("MANDATORY HOLDS INSPECTION", [])
        mand_reinsp = mar.get("MANDATORY HOLDS RE-INSPECTION", [])
        if mand_insp and amt("MANDATORY HOLDS INSPECTION") > 0:
            entries["MANDATORY HOLDS INSPECTION"] = {
                "concept": "MANDATORY HOLDS INSPECTION",
                "amount":  amt("MANDATORY HOLDS INSPECTION"),
                "tc": tc_port, "invoices": mand_insp,
            }
        if mand_reinsp and amt("MANDATORY HOLDS RE-INSPECTION") > 0:
            entries["MANDATORY HOLDS RE-INSPECTION"] = {
                "concept": "MANDATORY HOLDS RE-INSPECTION",
                "amount":  amt("MANDATORY HOLDS RE-INSPECTION"),
                "tc": tc_port, "invoices": mand_reinsp,
            }

        # Full On Hire / BQS Survey
        survey_inv = [(f, None) for f in analysis.get("edi_separovic", [])]
        if survey_inv and amt("FULL ON HIRE / BQS SURVEY") > 0:
            entries["FULL ON HIRE / BQS SURVEY"] = {
                "concept": "FULL ON HIRE / BQS SURVEY",
                "amount":  amt("FULL ON HIRE / BQS SURVEY"),
                "tc": tc_port, "invoices": survey_inv,
            }

        # Navigation Center — standalone o página de Maritime
        nav_mar   = mar.get("NAVIGATION CENTER CONTRIBUTION", [])
        nav_files = [(f, None) for f in analysis.get("centro_nav", [])]
        all_nav   = nav_files + nav_mar
        if all_nav and amt("NAVIGATION CENTER CONTRIBUTION") > 0:
            entries["NAVIGATION CENTER CONTRIBUTION"] = {
                "concept": "NAVIGATION CENTER CONTRIBUTION",
                "amount":  amt("NAVIGATION CENTER CONTRIBUTION"),
                "tc": tc_port, "invoices": all_nav,
            }

        # ── Tax — cada TC tiene su instancia ─────────────────────────────────
        # Se inserta automáticamente como fallback si aparece en la FACB
        tax_amt = amt("TAX ON CREDIT/DEBIT LAW 25.413")
        if tax_amt > 0:
            entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
                "concept": "TAX ON CREDIT/DEBIT LAW 25.413",
                "amount":  tax_amt,
                "tc": tc_port, "invoices": [], "solo": True,
            }

        # ── Toll Dues CARP ───────────────────────────────────────────────────
        carp_inv = [(f, None) for f in analysis.get("carp", [])]
        if carp_inv and amt("TOLL DUES (CARP)") > 0:
            entries["TOLL DUES (CARP)"] = {
                "concept": "TOLL DUES (CARP)",
                "amount":  amt("TOLL DUES (CARP)"),
                "tc": tc_port, "invoices": carp_inv,
            }

        # ── Pilot Launch Transportation River Plate (Glatil USD 4,440) ───────
        glatil_inv = [(f, None) for f in analysis.get("glatil", [])]
        if glatil_inv and amt("PILOT LAUNCH TRANSPORTATION RIVER PLATE") > 0:
            entries["PILOT LAUNCH TRANSPORTATION RIVER PLATE"] = {
                "concept": "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
                "amount":  amt("PILOT LAUNCH TRANSPORTATION RIVER PLATE"),
                "tc": tc_port, "invoices": glatil_inv,
            }

        # ── Toll Dues AGP ────────────────────────────────────────────────────
        agp_inv = [(f, None) for f in analysis.get("agp", [])]
        if agp_inv and amt("TOLL DUES (AGP)") > 0:
            entries["TOLL DUES (AGP)"] = {
                "concept": "TOLL DUES (AGP)",
                "amount":  amt("TOLL DUES (AGP)"),
                "tc": tc_port, "invoices": agp_inv,
            }

        # ── Fallback: líneas de FACB sin voucher asignado ────────────────────
        for concept, amount in line_amounts.items():
            if concept not in entries and amount > 0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept": concept, "amount": amount,
                                    "tc": tc_port, "invoices": []}

        return [entries[v] for v in self.VOUCHER_ORDER if v in entries]

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="agency"),
                    keys[0] if keys else 1407.0)
    def _tc_port(self, a):
        return next((f["tc"] for f in a["facbs"] if f.get("type")=="port_expenses"),
                    self._tc_agency(a))
    def _mar_inv(self, analysis, exclude_mooring_img=True):
        mar_pages = {}
        for m in analysis.get("maritime", []):
            for pg in m["pages"]:
                v, cat = pg.get("voucher"), pg.get("category", "")
                if exclude_mooring_img and cat == "mooring_img": continue
                if v: mar_pages.setdefault(v, []).append((m["filename"], pg["page"]))
        result = {}
        for v, pairs in mar_pages.items():
            merged = {}
            for fname, pg in pairs: merged.setdefault(fname, []).append(pg)
            result[v] = [(f, sorted(set(pgs))) for f, pgs in merged.items()]
        return result

# ══════════════════════════════════════════════════════════════════════════════
#  DETECCIÓN AUTOMÁTICA DE PUERTO
# ══════════════════════════════════════════════════════════════════════════════

def detect_port(analysis):
    """
    Detecta el puerto a partir de los datos del análisis.
    Retorna una instancia del PortConfig correspondiente.
    """
    port_str = (analysis.get("port") or "").upper()

    if "NECOCHEA" in port_str or "QUEQUEN" in port_str:
        return NecocheaPort()
    if "BAHIA BLANCA" in port_str or "BAHÍA BLANCA" in port_str:
        return BahiaBlancaPort()

    if "SAN LORENZO" in port_str or "ARROYO SECO" in port_str or "GRAL. LAGOS" in port_str:
        return SanLorenzoPort()

    # Fallback por proveedores detectados
    if analysis.get("consorcio_quequen") or analysis.get("melluso") or analysis.get("pilotaje"):
        return NecocheaPort()

    return BahiaBlancaPort()





