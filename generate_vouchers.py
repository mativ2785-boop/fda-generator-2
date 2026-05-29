"""
Genera vouchers ISA desde cero leyendo las FACBs.
Datos 100% extraídos de las facturas — nada hardcodeado del FDA anterior.
"""
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

LOGO = '/home/claude/fda_vtc/logo_isa.png'
PW, PH = A4  # 595.27 x 841.89

# Datos extraídos de las FACBs
VESSEL   = 'VTC PHOENIX'
SAILED   = 'Apr 21, 2026'
PORT     = 'SAN LORENZO'
FOOTER   = ('Av. del Libertador 602 - 9th Floor - C1001ABT - Buenos Aires - Argentina',
            'Phone (+54 11) 4819-4100 - Fax (+54 11) 4819-4101 - disbursements@isa-agents.com.ar')

def make_voucher(concept: str, amount: str, rate: str) -> io.BytesIO:
    """
    Genera una página de voucher ISA.
    concept: ej. 'AGENCY FEE'
    amount:  ej. 'USD 3,000.00'
    rate:    ej. '1366.5'
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Logo centrado arriba
    LOGO_W = 141.73
    LOGO_X = (PW - LOGO_W) / 2
    c.drawImage(LOGO, LOGO_X, PH - 133.34, width=LOGO_W, height=LOGO_W,
                preserveAspectRatio=True, mask='auto')

    # Puerto
    c.setFont('Helvetica-Bold', 16)
    c.drawString(80, PH - 182, PORT)

    # Línea separadora 1
    c.setLineWidth(1)
    c.line(80, PH - 232, 520, PH - 232)

    # VESSEL / SAILED / RATE OF EXCHANGE
    c.setFont('Helvetica-Bold', 24)
    c.drawString(80, PH - 257, f'VESSEL: {VESSEL}')
    c.setFont('Helvetica-Bold', 16)
    c.drawString(80, PH - 277, f'SAILED: {SAILED}')
    c.drawString(80, PH - 297, f'RATE OF EXCHANGE: {rate}')

    # Línea separadora 2
    c.line(80, PH - 302, 520, PH - 302)

    # Concepto
    c.setFont('Helvetica-Bold', 18)
    c.drawString(80, PH - 382, concept)

    # Monto centrado
    c.setFont('Helvetica-Bold', 22)
    c.drawCentredString(PW / 2, PH - 482, amount)

    # Footer
    c.setFont('Helvetica', 8)
    c.drawCentredString(PW / 2, PH - 742, FOOTER[0])
    c.drawCentredString(PW / 2, PH - 752, FOOTER[1])

    c.save()
    buf.seek(0)
    return buf

# ─────────────────────────────────────────────────────────────────────────────
# DEFINICIÓN DE VOUCHERS — extraídos directamente de las FACBs
# ─────────────────────────────────────────────────────────────────────────────

# TC 1366.5 — de FACB 30073 y FACB 30537
TC1 = '1366.5'
VOUCHERS_TC1 = [
    # (concept, amount_display)   — de FACB 30073
    ('AGENCY FEE',                          'USD 3,000.00'),
    # — de FACB 30537
    ('PORT DUES',                           'USD 7,945.38'),
    ('ENTRANCE AND LIGHT DUES',             'USD 501.48'),
    ('RIVER PLATE PILOTAGE',                'USD 17,946.80'),
    ('RIVER PARANA PILOTAGE',               'USD 35,310.00'),
    ('RIVER PARANA PILOTAGE ANCHORAGE MANEUVER', 'USD 2,898.00'),
    ('PORT PILOTAGE',                       'USD 8,842.90'),
    ('LAUNCH SERVICES FOR CLEARANCE (AT ROADS)', 'USD 3,000.00'),
    ('MOORING & UNMOORING SERVICES',        'USD 11,000.00'),
    ('CUSTOM HOUSE EXPENSES',               'USD 270.64'),
    ('MIGRATION EXPENSES',                  'USD 1,293.14'),
    ('GARBAGE COMPULSORY INSPECTION',       'USD 96.58'),
    ('MANDATORY HOLDS INSPECTION',          'USD 2,430.00'),
    ('HEADCLERK COMPULSORY SERVICES',       'USD 2,130.36'),
    ('TAX ON CREDIT/DEBIT LAW 25.413',      'USD 1,126.38'),
]

# TC 1400 — de FACB 30536
TC2 = '1400'
VOUCHERS_TC2 = [
    ('TOLL DUES (AGP)',                     'USD 25,325.53'),
    ('TAX ON CREDIT/DEBIT LAW 25.413',      'USD 303.91'),
]

# TC 1462.74 — de FACB 30544
TC3 = '1462.74'
VOUCHERS_TC3 = [
    ('PILOT LAUNCH TRANSPORTATION RIVER PLATE', 'USD 4,440.00'),
    ('TAX ON CREDIT/DEBIT LAW 25.413',      'USD 53.28'),
]

ALL_VOUCHERS = (
    [(c, a, TC1) for c, a in VOUCHERS_TC1] +
    [(c, a, TC2) for c, a in VOUCHERS_TC2] +
    [(c, a, TC3) for c, a in VOUCHERS_TC3]
)

def get_voucher(concept_key: str):
    """
    Devuelve el BytesIO del voucher que coincide con concept_key
    (búsqueda por substring del concepto).
    """
    key = concept_key.upper()
    for concept, amount, rate in ALL_VOUCHERS:
        if key in concept:
            return make_voucher(concept, amount, rate)
    raise ValueError(f"Voucher no encontrado para: {concept_key}")

if __name__ == '__main__':
    # Test: generate one voucher
    from pypdf import PdfReader
    buf = get_voucher('AGENCY FEE')
    r = PdfReader(buf)
    print(f"Agency Fee voucher: {len(r.pages)} page")
    buf = get_voucher('TOLL DUES')
    r = PdfReader(buf)
    print(f"Toll Dues voucher: TC={[v[2] for v in ALL_VOUCHERS if 'TOLL' in v[0]][0]}")
    print("generate_vouchers.py OK")
