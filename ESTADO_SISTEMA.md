# ISA FDA GENERATOR — Estado completo Jun 2026

## Repositorio
- **URL**: https://github.com/mativ2785-boop/fda-generator-2
- **Token**: [TOKEN_EN_MEMORIA]
- **Deploy**: Render.com (auto-deploy desde main)

## Archivos principales (estado sincronizado Jun 2026)
| Archivo | Líneas | Rol |
|---|---|---|
| `classifier.py` | 1181 | Clasifica cada PDF del ZIP (proveedor, tipo, páginas Maritime) |
| `assembler.py` | 671 | Ensambla el PDF final, genera vouchers ISA y sumario |
| `ports.py` | 515 | Mapea conceptos FACB → comprobantes de proveedores |
| `app.py` | 620 | Flask API (upload ZIP → analyze → generate) |
| `build_fda.py` | 283 | Script CLI de generación |
| `generate_vouchers.py` | 136 | Genera los vouchers ISA en PDF |
| `compress_pdf.py` | 122 | Comprime el PDF final |

---

## PRINCIPIO FUNDAMENTAL
**Las FACBs ISA son la fuente de verdad del orden y cantidad de vouchers.**
- Cada línea de la FACB → 1 voucher ISA + 1 comprobante de proveedor
- El orden de los vouchers = el orden de las líneas en las FACBs
- AGENCY FEE tiene FACB y voucher pero sin comprobante de proveedor

---

## Orden del FDA San Lorenzo

```
SUMARIO
SOF
BNA (tipo de cambio de la FACB Agency Fee)
NCBs (todas, orden TC descendente)
FACB Agency Fee → VOUCHER AGENCY FEE (sin comprobante)

--- para cada FACB port_expenses, ordenadas por grupo: ---

GRUPO 0 — gastos de puerto base (PORT DUES, ENTRANCE, PILOTAJE, etc.)
  FACB port_base (TC base)
  → VOUCHER PORT DUES + Terminal portuario
  → VOUCHER ENTRANCE AND LIGHT DUES + ENAPRO (Maritime)
  → VOUCHER RIVER PLATE PILOTAGE + Ripla (p1)
  → VOUCHER RIVER PLATE PILOTAGE (DELAY) + Ripla con demora
  → VOUCHER RIVER PLATE PILOTAGE ANCHORAGE MANEUVER + Ripla con maniobra
  → VOUCHER RIVER PARANA PILOTAGE + COPRAC/Multipar
  → VOUCHER RIVER PARANA PILOTAGE (DELAY)
  → VOUCHER RIVER PARANA PILOTAGE ANCHORAGE MANEUVER
  → VOUCHER PORT PILOTAGE + Coop Practicos del Parana
  → VOUCHER PORT PILOTAGE (DELAY)
  → VOUCHER LAUNCH SERVICES FOR CLEARANCE + amarre (is_clearance)
  → VOUCHER MOORING & UNMOORING SERVICES + amarre (is_mooring)
  → VOUCHER CUSTOM HOUSE EXPENSES + Centro Nav + Maritime AFIP/SSEE
  → VOUCHER COAST GUARD EXPENSES + Maritime
  → VOUCHER MIGRATION EXPENSES + Maritime migration
  → VOUCHER SANITARY DUES AND FREE PRATIQUE + Maritime sanidad
  → VOUCHER GARBAGE COMPULSORY INSPECTION + SENASA + orden transporte SENASA
  → VOUCHER MANDATORY HOLDS INSPECTION + Maritime
  → VOUCHER HEADCLERK COMPULSORY SERVICES + Maritime
  → VOUCHER TAX ON CREDIT/DEBIT LAW 25.413 (sin comprobante)

GRUPO 1 — TOLL DUES (CARP) y/o PILOT LAUNCH (Glatil)
  FACB TC_carp/pilot
  BNA (si TC diferente al base)
  → VOUCHER TOLL DUES (CARP) + factura CARP
  → VOUCHER PILOT LAUNCH + Glatil USD 4,440 (nunca 5234.80 ni 6154.80)
  → VOUCHER TAX (sin comprobante)

GRUPO 2 — TOLL DUES (AGP) — siempre último
  FACB TC_agp
  BNA (si TC diferente)
  → VOUCHER TOLL DUES (AGP) + factura(s) AGP
  → VOUCHER TAX (sin comprobante)
```

---

## Orden del FDA Bahía Blanca

```
SUMARIO → SOF → BNA → NCBs → FACB Agency → VOUCHER AGENCY FEE →
FACB port_exp → VOUCHER PORT DUES (Consorcio) → PERMANENCE DUES →
TOLL DUES → PORT PILOTAGE (Donmar) → MOORING → TOWAGE (Puerto Mariel) →
CUSTOM HOUSE (despacho + Maritime AFIP + Centro Nav) → MIGRATION →
SANITARY → GARBAGE → HEADCLERK → PEST CONTROL → OSRO ANNEX 18 →
CUSTOM HOUSE BUNKERING → TAX 25.413
```

---

## Lógica AGP vs CARP (fix Jun 2026)

El TC mínimo se calcula **solo entre las FACBs que tienen TOLL DUES**,
no entre todas las FACBs (la de gastos de puerto tiene TC más bajo y confundía el cálculo).

```python
toll_tcs = [tc de FACBs que tienen "TOLL DUES" en sus líneas]
TC mínimo de toll_tcs → TOLL DUES (AGP)  # grupo 2, último
Resto                 → TOLL DUES (CARP) # grupo 1, antes de AGP
```

Ejemplo LASKARO S:
- FACB 30317 TC 1345 — PORT DUES, ENTRANCE, PILOTAJE... (grupo 0)
- FACB 30318 TC 1385 — TOLL DUES → AGP (min de toll_tcs=[1385,1457])
- FACB 30319 TC 1457 — TOLL DUES + RIVER PLATE → CARP + Glatil

---

## Clasificación de amarradores (por contenido)

**LAUNCH SERVICES FOR CLEARANCE (AT ROADS):**
- EMBARKING/DISEMBARKING INSPECTORS AND AGENCY
- AT ROADS FOR INWARD / AT ROADS FOR OUTWARD
- BOAT SERVICE AT ROADS

**MOORING & UNMOORING SERVICES:**
- MOORING, UNMOORING, AMARRE, DESAMARRE
- BOAT SERVICE/PEOPLE FOR MOORING (~USD 11,000)

---

## Deduplicación de facturas

| Caso | Regla |
|---|---|
| COPRAC 2 páginas idénticas | `_only_original` → solo p0 |
| Amarre Coral ORIGINAL+DUP+TRIP | `_only_original` detecta DUPLICADO → solo p0 |
| Plate Amarres p1(texto)+p2(imagen) | p1 tiene ORIGINAL + p2 sin texto → solo p0 |
| 2 archivos mismo número de factura | `_dedup_by_invoice_number` → solo el primero |

---

## Clasificación páginas Maritime

| Categoría | Voucher | Keywords |
|---|---|---|
| `afip_lman` | CUSTOM HOUSE | LMAN + AFIP |
| `se_inward` | CUSTOM HOUSE | SOLICITUD HABILITACION + FEVA/ENTRADA |
| `enapro` | ENTRANCE AND LIGHT DUES | Ente Administrador Puerto Rosario |
| `migraciones_liq` | MIGRATION | Migraciones + quincena |
| `migraciones_sol` | MIGRATION | Servicios Marítimos y Fluviales + Solicitud |
| `orden_transporte` | MIGRATION | ORDEN DE TRANSPORTE + MIGRATION OFFICE |
| `orden_transporte_senasa` | GARBAGE | ORDEN DE TRANSPORTE + SE.NA.SA OFFICE |
| `orden_transporte_sanidad` | SANITARY | ORDEN DE TRANSPORTE + FREE PRATIQUE + SANITARY |
| `sanidad_cert` | SANITARY | Certificado de Libre Plática / FREE PRACTIQUE |
| `sanidad_transf` | SANITARY | MINISTERIO DE SALUD |
| `senasa` | GARBAGE | Barreras Sanitarias + BOLETA/ARANCEL/Regional |
| `compulsory_insp` | MANDATORY HOLDS | COMPULSORY INSPECTION BY PRIVATE SURVEYORS |
| `headclerk_break` | HEADCLERK | HEAD CLERK + Breakdown |
| `coast_guard` | COAST GUARD | PREFECTURA NAVAL / SEÑOR JEFE |
| `skip` | — | Carátula, DA, BNA, Service Certificate |

**SENASA** rescue: `is_duplicate_page` se evita si la página contiene
"BARRERAS SANITARIAS" o "BOLETA REQUERIDO/ARANCEL".

---

## Detección de maniobra en Ripla (detect_pilotaje_flags)

Formatos soportados:
- `USD 2,520.00` (estándar)
- `USD 2.520,00` (europeo: punto=miles, coma=decimal — LASKARO S)
- `2.520,00` (sin prefijo USD, formato ARS COPRAC)

---

## FDAs completados

| Buque | Puerto | Sailed | Cliente |
|---|---|---|---|
| LADY VENEZIA | San Lorenzo | Feb 20, 2026 | VENEZIA SHIPTRADING LTD |
| SUSANOO | San Lorenzo | Mar 06, 2026 | MOL CHEMICAL TANKERS |
| ISEACO GRACE | San Lorenzo | Mar 09, 2026 | ADM INTERNATIONAL SARL |
| KM VANCOUVER | San Lorenzo | Mar 22, 2026 | AXLE MARINE PTE LTD |
| THE ETERNAL | Bahía Blanca | Mar 23, 2026 | AL GHURAIR RESOURCES |
| INCE EVRENYE | Bahía Blanca | Mar 27, 2026 | BLACK SEA SHIPPING |
| OZGUR AKSOY | Necochea | Mar 23, 2026 | OLAM MARITIME |
| GENCO CONSTELLATION | Gral. Lagos | Mar 23, 2026 | OCTOFR8 LTD |
| LASKARO S | San Lorenzo | Apr 13, 2026 | CEFETRA SPA |

---

## Datos bancarios fijos (sumario)

Citibank N.A., New York Branch  
ABA: 21000089 | SWIFT: CITIUS33  
Account: 36404074  
Beneficiary: INDEPENDENT SHIP AGENTS S.A.

---

*Generado automáticamente — Jun 2, 2026*
