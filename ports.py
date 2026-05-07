"""
ports.py  —  Configuración multi-puerto para FDA Generator ISA
Un solo archivo — compatible con Render sin necesidad de carpetas.
"""

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
        if mooring:
            entries["MOORING & UNMOORING SERVICES"] = {"concept":"MOORING & UNMOORING SERVICES",
                "amount":amt("MOORING & UNMOORING SERVICES"),"tc":tc_port,"invoices":mooring}
        if analysis.get("puerto_mariel"):
            entries["TOWAGE SERVICES"] = {"concept":"TOWAGE SERVICES","amount":amt("TOWAGE SERVICES"),
                "tc":tc_port,"invoices":[(f,None) for f in analysis["puerto_mariel"]]}
        for v in ["CUSTOM HOUSE EXPENSES","CUSTOM HOUSE PERMANENCE","CUSTOM HOUSE (BUNKERING)",
                  "MIGRATION EXPENSES","SANITARY DUES AND FREE PRATIQUE","GARBAGE COMPULSORY INSPECTION",
                  "WATCHMEN COMPULSORY SERVICES","HEADCLERK COMPULSORY SERVICES"]:
            inv = mar.get(v,[])
            if inv: entries[v] = {"concept":v,"amount":amt(v),"tc":tc_port,"invoices":inv}
        pest = mar.get("PEST CONTROL",[]) + [(f,None) for f in analysis.get("ammoca",[])]
        if pest: entries["PEST CONTROL"] = {"concept":"PEST CONTROL","amount":amt("PEST CONTROL"),"tc":tc_port,"invoices":pest}
        osro = mar.get("OSRO ANNEX 18",[])
        if osro: entries["OSRO ANNEX 18"] = {"concept":"OSRO ANNEX 18","amount":amt("OSRO ANNEX 18"),"tc":tc_port,"invoices":osro}
        entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {"concept":"TAX ON CREDIT/DEBIT LAW 25.413",
            "amount":amt("TAX ON CREDIT/DEBIT LAW 25.413"),"tc":tc_port,"invoices":[],"solo":True}
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
            if inv: entries[v] = {"concept":v,"amount":amt(v),"tc":tc_port,"invoices":inv}
        pest = mar.get("PEST CONTROL",[])
        if pest: entries["PEST CONTROL"] = {"concept":"PEST CONTROL","amount":amt("PEST CONTROL"),"tc":tc_port,"invoices":pest}
        entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {"concept":"TAX ON CREDIT/DEBIT LAW 25.413",
            "amount":amt("TAX ON CREDIT/DEBIT LAW 25.413"),"tc":tc_port,"invoices":[],"solo":True}
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

    # Fallback por proveedores detectados
    if analysis.get("consorcio_quequen") or analysis.get("melluso") or analysis.get("pilotaje"):
        return NecocheaPort()

    return BahiaBlancaPort()

