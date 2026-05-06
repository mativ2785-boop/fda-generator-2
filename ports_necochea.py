"""
ports/necochea.py
Configuración del puerto de Necochea / Quequén.

Diferencias vs Bahia Blanca:
  - Consorcio Puerto Quequén (no BB)
  - ENTRANCE AND LIGHT DUES existe (sí en Necochea)
  - Pilotaje: Meyer Arana (no Donmar)
  - Mooring: Melluso S.A. (no Amarradores BB)
  - SHORE GANGWAY existe (nuevo voucher)
  - Sin TOWAGE SERVICES habitualmente
  - Sin PERMANENCE DUES habitualmente
  - Sin OSRO ANNEX 18 habitualmente
"""

from .base import PortConfig


class NecocheaPort(PortConfig):

    name       = "Necochea Port"
    short_name = "NECOCHEA"

    VOUCHER_ORDER = [
        "AGENCY FEE",
        "PORT DUES",
        "ENTRANCE AND LIGHT DUES",
        "TOLL DUES",
        "PORT PILOTAGE",
        "PORT PILOTAGE (DELAY)",
        "MOORING & UNMOORING SERVICES",
        "SHORE GANGWAY",
        "CUSTOM HOUSE EXPENSES",
        "CUSTOM HOUSE PERMANENCE",
        "MIGRATION EXPENSES",
        "SANITARY DUES AND FREE PRATIQUE",
        "GARBAGE COMPULSORY INSPECTION",
        "WATCHMEN COMPULSORY SERVICES",
        "HEADCLERK COMPULSORY SERVICES",
        "PEST CONTROL",
        "TAX ON CREDIT/DEBIT LAW 25.413",
    ]

    PROVIDER_SIGNATURES = {
        # Consorcio Puerto Quequén — Port Dues, Entrance & Light, Toll Dues
        "consorcio": [
            ["Consorcio de Gestión del Puerto Quequén"],
            ["CONSORCIO DE GESTION DEL PUERTO QUEQUEN"],
            ["Puerto Quequén", "Av. Juan de Garay"],
            ["30-66634948-9"],    # CUIT del Consorcio Quequén
        ],
        # Meyer Arana — Port Pilotage
        "pilotaje": [
            ["MEYER", "ARANA"],
            ["MEYER  ARANA"],
            ["Necochea, Buenos Aires", "Período Facturado"],
        ],
        # Melluso S.A. — Mooring & Unmooring
        "melluso": [
            ["MELLUSO S.A."],
            ["MELLUSO"],
            ["SERVICIO DE LANCHAS Y AMARRADORES PUERTO QUEQUEN"],
        ],
        # Shore Gangway provider (empresa sin nombre fijo — detectar por contenido)
        "shore_gangway": [
            ["SHORE GANGWAY"],
            ["30716643685"],    # CUIT del proveedor de Shore Gangway
        ],
        # Maritime Shipping Agency
        "maritime": [
            ["MARITIME SHIPPING AGENCY"],
        ],
        # Centro de Navegación
        "centro_nav": [
            ["Centro de Navegación Asociación Civil"],
            ["cnav.org.ar"],
        ],
    }

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        """Construye el invoice_map para Necochea."""

        def amt(key):
            return line_amounts.get(key.upper(), 0)

        tc_port   = self._tc_port(analysis)
        tc_agency = self._tc_agency(analysis)

        # Páginas Maritime agrupadas por voucher
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

        # Port Dues — primera factura del Consorcio Quequén
        if analysis.get("consorcio"):
            entries["PORT DUES"] = {
                "concept":  "PORT DUES",
                "amount":   amt("PORT DUES"),
                "tc":       tc_port,
                "invoices": [(analysis["consorcio"][0], None)],
            }

        # Entrance and Light Dues — segunda factura del Consorcio Quequén
        if len(analysis.get("consorcio", [])) >= 2:
            entries["ENTRANCE AND LIGHT DUES"] = {
                "concept":  "ENTRANCE AND LIGHT DUES",
                "amount":   amt("ENTRANCE AND LIGHT DUES"),
                "tc":       tc_port,
                "invoices": [(analysis["consorcio"][1], None)],
            }
        elif analysis.get("consorcio"):
            # Si solo hay una factura del Consorcio, igual agrego el voucher
            # (la misma factura puede contener ambos conceptos)
            entries["ENTRANCE AND LIGHT DUES"] = {
                "concept":  "ENTRANCE AND LIGHT DUES",
                "amount":   amt("ENTRANCE AND LIGHT DUES"),
                "tc":       tc_port,
                "invoices": [(analysis["consorcio"][0], None)],
            }

        # Toll Dues — tercera factura del Consorcio (o todas)
        if analysis.get("consorcio"):
            toll_inv = analysis["consorcio"][2:] if len(analysis["consorcio"]) > 2 \
                       else analysis["consorcio"]
            entries["TOLL DUES"] = {
                "concept":  "TOLL DUES",
                "amount":   amt("TOLL DUES"),
                "tc":       tc_port,
                "invoices": [(f, None) for f in toll_inv],
            }

        # Port Pilotage — Meyer Arana (archivo separado O páginas dentro de Maritime)
        pilotaje_files = [(f, None) for f in analysis.get("pilotaje", [])]
        pilotaje_mar   = mar_inv.get("PORT PILOTAGE", [])
        if pilotaje_files or pilotaje_mar:
            entries["PORT PILOTAGE"] = {
                "concept":  "PORT PILOTAGE",
                "amount":   amt("PORT PILOTAGE"),
                "tc":       tc_port,
                "invoices": pilotaje_files + pilotaje_mar,
            }

        # Mooring — Melluso S.A. (archivo separado O páginas dentro de Maritime)
        melluso_files = [(f, None) for f in analysis.get("melluso", [])]
        melluso_mar   = mar_inv.get("MOORING & UNMOORING SERVICES", [])
        # También páginas de amarradores dentro de Maritime
        if melluso_files or melluso_mar:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept":  "MOORING & UNMOORING SERVICES",
                "amount":   amt("MOORING & UNMOORING SERVICES"),
                "tc":       tc_port,
                "invoices": melluso_files + melluso_mar,
            }

        # Shore Gangway — archivo separado O página dentro de Maritime
        sg_files = [(f, None) for f in analysis.get("shore_gangway", [])]
        sg_mar   = mar_inv.get("SHORE GANGWAY", [])
        if sg_files or sg_mar:
            entries["SHORE GANGWAY"] = {
                "concept":  "SHORE GANGWAY",
                "amount":   amt("SHORE GANGWAY"),
                "tc":       tc_port,
                "invoices": sg_files + sg_mar,
            }

        # Custom House Expenses — AFIP + SE inward + Centro de Navegación
        ch_inv = mar_inv.get("CUSTOM HOUSE EXPENSES", [])
        cnav   = [(f, None) for f in analysis.get("centro_nav", [])]
        if ch_inv or cnav:
            entries["CUSTOM HOUSE EXPENSES"] = {
                "concept":  "CUSTOM HOUSE EXPENSES",
                "amount":   amt("CUSTOM HOUSE EXPENSES"),
                "tc":       tc_port,
                "invoices": ch_inv + cnav,
            }

        # Vouchers restantes de Maritime
        for voucher in [
            "CUSTOM HOUSE PERMANENCE",
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
        pest = mar_inv.get("PEST CONTROL", [])
        if pest:
            entries["PEST CONTROL"] = {
                "concept":  "PEST CONTROL",
                "amount":   amt("PEST CONTROL"),
                "tc":       tc_port,
                "invoices": pest,
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

    # ── Helpers (heredados de BB con mínimos cambios) ─────────────────────────

    def _tc_agency(self, analysis):
        keys = sorted(analysis["tc_groups"].keys())
        return next((f["tc"] for f in analysis["facbs"] if f.get("type")=="agency"),
                    keys[0] if keys else 1359.0)

    def _tc_port(self, analysis):
        keys = sorted(analysis["tc_groups"].keys())
        return next((f["tc"] for f in analysis["facbs"] if f.get("type")=="port_expenses"),
                    self._tc_agency(analysis))

    def _mar_inv(self, analysis, exclude_mooring_img=True):
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
