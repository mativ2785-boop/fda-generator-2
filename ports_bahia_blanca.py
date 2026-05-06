"""
ports/bahia_blanca.py
Configuración del puerto de Bahia Blanca.
"""

from .base import PortConfig


class BahiaBlancaPort(PortConfig):

    name       = "Bahia Blanca Port"
    short_name = "BAHIA BLANCA"

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

    PROVIDER_SIGNATURES = {
        "consorcio": [
            ["Consorcio de Gestión del Puerto de Bahia Blanca"],
            ["CONSORCIO DE GESTION DEL PUERTO DE BAHIA BLANCA"],
            ["USO DE PUERTO ULTRAMAR"],
        ],
        "donmar": [
            ["DONMAR S.A."],
            ["Servicio de Practicaje", "BOYA 11"],
        ],
        "puerto_mariel": [
            ["PUERTO MARIEL"],
            ["ARGENTINA TOWAGE"],
            ["Towage Service", "COOPOR"],
        ],
        "maritime": [
            ["MARITIME SHIPPING AGENCY"],
            ["SUCURSAL: Bahía Blanca", "FACT CRED ELECT"],
        ],
        "amarradores": [
            ["AMARRADORES DEL PUERTO DE BAHIA BLANCA"],
        ],
        "ammoca": [
            ["AMMOCA S.A."],
        ],
        "centro_nav": [
            ["Centro de Navegación Asociación Civil"],
            ["cnav.org.ar"],
        ],
    }

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        """Construye el invoice_map para Bahia Blanca."""

        def amt(key):
            return line_amounts.get(key.upper(), 0)

        tc_port   = self._tc_port(analysis)
        tc_agency = self._tc_agency(analysis)

        # Páginas Maritime agrupadas por voucher (excluye mooring_img)
        mar_inv = self._mar_inv(analysis, exclude_mooring_img=True)

        entries = {}

        # Agency Fee
        entries["AGENCY FEE"] = {
            "concept":  "AGENCY FEE",
            "amount":   next((f.get("total",0) for f in analysis["facbs"]
                              if f.get("type")=="agency"), 0),
            "tc":       tc_agency,
            "invoices": [],
            "solo":     True,
        }

        # Port Dues — primera factura del Consorcio
        if analysis.get("consorcio"):
            entries["PORT DUES"] = {
                "concept":  "PORT DUES",
                "amount":   amt("PORT DUES"),
                "tc":       tc_port,
                "invoices": [(analysis["consorcio"][0], None)],
            }

        # Toll Dues — todas las facturas del Consorcio
        if analysis.get("consorcio"):
            entries["TOLL DUES"] = {
                "concept":  "TOLL DUES",
                "amount":   amt("TOLL DUES"),
                "tc":       tc_port,
                "invoices": [(f, None) for f in analysis["consorcio"]],
            }

        # Port Pilotage — Donmar
        if analysis.get("donmar"):
            entries["PORT PILOTAGE"] = {
                "concept":  "PORT PILOTAGE",
                "amount":   amt("PORT PILOTAGE"),
                "tc":       tc_port,
                "invoices": [(f, None) for f in analysis["donmar"]],
            }

        # Mooring — solo página de Amarradores de Maritime + externos
        mooring = mar_inv.get("MOORING & UNMOORING SERVICES", [])
        ama     = [(f, None) for f in analysis.get("amarradores", [])]
        if mooring or ama:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept":  "MOORING & UNMOORING SERVICES",
                "amount":   amt("MOORING & UNMOORING SERVICES"),
                "tc":       tc_port,
                "invoices": mooring + ama,
            }

        # Towage — Puerto Mariel
        if analysis.get("puerto_mariel"):
            entries["TOWAGE SERVICES"] = {
                "concept":  "TOWAGE SERVICES",
                "amount":   amt("TOWAGE SERVICES"),
                "tc":       tc_port,
                "invoices": [(f, None) for f in analysis["puerto_mariel"]],
            }

        # Vouchers de Maritime
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
            inv = mar_inv.get(voucher, [])
            if inv:
                entries[voucher] = {
                    "concept":  voucher,
                    "amount":   amt(voucher),
                    "tc":       tc_port,
                    "invoices": inv,
                }

        # Pest Control
        pest = mar_inv.get("PEST CONTROL", []) + [(f, None) for f in analysis.get("ammoca", [])]
        if pest:
            entries["PEST CONTROL"] = {
                "concept":  "PEST CONTROL",
                "amount":   amt("PEST CONTROL"),
                "tc":       tc_port,
                "invoices": pest,
            }

        # OSRO
        osro = mar_inv.get("OSRO ANNEX 18", [])
        if osro:
            entries["OSRO ANNEX 18"] = {
                "concept":  "OSRO ANNEX 18",
                "amount":   amt("OSRO ANNEX 18"),
                "tc":       tc_port,
                "invoices": osro,
            }

        # Tax — siempre último
        entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
            "concept":  "TAX ON CREDIT/DEBIT LAW 25.413",
            "amount":   amt("TAX ON CREDIT/DEBIT LAW 25.413"),
            "tc":       tc_port,
            "invoices": [],
            "solo":     True,
        }

        return [entries[v] for v in self.VOUCHER_ORDER if v in entries]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _tc_agency(self, analysis):
        keys = sorted(analysis["tc_groups"].keys())
        return next((f["tc"] for f in analysis["facbs"] if f.get("type")=="agency"),
                    keys[0] if keys else 1373.5)

    def _tc_port(self, analysis):
        keys = sorted(analysis["tc_groups"].keys())
        return next((f["tc"] for f in analysis["facbs"] if f.get("type")=="port_expenses"),
                    self._tc_agency(analysis))

    def _mar_inv(self, analysis, exclude_mooring_img=True):
        """Agrupa páginas Maritime por voucher → [(filename, [pages])]."""
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
