"""
FDA VTC PHOENIX v3 — vouchers generados 100% desde las FACBs
"""
import os, io, sys
sys.path.insert(0, '/home/claude/fda_vtc')
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from generate_vouchers import get_voucher

CONTENTS = '/home/claude/fda_vtc/contents'
LOGO     = '/home/claude/fda_vtc/logo_isa.png'
OUTPUT   = '/mnt/user-data/outputs/VTC_PHOENIX_FDA.pdf'
PW, PH   = A4
ISA_BLUE = colors.HexColor('#1428B4')
ISA_RED  = colors.HexColor('#CC0000')
LT_GRAY  = colors.HexColor('#F2F2F2')
MD_GRAY  = colors.HexColor('#CCCCCC')

writer = PdfWriter()

def add_zip(filename, page_indices=None):
    path = os.path.join(CONTENTS, filename)
    r = PdfReader(path)
    idx = page_indices if page_indices is not None else list(range(len(r.pages)))
    for i in idx:
        writer.add_page(r.pages[i])

def add_all(filename):
    add_zip(filename)

def add_voucher(concept_key):
    buf = get_voucher(concept_key)
    writer.add_page(PdfReader(buf).pages[0])

# ── SUMARIO ──────────────────────────────────────────────────────────────────
def build_summary():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(LOGO, PW-100, PH-100, width=70, height=70,
                preserveAspectRatio=True, mask='auto')
    c.setFont('Helvetica-Oblique', 11); c.setFillColor(ISA_BLUE)
    c.drawString(35, PH-28, 'Disbursement Summary')
    c.setFont('Helvetica', 9); c.setFillColor(colors.black)
    c.drawString(35, PH-88, 'Buenos Aires, May 29, 2026')
    c.setStrokeColor(ISA_BLUE); c.setLineWidth(2)
    c.line(35, PH-98, PW-35, PH-98)
    c.setStrokeColor(MD_GRAY); c.setLineWidth(0.5)
    c.line(35, PH-101, PW-35, PH-101)
    y0 = PH-116; rh = 16
    data = [('To:','DAEDONG SHIPPING CO LTD','Sailed:','April 21, 2026'),
            ('Vessel:','M/V VTC PHOENIX','Date:','May 29, 2026'),
            ('Port:','San Lorenzo Port','','')]
    for ri,(l1,v1,l2,v2) in enumerate(data):
        y = y0 - ri*rh
        if ri%2==0:
            c.setFillColor(LT_GRAY); c.rect(35,y-3,PW-70,rh,fill=1,stroke=0)
        c.setFillColor(colors.black)
        c.setFont('Helvetica-Bold',9); c.drawString(40,y+2,l1)
        c.setFont('Helvetica-Bold' if l1=='To:' else 'Helvetica',9); c.drawString(95,y+2,v1)
        c.setFont('Helvetica-Bold',9); c.drawString(PW/2+15,y+2,l2)
        c.setFont('Helvetica',9); c.drawString(PW/2+70,y+2,v2)
    yd = y0-3*rh-12
    c.setFont('Helvetica',9); c.setFillColor(colors.black)
    c.drawString(35,yd,'Dear Sir / Madam,')
    c.drawString(35,yd-13,'Please find our final disbursement account for the operations of the concerning vessel during the call at ref. port.')
    yt = yd-38; cw = [110,165,90,85]
    c.setFillColor(ISA_BLUE); c.rect(35,yt,sum(cw),16,fill=1,stroke=0)
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold',9)
    x=35
    for i,h in enumerate(['Invoice Number','Concept','Port','USD Amount']):
        if i==3: c.drawRightString(x+cw[i]-5,yt+4,h)
        else: c.drawString(x+5,yt+4,h)
        x+=cw[i]
    rows=[('Invoice 16526','Nota de crédito','San Lorenzo','(12,979.59)',True),
          ('Invoice 16525','Nota de crédito','San Lorenzo','(449.33)',True),
          ('Invoice 30073','Agency fee','San Lorenzo','3,000.00',False),
          ('Invoice 30537','Port expenses','San Lorenzo','94,991.66',False),
          ('Invoice 30536','Port expenses','San Lorenzo','25,629.44',False),
          ('Invoice 30544','Port expenses','San Lorenzo','4,493.28',False)]
    for ri,(inv,con,port,amt,ncb) in enumerate(rows):
        yr=yt-(ri+1)*16
        if ri%2==1:
            c.setFillColor(LT_GRAY); c.rect(35,yr,sum(cw),16,fill=1,stroke=0)
        c.setFillColor(ISA_RED if ncb else colors.black)
        c.setFont('Helvetica',9); x=35
        c.drawString(x+5,yr+4,inv); x+=cw[0]
        c.drawString(x+5,yr+4,con); x+=cw[1]
        c.drawString(x+5,yr+4,port); x+=cw[2]
        c.drawRightString(x+cw[3]-5,yr+4,amt)
    yTot=yt-7*16
    c.setFillColor(colors.black); c.setFont('Helvetica-Bold',9)
    c.drawRightString(35+cw[0]+cw[1]+cw[2]-5,yTot+4,'Total Expenses')
    c.drawRightString(35+sum(cw)-5,yTot+4,'141,543.30')
    yAdv=yTot-16; c.setFont('Helvetica',9); c.setFillColor(ISA_RED)
    c.drawString(35+cw[0]+5,yAdv+4,'Less advanced by DAEDONG SHIPPING CO LTD')
    c.drawRightString(35+sum(cw)-5,yAdv+4,'(97,924.00)')
    yBal=yAdv-16
    c.setFillColor(ISA_BLUE); c.rect(35,yBal,sum(cw),16,fill=1,stroke=0)
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold',10)
    c.drawString(40,yBal+4,'Total due to ISA')
    c.drawRightString(35+sum(cw)-5,yBal+4,'43,619.30')
    yC=yBal-30; c.setFont('Helvetica',9); c.setFillColor(colors.black)
    c.drawString(35,yC,'Please do not hesitate to contact us if you need to elaborate on this disbursement.')
    c.drawString(35,yC-13,'We thank you very much for having chosen us as agents. We trust our performance has reached your requirements, and we look')
    c.drawString(35,yC-26,'forward to be of assistance to you in the future.')
    c.setStrokeColor(MD_GRAY); c.setLineWidth(0.5); c.line(35,82,PW-35,82)
    c.setFont('Helvetica-Bold',8); c.setFillColor(ISA_BLUE)
    c.drawString(35,70,'Independent Ship Agents S.A.')
    c.setFont('Helvetica',7); c.setFillColor(colors.black)
    c.drawString(35,60,'Av. del Libertador 602, 9th Floor  |  C1001ABT Buenos Aires, Argentina')
    c.drawString(35,50,'Tel: (+54 11) 4819-4100  |  isa@isa-agents.com.ar  |  www.isa-agents.com.ar')
    yB=yC-55
    c.setFillColor(ISA_BLUE); c.rect(35,yB,200,14,fill=1,stroke=0)
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold',9); c.drawString(40,yB+3,'Bank Details')
    bank=[('Bank:','Citibank N.A., New York Branch'),('Address:','111 Wall Street, New York, NY 10043'),
          ('ABA #:','21000089'),('SWIFT:','CITIUS33'),('Account No:','36404074'),
          ('Beneficiary:','INDEPENDENT SHIP AGENTS S.A.')]
    for bi,(lbl,val) in enumerate(bank):
        yb=yB-14-bi*14
        if bi%2==1:
            c.setFillColor(LT_GRAY); c.rect(35,yb-2,200,14,fill=1,stroke=0)
        c.setFillColor(colors.black); c.setFont('Helvetica',8); c.drawString(40,yb+1,lbl)
        c.setFont('Helvetica-Bold' if lbl=='Beneficiary:' else 'Helvetica',8)
        c.drawString(105,yb+1,val)
    c.save(); buf.seek(0); return buf

writer.add_page(PdfReader(build_summary()).pages[0])
print("1. Sumario ✓")

add_all('84011_VTC PHOENIX - SOF.pdf')
print("2. SOF ✓")

# ════════════════ GRUPO TC 1366.5 ════════════════════════════════════════════
add_zip('N_CB0000300016526.pdf')
print("3. NCB 16526 (TC 1366.5) ✓")
add_zip('FACB0000300030073.pdf')
print("4. FACB 30073 Agency Fee (TC 1366.5) ✓")
add_zip('FACB0000300030537.pdf')
print("5. FACB 30537 Port expenses (TC 1366.5) ✓")

# Agency Fee — voucher solo sin factura
add_voucher('AGENCY FEE')
print("6. Voucher AGENCY FEE [TC 1366.5] ✓")

# Port Dues
add_voucher('PORT DUES')
add_all('TERMINAL 6 S.A. (120007)_W313722.pdf')
print("7. PORT DUES + Terminal 6 [TC 1366.5] ✓")

# Entrance and Light Dues — solo ENAPRO (p5 de W316324, idx 4)
add_voucher('ENTRANCE AND LIGHT DUES')
add_zip('MARITIME SHIPPING AGENCY SRL (130025)_W316324.pdf', [4])
print("8. ENTRANCE AND LIGHT DUES + ENAPRO [TC 1366.5] ✓")

# River Plate Pilotage
add_voucher('RIVER PLATE PILOTAGE')
add_all('PRACTICAJE RIO DE LA PLATA CT (120002)_W312710.pdf')
add_all('PRACTICAJE RIO DE LA PLATA CT (120002)_W312711.pdf')
print("9. RIVER PLATE PILOTAGE + Ripla [TC 1366.5] ✓")

# River Parana Pilotage
add_voucher('RIVER PARANA PILOTAGE')
for f in ['MULTIPAR S.A. (120097)_W309630.pdf','MULTIPAR S.A. (120097)_W309631.pdf',
          'MULTIPAR S.A. (120097)_W311675.pdf','MULTIPAR S.A. (120097)_W311676.pdf',
          'MULTIPAR S.A. (120097)_W312264.pdf','MULTIPAR S.A. (120097)_W312265.pdf']:
    add_all(f)
print("10. RIVER PARANA PILOTAGE + Multipar (6) [TC 1366.5] ✓")

# River Parana Anchorage Maneuver
add_voucher('ANCHORAGE')
add_all('MULTIPAR S.A. (120097)_W309630.pdf')
add_all('MULTIPAR S.A. (120097)_W311675.pdf')
print("11. RIVER PARANA ANCHORAGE MANEUVER [TC 1366.5] ✓")

# Port Pilotage
add_voucher('PORT PILOTAGE')
for f in ['COOP DE TRABAJO PRACTICOS DEL PARANA LTDA (401242)_W312143.pdf',
          'COOP DE TRABAJO PRACTICOS DEL PARANA LTDA (401242)_W312144.pdf',
          'COOP DE TRABAJO PRACTICOS DEL PARANA LTDA (401242)_W312146.pdf',
          'COOP DE TRABAJO PRACTICOS DEL PARANA LTDA (401242)_W312147.pdf']:
    add_all(f)
print("12. PORT PILOTAGE + Coop Practicos [TC 1366.5] ✓")

# Launch Services for Clearance
add_voucher('LAUNCH SERVICES')
add_all('GENTE DE RIO SERVICIOS FLUVIALES SA (401399)_W311921.pdf')
print("13. LAUNCH SERVICES FOR CLEARANCE + Gente de Rio W311921 [TC 1366.5] ✓")

# Mooring & Unmooring
add_voucher('MOORING')
add_all('GENTE DE RIO SERVICIOS FLUVIALES SA (401399)_W311924.pdf')
add_zip('PLATE AMARRES S. A. (404768)_W314445.pdf', [0])
print("14. MOORING & UNMOORING + Gente de Rio + Plate Amarres [TC 1366.5] ✓")

# Custom House Expenses
add_voucher('CUSTOM HOUSE EXPENSES')
add_zip('MARITIME SHIPPING AGENCY SRL (130025)_W316324.pdf', [5,6,7])
add_all('CENTRO DE NAVEGACION ASOCIACION CIVIL (110144)_W312367.pdf')
print("15. CUSTOM HOUSE EXPENSES + AFIP + SSEE + Centro Nav [TC 1366.5] ✓")

# Migration Expenses
add_voucher('MIGRATION')
add_zip('MARITIME SHIPPING AGENCY SRL (130025)_W316324.pdf', [8,9,10])
print("16. MIGRATION EXPENSES [TC 1366.5] ✓")

# Garbage Compulsory Inspection
add_voucher('GARBAGE')
add_zip('MARITIME SHIPPING AGENCY SRL (130025)_W316324.pdf', [11,12])
print("17. GARBAGE COMPULSORY INSPECTION + SENASA [TC 1366.5] ✓")

# Mandatory Holds Inspection
add_voucher('MANDATORY HOLDS')
add_zip('MARITIME SHIPPING AGENCY SRL (130025)_W316325.pdf', [1,2,3,4])
print("18. MANDATORY HOLDS INSPECTION [TC 1366.5] ✓")

# Headclerk Compulsory Services
add_voucher('HEADCLERK')
add_zip('MARITIME SHIPPING AGENCY SRL (130025)_W316326.pdf', [2,3])
print("19. HEADCLERK COMPULSORY SERVICES [TC 1366.5] ✓")

# Tax on Credit/Debit TC 1366.5
add_voucher('TAX ON CREDIT')
print("20. TAX ON CREDIT/DEBIT [TC 1366.5] USD 1,126.38 ✓")

# ════════════════ GRUPO TC 1400 ══════════════════════════════════════════════
add_zip('FACB0000300030536.pdf')
print("21. FACB 30536 Toll Dues (TC 1400) ✓")

add_voucher('TOLL DUES')
add_all('ADMINISTRACION GENERAL DE PUERTOS S. A. U. (401262)_W312878.pdf')
print("22. TOLL DUES (AGP) + factura AGP [TC 1400] ✓")

# Tax TC 1400 — necesita voucher específico con TC 1400
# get_voucher busca por substring: 'TAX ON CREDIT' ya matchea el primero (TC 1366.5)
# Para TC 1400 necesitamos el segundo Tax voucher
from generate_vouchers import make_voucher
buf_tax2 = make_voucher('TAX ON CREDIT/DEBIT LAW 25.413', 'USD 303.91', '1400')
writer.add_page(PdfReader(buf_tax2).pages[0])
print("23. TAX ON CREDIT/DEBIT [TC 1400] USD 303.91 ✓")

# ════════════════ GRUPO TC 1462.74 ═══════════════════════════════════════════
add_zip('N_CB0000300016525.pdf')
print("24. NCB 16525 (TC 1462.74) ✓")
add_zip('FACB0000300030544.pdf')
print("25. FACB 30544 Pilot Launch (TC 1462.74) ✓")

add_voucher('PILOT LAUNCH')
add_all('GLATIL SA (300361)_W313576.pdf')   # USD 4,440 ✓
print("26. PILOT LAUNCH TRANSPORTATION + Glatil 4440 [TC 1462.74] ✓")

buf_tax3 = make_voucher('TAX ON CREDIT/DEBIT LAW 25.413', 'USD 53.28', '1462.74')
writer.add_page(PdfReader(buf_tax3).pages[0])
print("27. TAX ON CREDIT/DEBIT [TC 1462.74] USD 53.28 ✓")

# Output
with open(OUTPUT, 'wb') as f:
    writer.write(f)

total = len(PdfReader(OUTPUT).pages)
print(f"\n✅ {OUTPUT}")
print(f"   Páginas totales: {total}")

# ─────────────────────────────────────────────────────────────────────────────
# COMPRESIÓN AUTOMÁTICA
# ─────────────────────────────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from compress_pdf import compress

print("\nComprimiendo PDF...")
stats = compress(OUTPUT, OUTPUT)
print(f"  Original:  {stats['original_mb']} MB")
print(f"  Final:     {stats['final_mb']} MB")
print(f"  Reducción: {stats['reduction_pct']}%")
print(f"\n✅ FDA listo: {OUTPUT}")


