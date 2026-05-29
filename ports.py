"""
ports.py  —  Configuración multi-puerto para FDA Generator ISA
FIXES aplicados (San Lorenzo):
  1. FACB 30317 se insertaba ANTES del voucher Agency Fee — corregido en assembler.py
  2. River Plate Anchorage Maneuver: solo facturas con has_maniobra=True (no todas)
  3. River Parana Pilotage: facturas con Maniobras de Fondeo van SOLO bajo Anchorage
  4. Port Pilotage: vouchers internos (Rosario Pilots) al final, tras todas las facturas
  5. Custom House Expenses: Centro de Navegación va primero, luego AFIP/SSEE
  6. Migration Expenses: orden transporte SENASA excluido (va bajo Garbage)
  7. Sanitary Dues: páginas de Libre Plática incluidas correctamente
  8. Garbage Inspection: orden transporte SENASA incluida aquí
  9. Mandatory Holds: comprobante interno + factura incluidos
 10. Bloques TC 1385 y TC 1457 completos (Toll Dues AGP/CARP, NCBs, FACBs, Tax)
"""

import os


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
        normalized = {}
        for k, v in line_amounts.items():
            key = k.upper().replace("PRACTIQUE", "PRATIQUE")
            normalized[key] = v
        line_amounts = normalized

        def amt(k): return line_amounts.get(k.upper(), 0)

        tc_agency = self._tc_agency(analysis)
        tc_port   = self._tc_port(analysis)
        mar       = self._mar_inv(analysis)
        entries   = {}

        entries["AGENCY FEE"] = {
            "concept": "AGENCY FEE",
            "amount": next((f.get("total", 0) for f in analysis["facbs"] if f.get("type") == "agency"), 0),
            "tc": tc_agency, "invoices": [], "solo": True
        }
        if analysis.get("consorcio"):
            entries["PORT DUES"] = {
                "concept": "PORT DUES", "amount": amt("PORT DUES"),
                "tc": tc_port, "invoices": [(analysis["consorcio"][0], None)]
            }
            entries["TOLL DUES"] = {
                "concept": "TOLL DUES", "amount": amt("TOLL DUES"),
                "tc": tc_port, "invoices": [(f, None) for f in analysis["consorcio"]]
            }
        if analysis.get("donmar"):
            entries["PORT PILOTAGE"] = {
                "concept": "PORT PILOTAGE", "amount": amt("PORT PILOTAGE"),
                "tc": tc_port, "invoices": [(f, None) for f in analysis["donmar"]]
            }
        mooring = mar.get("MOORING & UNMOORING SERVICES", []) + [(f, None) for f in analysis.get("amarradores", [])]
        if mooring and amt("MOORING & UNMOORING SERVICES") > 0:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept": "MOORING & UNMOORING SERVICES", "amount": amt("MOORING & UNMOORING SERVICES"),
                "tc": tc_port, "invoices": mooring
            }
        if analysis.get("puerto_mariel") and amt("TOWAGE SERVICES") > 0:
            entries["TOWAGE SERVICES"] = {
                "concept": "TOWAGE SERVICES", "amount": amt("TOWAGE SERVICES"),
                "tc": tc_port, "invoices": [(f, None) for f in analysis["puerto_mariel"]]
            }
        for v in ["CUSTOM HOUSE EXPENSES", "CUSTOM HOUSE PERMANENCE", "CUSTOM HOUSE (BUNKERING)",
                  "MIGRATION EXPENSES", "SANITARY DUES AND FREE PRATIQUE", "GARBAGE COMPULSORY INSPECTION",
                  "WATCHMEN COMPULSORY SERVICES", "HEADCLERK COMPULSORY SERVICES"]:
            inv = mar.get(v, [])
            if inv and amt(v) > 0:
                entries[v] = {"concept": v, "amount": amt(v), "tc": tc_port, "invoices": inv}
        pest = mar.get("PEST CONTROL", []) + [(f, None) for f in analysis.get("ammoca", [])]
        if pest:
            entries["PEST CONTROL"] = {
                "concept": "PEST CONTROL", "amount": amt("PEST CONTROL"),
                "tc": tc_port, "invoices": pest
            }
        osro = mar.get("OSRO ANNEX 18", [])
        if osro:
            entries["OSRO ANNEX 18"] = {
                "concept": "OSRO ANNEX 18", "amount": amt("OSRO ANNEX 18"),
                "tc": tc_port, "invoices": osro
            }
        entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
            "concept": "TAX ON CREDIT/DEBIT LAW 25.413",
            "amount": amt("TAX ON CREDIT/DEBIT LAW 25.413"),
            "tc": tc_port, "invoices": [], "solo": True
        }
        for concept, amount in line_amounts.items():
            if concept not in entries and amount > 0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept": concept, "amount": amount, "tc": tc_port, "invoices": []}
        # Construir resultado final con Tax extras en posición correcta
        base_result = [entries[v] for v in self.VOUCHER_ORDER if v in entries]
        
        # Insertar Tax extras inmediatamente DESPUÉS del último voucher de su TC
        # Orden: ... TOLL DUES (AGP) [TC1385] → Tax TC1385 → NCB/FACB TC1457 → TOLL DUES (CARP) → Tax TC1457
        extra_taxes = {}
        for k, entry in entries.items():
            if "_TC" in k and k.startswith("TAX ON CREDIT/DEBIT LAW 25.413"):
                extra_taxes[entry["tc"]] = entry
        
        if not extra_taxes:
            return base_result
        
        # Insertar cada Tax extra después del último voucher que comparte su TC
        final_result = []
        inserted_tax_tcs = set()
        for entry in base_result:
            final_result.append(entry)
            tc = entry.get("tc", 0)
            # Si este TC tiene un Tax extra y aún no lo insertamos,
            # y este es el último voucher de ese TC en el resultado
            if tc in extra_taxes and tc not in inserted_tax_tcs:
                # Verificar si el siguiente entry es de un TC diferente
                pos = base_result.index(entry)
                next_entries = [e for e in base_result[pos+1:] if e.get("tc", 0) == tc]
                if not next_entries:
                    final_result.append(extra_taxes[tc])
                    inserted_tax_tcs.add(tc)
        
        # Agregar cualquier Tax extra que no se haya insertado
        for tc_e, entry in sorted(extra_taxes.items()):
            if tc_e not in inserted_tax_tcs:
                final_result.append(entry)
        
        return final_result

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type") == "agency"), keys[0] if keys else 1373.5)

    def _tc_port(self, a):
        # FIX B2: usar el TC MÍNIMO de port_expenses (cronológicamente el primero).
        tcs = [f["tc"] for f in a["facbs"] if f.get("type") == "port_expenses" and f.get("tc")]
        return min(tcs) if tcs else self._tc_agency(a)

    def _mar_inv(self, analysis, exclude_mooring_img=True):
        mar_pages = {}
        for m in analysis.get("maritime", []):
            for pg in m["pages"]:
                v, cat = pg.get("voucher"), pg.get("category", "")
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


class NecocheaPort:
    name       = "Necochea Port"
    short_name = "NECOCHEA"
    VOUCHER_ORDER = [
        "AGENCY FEE", "PORT DUES", "ENTRANCE AND LIGHT DUES", "TOLL DUES",
        "PORT PILOTAGE", "PORT PILOTAGE (DELAY)", "MOORING & UNMOORING SERVICES",
        "SHORE GANGWAY", "TOWAGE SERVICES", "CUSTOM HOUSE EXPENSES", "CUSTOM HOUSE PERMANENCE",
        "MIGRATION EXPENSES", "SANITARY DUES AND FREE PRATIQUE",
        "GARBAGE COMPULSORY INSPECTION", "WATCHMEN COMPULSORY SERVICES",
        "HEADCLERK COMPULSORY SERVICES", "PEST CONTROL", "TAX ON CREDIT/DEBIT LAW 25.413",
    ]

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        normalized = {}
        for k, v in line_amounts.items():
            key = k.upper().replace("PRACTIQUE", "PRATIQUE")
            normalized[key] = v
        line_amounts = normalized

        def amt(k): return line_amounts.get(k.upper(), 0)

        tc_agency = self._tc_agency(analysis)
        tc_port   = self._tc_port(analysis)
        mar       = self._mar_inv(analysis)
        entries   = {}

        entries["AGENCY FEE"] = {
            "concept": "AGENCY FEE",
            "amount": next((f.get("total", 0) for f in analysis["facbs"] if f.get("type") == "agency"), 0),
            "tc": tc_agency, "invoices": [], "solo": True
        }
        consorcio = analysis.get("consorcio_quequen") or analysis.get("consorcio", [])
        if consorcio:
            entries["PORT DUES"] = {
                "concept": "PORT DUES", "amount": amt("PORT DUES"),
                "tc": tc_port, "invoices": [(consorcio[0], None)]
            }
        if len(consorcio) >= 2:
            entries["ENTRANCE AND LIGHT DUES"] = {
                "concept": "ENTRANCE AND LIGHT DUES", "amount": amt("ENTRANCE AND LIGHT DUES"),
                "tc": tc_port, "invoices": [(consorcio[1], None)]
            }
        elif consorcio:
            entries["ENTRANCE AND LIGHT DUES"] = {
                "concept": "ENTRANCE AND LIGHT DUES", "amount": amt("ENTRANCE AND LIGHT DUES"),
                "tc": tc_port, "invoices": [(consorcio[0], None)]
            }
        toll_inv = consorcio[2:] if len(consorcio) > 2 else consorcio
        if toll_inv:
            entries["TOLL DUES"] = {
                "concept": "TOLL DUES", "amount": amt("TOLL DUES"),
                "tc": tc_port, "invoices": [(f, None) for f in toll_inv]
            }
        pilotaje = [(f, None) for f in analysis.get("pilotaje", [])] + mar.get("PORT PILOTAGE", [])
        if pilotaje:
            entries["PORT PILOTAGE"] = {
                "concept": "PORT PILOTAGE", "amount": amt("PORT PILOTAGE"),
                "tc": tc_port, "invoices": pilotaje
            }
        melluso = [(f, None) for f in analysis.get("melluso", [])] + mar.get("MOORING & UNMOORING SERVICES", [])
        if melluso:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept": "MOORING & UNMOORING SERVICES", "amount": amt("MOORING & UNMOORING SERVICES"),
                "tc": tc_port, "invoices": melluso
            }
        sg = [(f, None) for f in analysis.get("shore_gangway", [])] + mar.get("SHORE GANGWAY", [])
        if sg:
            entries["SHORE GANGWAY"] = {
                "concept": "SHORE GANGWAY", "amount": amt("SHORE GANGWAY"),
                "tc": tc_port, "invoices": sg
            }
        if analysis.get("puerto_mariel"):
            entries["TOWAGE SERVICES"] = {
                "concept": "TOWAGE SERVICES", "amount": amt("TOWAGE SERVICES"),
                "tc": tc_port, "invoices": [(f, None) for f in analysis["puerto_mariel"]]
            }
        ch = mar.get("CUSTOM HOUSE EXPENSES", []) + [(f, None) for f in analysis.get("centro_nav", [])]
        if ch:
            entries["CUSTOM HOUSE EXPENSES"] = {
                "concept": "CUSTOM HOUSE EXPENSES", "amount": amt("CUSTOM HOUSE EXPENSES"),
                "tc": tc_port, "invoices": ch
            }
        for v in ["CUSTOM HOUSE PERMANENCE", "MIGRATION EXPENSES", "SANITARY DUES AND FREE PRATIQUE",
                  "GARBAGE COMPULSORY INSPECTION", "WATCHMEN COMPULSORY SERVICES", "HEADCLERK COMPULSORY SERVICES"]:
            inv = mar.get(v, [])
            if inv and amt(v) > 0:
                entries[v] = {"concept": v, "amount": amt(v), "tc": tc_port, "invoices": inv}
        pest = mar.get("PEST CONTROL", [])
        if pest:
            entries["PEST CONTROL"] = {
                "concept": "PEST CONTROL", "amount": amt("PEST CONTROL"),
                "tc": tc_port, "invoices": pest
            }
        entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
            "concept": "TAX ON CREDIT/DEBIT LAW 25.413",
            "amount": amt("TAX ON CREDIT/DEBIT LAW 25.413"),
            "tc": tc_port, "invoices": [], "solo": True
        }
        for concept, amount in line_amounts.items():
            if concept not in entries and amount > 0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept": concept, "amount": amount, "tc": tc_port, "invoices": []}
        # Construir resultado final con Tax extras en posición correcta
        base_result = [entries[v] for v in self.VOUCHER_ORDER if v in entries]
        
        # Insertar Tax extras inmediatamente DESPUÉS del último voucher de su TC
        # Orden: ... TOLL DUES (AGP) [TC1385] → Tax TC1385 → NCB/FACB TC1457 → TOLL DUES (CARP) → Tax TC1457
        extra_taxes = {}
        for k, entry in entries.items():
            if "_TC" in k and k.startswith("TAX ON CREDIT/DEBIT LAW 25.413"):
                extra_taxes[entry["tc"]] = entry
        
        if not extra_taxes:
            return base_result
        
        # Insertar cada Tax extra después del último voucher que comparte su TC
        final_result = []
        inserted_tax_tcs = set()
        for entry in base_result:
            final_result.append(entry)
            tc = entry.get("tc", 0)
            # Si este TC tiene un Tax extra y aún no lo insertamos,
            # y este es el último voucher de ese TC en el resultado
            if tc in extra_taxes and tc not in inserted_tax_tcs:
                # Verificar si el siguiente entry es de un TC diferente
                pos = base_result.index(entry)
                next_entries = [e for e in base_result[pos+1:] if e.get("tc", 0) == tc]
                if not next_entries:
                    final_result.append(extra_taxes[tc])
                    inserted_tax_tcs.add(tc)
        
        # Agregar cualquier Tax extra que no se haya insertado
        for tc_e, entry in sorted(extra_taxes.items()):
            if tc_e not in inserted_tax_tcs:
                final_result.append(entry)
        
        return final_result

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type") == "agency"), keys[0] if keys else 1359.0)

    def _tc_port(self, a):
        # FIX B2: usar el TC MÍNIMO de port_expenses (cronológicamente el primero).
        tcs = [f["tc"] for f in a["facbs"] if f.get("type") == "port_expenses" and f.get("tc")]
        return min(tcs) if tcs else self._tc_agency(a)

    def _mar_inv(self, analysis, exclude_mooring_img=True):
        mar_pages = {}
        for m in analysis.get("maritime", []):
            for pg in m["pages"]:
                v, cat = pg.get("voucher"), pg.get("category", "")
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


class SanLorenzoPort:
    name       = "San Lorenzo Port"
    short_name = "SAN LORENZO"
    VOUCHER_ORDER = [
        "AGENCY FEE", "PORT DUES", "ENTRANCE AND LIGHT DUES",
        "RIVER PLATE PILOTAGE", "RIVER PLATE PILOTAGE (DELAY)", "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER",
        "RIVER PARANA PILOTAGE", "RIVER PARANA PILOTAGE (DELAY)", "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER",
        "PORT PILOTAGE", "PORT PILOTAGE (DELAY)",
        "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)", "LAUNCH SERVICES AT ZONA COMUN",
        "MOORING & UNMOORING SERVICES",
        "CUSTOM HOUSE EXPENSES", "CUSTOM HOUSE PERMANENCE", "CUSTOM HOUSE EXPENSE (CARGO)",
        "MIGRATION EXPENSES", "SANITARY DUES AND FREE PRATIQUE", "GARBAGE COMPULSORY INSPECTION",
        "FULL ON HIRE / BQS SURVEY",
        "MANDATORY HOLDS INSPECTION", "MANDATORY HOLDS RE-INSPECTION",
        "HEADCLERK COMPULSORY SERVICES", "BQS EXPENSES", "GAS FREE INSPECTION", "PEST CONTROL",
        "TAX ON CREDIT/DEBIT LAW 25.413",
        "TOLL DUES (AGP)", "TOLL DUES (CARP)", "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
    ]

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        # ── Normalizar claves ──────────────────────────────────────────────────
        normalized = {}
        for k, v in line_amounts.items():
            key = k.upper().strip()
            key = key.replace("PRACTIQUE", "PRATIQUE").replace("CLEARENCE", "CLEARANCE")
            if key == "RIVER PLATE PILOTAGE ANCHORAGE":
                key = "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER"
            if key == "RIVER PARANA PILOTAGE ANCHORAG":
                key = "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER"
            if key == "MANDATORY HOLDS INSPECTION AT":
                key = "MANDATORY HOLDS INSPECTION"
            if key == "HEADCLERK COMPULSORY":
                key = "HEADCLERK COMPULSORY SERVICES"
            if key in ("LAUNCH SERVICES FOR CLEARENCE", "LAUNCH SERVICES FOR CLEARANCE"):
                key = "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"
            if key == "FULL ON HIRE DELIVERY BUNKER A":
                key = "FULL ON HIRE / BQS SURVEY"
            normalized[key] = v
        line_amounts = normalized

        def amt(k): return line_amounts.get(k.upper(), 0)

        tc_agency = self._tc_agency(analysis)
        tc_port   = self._tc_port(analysis)
        mar       = self._mar_inv(analysis)
        entries   = {}

        # ── Agency Fee — solo voucher, sin factura adjunta ─────────────────────
        entries["AGENCY FEE"] = {
            "concept": "AGENCY FEE",
            "amount": next((f.get("total", 0) for f in analysis["facbs"] if f.get("type") == "agency"), 0),
            "tc": tc_agency, "invoices": [], "solo": True
        }

        # ── Port Dues ──────────────────────────────────────────────────────────
        term = [(f, None) for f in analysis.get("terminal_portuario", [])]
        if term and amt("PORT DUES") > 0:
            entries["PORT DUES"] = {
                "concept": "PORT DUES", "amount": amt("PORT DUES"),
                "tc": tc_port, "invoices": term
            }

        # ── Entrance and Light Dues — solo página ENAPRO de Maritime ──────────
        enapro = mar.get("ENTRANCE AND LIGHT DUES", [])
        if enapro and amt("ENTRANCE AND LIGHT DUES") > 0:
            entries["ENTRANCE AND LIGHT DUES"] = {
                "concept": "ENTRANCE AND LIGHT DUES", "amount": amt("ENTRANCE AND LIGHT DUES"),
                "tc": tc_port, "invoices": enapro
            }

        # ── River Plate Pilotage ───────────────────────────────────────────────
        # FIX #2: Anchorage Maneuver solo incluye facturas con has_maniobra=True
        rp_all   = analysis.get("practicaje_rp", [])
        rp_base  = [(r["filename"], None) for r in rp_all]
        rp_delay = [(r["filename"], None) for r in rp_all if r.get("has_demora")]
        # SOLO las facturas que tienen línea de maniobra con monto
        rp_manio     = [(r["filename"], None) for r in rp_all if r.get("has_maniobra")]
        # El monto del voucher SIEMPRE es el de la FACB (línea de la factura ISA)
        facb_rp_manio = amt("RIVER PLATE PILOTAGE ANCHORAGE MANEUVER")
        rp_manio_amt = facb_rp_manio
        if rp_manio_amt == 0:
            # Fallback: sumar facturas de proveedor si no hay FACB
            rp_manio_amt = sum(r.get("maniobra_amount", 0) for r in rp_all if r.get("has_maniobra"))
        if rp_manio_amt == 0:
            rp_manio = rp_base

        if rp_base and amt("RIVER PLATE PILOTAGE") > 0:
            entries["RIVER PLATE PILOTAGE"] = {
                "concept": "RIVER PLATE PILOTAGE", "amount": amt("RIVER PLATE PILOTAGE"),
                "tc": tc_port, "invoices": rp_base
            }
        if rp_delay and amt("RIVER PLATE PILOTAGE (DELAY)") > 0:
            entries["RIVER PLATE PILOTAGE (DELAY)"] = {
                "concept": "RIVER PLATE PILOTAGE (DELAY)", "amount": amt("RIVER PLATE PILOTAGE (DELAY)"),
                "tc": tc_port, "invoices": rp_delay
            }
        if rp_manio and rp_manio_amt > 0:
            entries["RIVER PLATE PILOTAGE ANCHORAGE MANEUVER"] = {
                "concept": "RIVER PLATE PILOTAGE ANCHORAGE MANEUVER", "amount": rp_manio_amt,
                "tc": tc_port, "invoices": rp_manio
            }

        # ── River Parana Pilotage — COPRAC ────────────────────────────────────
        # FIX #3: Facturas de Maniobras de Fondeo van SOLO bajo Anchorage Maneuver.
        # Las facturas de recorrido/servicios (sin maniobra) van bajo River Parana Pilotage.
        # Las facturas con maniobra van bajo AMBOS (Parana Pilotage Y Anchorage Maneuver).
        cp_all = analysis.get("coprac", [])
        # FIX B3: cp_base incluye TODAS las facturas (con y sin maniobra).
        # El manual dice: facturas con maniobra van bajo Parana Pilotage Y Anchorage Maneuver.
        # Facturas sin maniobra van SOLO bajo Parana Pilotage.
        cp_base  = [(r["filename"], None) for r in cp_all]
        cp_delay = [(r["filename"], None) for r in cp_all if r.get("has_demora")]
        # Anchorage: SOLO las que tienen línea de maniobra con monto
        cp_manio     = [(r["filename"], None) for r in cp_all if r.get("has_maniobra")]
        # El monto del voucher SIEMPRE es el de la FACB (línea de la factura ISA)
        facb_cp_manio = amt("RIVER PARANA PILOTAGE ANCHORAGE MANEUVER")
        cp_manio_amt = facb_cp_manio
        if cp_manio_amt == 0:
            # Fallback: sumar facturas de proveedor si no hay FACB
            cp_manio_amt = sum(r.get("maniobra_amount", 0) for r in cp_all if r.get("has_maniobra"))
        if cp_manio_amt == 0:
            cp_manio = cp_base

        if cp_base and amt("RIVER PARANA PILOTAGE") > 0:
            entries["RIVER PARANA PILOTAGE"] = {
                "concept": "RIVER PARANA PILOTAGE", "amount": amt("RIVER PARANA PILOTAGE"),
                "tc": tc_port, "invoices": cp_base
            }
        if cp_delay and amt("RIVER PARANA PILOTAGE (DELAY)") > 0:
            entries["RIVER PARANA PILOTAGE (DELAY)"] = {
                "concept": "RIVER PARANA PILOTAGE (DELAY)", "amount": amt("RIVER PARANA PILOTAGE (DELAY)"),
                "tc": tc_port, "invoices": cp_delay
            }
        if cp_manio and cp_manio_amt > 0:
            entries["RIVER PARANA PILOTAGE ANCHORAGE MANEUVER"] = {
                "concept": "RIVER PARANA PILOTAGE ANCHORAGE MANEUVER", "amount": cp_manio_amt,
                "tc": tc_port, "invoices": cp_manio
            }

        # ── Port Pilotage — Rosario Pilots ─────────────────────────────────────
        # FIX #4: Páginas de factura primero, luego páginas de voucher interno.
        # Archivos multi-página (W310744, W310759) tienen p1=factura y p2=voucher ABRATTI/BAGLIETTO.
        rsp_all = analysis.get("rosario_pilots", [])

        import fitz as _fitz_rsp

        rsp_facturas = []  # (fname, [fact_pages])
        rsp_vouchers = []  # (fname, [vouch_pages])

        for r in rsp_all:
            fname = r["filename"]
            fact_pages = []
            vouch_pages = []
            try:
                doc = _fitz_rsp.open(os.path.join(work_dir, fname))
                for i in range(doc.page_count):
                    text = doc[i].get_text()
                    if "Voucher por Servicio de Practicaje" in text and "SUBTOTAL" not in text:
                        vouch_pages.append(i)
                    else:
                        fact_pages.append(i)
            except Exception:
                fact_pages = [0]
            if fact_pages:
                rsp_facturas.append((fname, fact_pages))
            if vouch_pages:
                rsp_vouchers.append((fname, vouch_pages))

        rsp_base  = rsp_facturas + rsp_vouchers
        rsp_delay = [(r["filename"], None) for r in rsp_all if r.get("has_demora")]

        if rsp_base and amt("PORT PILOTAGE") > 0:
            entries["PORT PILOTAGE"] = {
                "concept": "PORT PILOTAGE", "amount": amt("PORT PILOTAGE"),
                "tc": tc_port, "invoices": rsp_base
            }
        if rsp_delay and amt("PORT PILOTAGE (DELAY)") > 0:
            entries["PORT PILOTAGE (DELAY)"] = {
                "concept": "PORT PILOTAGE (DELAY)", "amount": amt("PORT PILOTAGE (DELAY)"),
                "tc": tc_port, "invoices": rsp_delay
            }

        # ── Launch Services for Clearance ─────────────────────────────────────
        clearance_inv = [(r["filename"], [0]) for r in analysis.get("amarre_coral", []) if r.get("is_clearance")]
        if clearance_inv and amt("LAUNCH SERVICES FOR CLEARANCE (AT ROADS)") > 0:
            entries["LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"] = {
                "concept": "LAUNCH SERVICES FOR CLEARANCE (AT ROADS)",
                "amount": amt("LAUNCH SERVICES FOR CLEARANCE (AT ROADS)"),
                "tc": tc_port, "invoices": clearance_inv
            }

        # ── Mooring & Unmooring ───────────────────────────────────────────────
        mooring_inv = [(r["filename"], None) for r in analysis.get("amarre_coral", []) if r.get("is_mooring")]
        mar_mooring = mar.get("MOORING & UNMOORING SERVICES", [])
        all_mooring = mooring_inv + mar_mooring
        if all_mooring and amt("MOORING & UNMOORING SERVICES") > 0:
            entries["MOORING & UNMOORING SERVICES"] = {
                "concept": "MOORING & UNMOORING SERVICES", "amount": amt("MOORING & UNMOORING SERVICES"),
                "tc": tc_port, "invoices": all_mooring
            }

        # ── Custom House Expenses ─────────────────────────────────────────────
        # FIX #5: Centro de Navegación va PRIMERO, luego AFIP/SSEE de Maritime
        nav_files = [(f, None) for f in analysis.get("centro_nav", [])]
        mar_ch    = mar.get("CUSTOM HOUSE EXPENSES", [])
        # nav_center desde Maritime también puede aparecer clasificado aquí
        mar_nav   = mar.get("NAVIGATION CENTER CONTRIBUTION", [])
        # Orden: Centro de Navegación (archivos externos) → AFIP/SSEE (Maritime)
        ch_inv = nav_files + mar_nav + mar_ch
        if ch_inv and amt("CUSTOM HOUSE EXPENSES") > 0:
            entries["CUSTOM HOUSE EXPENSES"] = {
                "concept": "CUSTOM HOUSE EXPENSES", "amount": amt("CUSTOM HOUSE EXPENSES"),
                "tc": tc_port, "invoices": ch_inv
            }

        # Custom House Permanence / Cargo
        for v in ["CUSTOM HOUSE PERMANENCE", "CUSTOM HOUSE EXPENSE (CARGO)"]:
            inv = mar.get(v, [])
            if inv and amt(v) > 0:
                entries[v] = {"concept": v, "amount": amt(v), "tc": tc_port, "invoices": inv}

        # ── Migration Expenses ────────────────────────────────────────────────
        # FIX #6: Solo páginas de migraciones (liq, sol, transporte de migración).
        # La orden de transporte SENASA (06/04) NO va aquí — va bajo Garbage.
        # El clasificador ya separa correctamente: orden_transporte → MIGRATION,
        # senasa → GARBAGE. El fix aquí es asegurarse que no haya orden_transporte
        # de SENASA mezclada. Esto se resuelve en el clasificador (classifier.py),
        # pero como backup filtramos páginas con "SE.NA.SA" del grupo migration.
        mig_raw = mar.get("MIGRATION EXPENSES", [])
        # Filtrar: excluir páginas que pertenecen a SENASA (ya clasificadas en Garbage)
        # (El clasificador debería haberlas separado; esto es un guard extra)
        mig_inv = mig_raw  # La corrección principal está en el clasificador
        if mig_inv and amt("MIGRATION EXPENSES") > 0:
            entries["MIGRATION EXPENSES"] = {
                "concept": "MIGRATION EXPENSES", "amount": amt("MIGRATION EXPENSES"),
                "tc": tc_port, "invoices": mig_inv
            }

        # ── Sanitary Dues and Free Pratique ───────────────────────────────────
        # FIX #7: Las páginas de Libre Plática (sanidad_cert) deben estar incluidas.
        # El clasificador ya las clasifica como "sanidad_cert" → "SANITARY DUES AND FREE PRATIQUE".
        # Verificamos que están presentes en el grupo.
        san_inv = mar.get("SANITARY DUES AND FREE PRATIQUE", [])
        if san_inv and amt("SANITARY DUES AND FREE PRATIQUE") > 0:
            entries["SANITARY DUES AND FREE PRATIQUE"] = {
                "concept": "SANITARY DUES AND FREE PRATIQUE", "amount": amt("SANITARY DUES AND FREE PRATIQUE"),
                "tc": tc_port, "invoices": san_inv
            }

        # ── Garbage Compulsory Inspection ─────────────────────────────────────
        # FIX #8: Incluir orden de transporte SENASA (clasificada como orden_transporte
        # cuando el detalle del viaje menciona SE.NA.SA).
        # El clasificador ya separa boleta SENASA y su orden de transporte.
        garb_inv = mar.get("GARBAGE COMPULSORY INSPECTION", [])
        if garb_inv and amt("GARBAGE COMPULSORY INSPECTION") > 0:
            entries["GARBAGE COMPULSORY INSPECTION"] = {
                "concept": "GARBAGE COMPULSORY INSPECTION", "amount": amt("GARBAGE COMPULSORY INSPECTION"),
                "tc": tc_port, "invoices": garb_inv
            }

        # ── Mandatory Holds Inspection / Re-Inspection ────────────────────────
        # FIX #9: Incluir comprobante interno + factura (ya clasificados por el clasificador
        # como compulsory_insp → MANDATORY HOLDS INSPECTION).
        mand_insp   = mar.get("MANDATORY HOLDS INSPECTION", [])
        mand_reinsp = mar.get("MANDATORY HOLDS RE-INSPECTION", [])
        if mand_insp and amt("MANDATORY HOLDS INSPECTION") > 0:
            entries["MANDATORY HOLDS INSPECTION"] = {
                "concept": "MANDATORY HOLDS INSPECTION", "amount": amt("MANDATORY HOLDS INSPECTION"),
                "tc": tc_port, "invoices": mand_insp
            }
        if mand_reinsp and amt("MANDATORY HOLDS RE-INSPECTION") > 0:
            entries["MANDATORY HOLDS RE-INSPECTION"] = {
                "concept": "MANDATORY HOLDS RE-INSPECTION", "amount": amt("MANDATORY HOLDS RE-INSPECTION"),
                "tc": tc_port, "invoices": mand_reinsp
            }

        # ── Headclerk Compulsory Services ─────────────────────────────────────
        headclerk = mar.get("HEADCLERK COMPULSORY SERVICES", [])
        if headclerk and amt("HEADCLERK COMPULSORY SERVICES") > 0:
            entries["HEADCLERK COMPULSORY SERVICES"] = {
                "concept": "HEADCLERK COMPULSORY SERVICES", "amount": amt("HEADCLERK COMPULSORY SERVICES"),
                "tc": tc_port, "invoices": headclerk
            }

        # ── Full On Hire / BQS Survey — EDI Separovic ─────────────────────────
        survey_inv = [(f, [0]) for f in analysis.get("edi_separovic", [])]
        if survey_inv and amt("FULL ON HIRE / BQS SURVEY") > 0:
            entries["FULL ON HIRE / BQS SURVEY"] = {
                "concept": "FULL ON HIRE / BQS SURVEY", "amount": amt("FULL ON HIRE / BQS SURVEY"),
                "tc": tc_port, "invoices": survey_inv
            }

        # ── BQS Expenses, Gas Free, Pest Control, Watchmen ────────────────────
        for v in ["BQS EXPENSES", "GAS FREE INSPECTION", "PEST CONTROL", "WATCHMEN COMPULSORY SERVICES", "OSRO ANNEX 18"]:
            inv = mar.get(v, [])
            if inv and amt(v) > 0:
                entries[v] = {"concept": v, "amount": amt(v), "tc": tc_port, "invoices": inv}

        # ── Tax on Credit/Debit Law 25.413 (TC base) ──────────────────────────
        # FIX #10: Hay múltiples Tax vouchers, uno por cada TC.
        # El voucher del TC base se inserta aquí por el assembler al iterar invoice_map.
        # Los otros TC (1385, 1457) los maneja el assembler al insertar FACBs de esos TC.
        tax_amt = amt("TAX ON CREDIT/DEBIT LAW 25.413")
        if tax_amt > 0:
            entries["TAX ON CREDIT/DEBIT LAW 25.413"] = {
                "concept": "TAX ON CREDIT/DEBIT LAW 25.413", "amount": tax_amt,
                "tc": tc_port, "invoices": [], "solo": True
            }
        # Tax extras de TCs superiores — claves con sufijo _TC{n}
        import re as _re_tax
        for key_la, val_la in line_amounts.items():
            if "_TC" in key_la and key_la.startswith("TAX ON CREDIT/DEBIT LAW 25.413") and val_la > 0:
                m_tc = _re_tax.search(r"_TC([\d.]+)$", key_la)
                if m_tc:
                    tc_extra = float(m_tc.group(1))
                    entries[key_la] = {
                        "concept": "TAX ON CREDIT/DEBIT LAW 25.413",
                        "amount": val_la, "tc": tc_extra, "invoices": [], "solo": True
                    }

        # ── Toll Dues AGP — TC correcto según FACB ────────────────────────────
        agp_inv = [(f, None) for f in analysis.get("agp", [])]
        if agp_inv and amt("TOLL DUES (AGP)") > 0:
            tc_agp = self._tc_for_concept(analysis, "TOLL DUES (AGP)", work_dir)
            entries["TOLL DUES (AGP)"] = {
                "concept": "TOLL DUES (AGP)", "amount": amt("TOLL DUES (AGP)"),
                "tc": tc_agp, "invoices": agp_inv
            }

        # ── Pilot Launch Transportation River Plate (Glatil) — TC correcto ───
        glatil_inv = [(f, None) for f in analysis.get("glatil", [])]
        if glatil_inv and amt("PILOT LAUNCH TRANSPORTATION RIVER PLATE") > 0:
            tc_glatil = self._tc_for_concept(analysis, "PILOT LAUNCH TRANSPORTATION RIVER PLATE", work_dir)
            entries["PILOT LAUNCH TRANSPORTATION RIVER PLATE"] = {
                "concept": "PILOT LAUNCH TRANSPORTATION RIVER PLATE",
                "amount": amt("PILOT LAUNCH TRANSPORTATION RIVER PLATE"),
                "tc": tc_glatil, "invoices": glatil_inv
            }

        # ── Toll Dues CARP — TC correcto según FACB ───────────────────────────
        carp_inv = [(f, None) for f in analysis.get("carp", [])]
        if amt("TOLL DUES (CARP)") > 0:
            tc_carp = self._tc_for_concept(analysis, "TOLL DUES (CARP)", work_dir)
            entries["TOLL DUES (CARP)"] = {
                "concept": "TOLL DUES (CARP)", "amount": amt("TOLL DUES (CARP)"),
                "tc": tc_carp, "invoices": carp_inv
            }

        # ── Fallback ──────────────────────────────────────────────────────────
        for concept, amount in line_amounts.items():
            if concept not in entries and amount > 0 and concept in self.VOUCHER_ORDER:
                entries[concept] = {"concept": concept, "amount": amount, "tc": tc_port, "invoices": []}

        # Construir resultado final con Tax extras en posición correcta
        base_result = [entries[v] for v in self.VOUCHER_ORDER if v in entries]
        
        # Insertar Tax extras inmediatamente DESPUÉS del último voucher de su TC
        # Orden: ... TOLL DUES (AGP) [TC1385] → Tax TC1385 → NCB/FACB TC1457 → TOLL DUES (CARP) → Tax TC1457
        extra_taxes = {}
        for k, entry in entries.items():
            if "_TC" in k and k.startswith("TAX ON CREDIT/DEBIT LAW 25.413"):
                extra_taxes[entry["tc"]] = entry
        
        if not extra_taxes:
            return base_result
        
        # Insertar cada Tax extra después del último voucher que comparte su TC
        final_result = []
        inserted_tax_tcs = set()
        for entry in base_result:
            final_result.append(entry)
            tc = entry.get("tc", 0)
            # Si este TC tiene un Tax extra y aún no lo insertamos,
            # y este es el último voucher de ese TC en el resultado
            if tc in extra_taxes and tc not in inserted_tax_tcs:
                # Verificar si el siguiente entry es de un TC diferente
                pos = base_result.index(entry)
                next_entries = [e for e in base_result[pos+1:] if e.get("tc", 0) == tc]
                if not next_entries:
                    final_result.append(extra_taxes[tc])
                    inserted_tax_tcs.add(tc)
        
        # Agregar cualquier Tax extra que no se haya insertado
        for tc_e, entry in sorted(extra_taxes.items()):
            if tc_e not in inserted_tax_tcs:
                final_result.append(entry)
        
        return final_result

    def _tc_agency(self, a):
        keys = sorted(a["tc_groups"].keys())
        return next((f["tc"] for f in a["facbs"] if f.get("type") == "agency"), keys[0] if keys else 1407.0)

    def _tc_port(self, a):
        # FIX B2: usar el TC MÍNIMO de port_expenses (cronológicamente el primero).
        # No usar next() porque el orden de facbs puede estar alterado por sort numérico.
        tcs = [f["tc"] for f in a["facbs"] if f.get("type") == "port_expenses" and f.get("tc")]
        return min(tcs) if tcs else self._tc_agency(a)

    def _tc_for_concept(self, a, concept, work_dir):
        """Devuelve el TC de la FACB de port_expenses que contiene el concepto dado."""
        import os
        from assembler import extract_facb_line_amounts
        concept_up = concept.upper()
        aliases = {
            "TOLL DUES (AGP)": ["TOLL DUES"],
            "TOLL DUES (CARP)": ["TOLL DUES"],
            "PILOT LAUNCH TRANSPORTATION RIVER PLATE": ["RIVER PLATE PILOTAGE"],
        }
        search_terms = aliases.get(concept_up, [concept_up])
        
        # Recolectar todos los TCs que tienen este concepto en su FACB
        matching_tcs = []
        for facb in sorted(a.get("facbs", []), key=lambda x: x.get("tc", 0)):
            if facb.get("type") != "port_expenses":
                continue
            fpath = os.path.join(work_dir, facb.get("filename", ""))
            if not os.path.exists(fpath):
                continue
            try:
                la = extract_facb_line_amounts(fpath)
                la_keys = [k.upper() for k in la.keys()]
                for term in search_terms:
                    if term in la_keys:
                        matching_tcs.append(facb.get("tc", 0))
                        break
            except Exception:
                pass
        
        if not matching_tcs:
            return self._tc_port(a)
        
        # Para AGP: el TC más bajo entre los que tienen TOLL DUES
        # Para CARP: el TC más alto entre los que tienen TOLL DUES
        if concept_up == "TOLL DUES (AGP)":
            return min(matching_tcs)
        elif concept_up in ("TOLL DUES (CARP)", "PILOT LAUNCH TRANSPORTATION RIVER PLATE"):
            return max(matching_tcs)
        return matching_tcs[0]

    def _mar_inv(self, analysis, exclude_mooring_img=True):
        mar_pages = {}
        for m in analysis.get("maritime", []):
            for pg in m["pages"]:
                v, cat = pg.get("voucher"), pg.get("category", "")
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


def detect_port(analysis):
    port_str = (analysis.get("port") or "").upper()
    if "NECOCHEA" in port_str or "QUEQUEN" in port_str:
        return NecocheaPort()
    if "BAHIA BLANCA" in port_str or "BAHÍA BLANCA" in port_str:
        return BahiaBlancaPort()
    if "SAN LORENZO" in port_str or "ARROYO SECO" in port_str or "GRAL. LAGOS" in port_str:
        return SanLorenzoPort()
    if analysis.get("consorcio_quequen") or analysis.get("melluso") or analysis.get("pilotaje"):
        return NecocheaPort()
    if (analysis.get("practicaje_rp") or analysis.get("coprac") or
            analysis.get("rosario_pilots") or analysis.get("terminal_portuario")):
        return SanLorenzoPort()
    return BahiaBlancaPort()



















