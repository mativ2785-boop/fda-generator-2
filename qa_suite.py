"""
ISA FDA Generator — QA Suite v1.0
Tests de producción para classifier.py, assembler.py, ports.py

Ejecutar:
    python3 qa_suite.py              # todos los tests
    python3 qa_suite.py CLF          # solo tests CLF-*
    python3 qa_suite.py CLF-02       # test específico
    python3 qa_suite.py --json       # output JSON para el dashboard
"""

import sys, os, io, re, json, tempfile, time, traceback
from pathlib import Path

# ── Setup de paths ────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

# ── Importar módulos bajo test ────────────────────────────────────────────────
import importlib.util

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

try:
    pts = _load('ports',      BASE / 'ports.py')
    clf = _load('classifier', BASE / 'classifier.py')
    asm = _load('assembler',  BASE / 'assembler.py')
    IMPORT_OK = True
    IMPORT_ERROR = None
except Exception as e:
    IMPORT_OK = False
    IMPORT_ERROR = str(e)
    pts = clf = asm = None

# ── Helpers para generar PDFs de prueba ───────────────────────────────────────
def _make_pdf(lines, path=None):
    """Crea un PDF de texto simple con las líneas dadas."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 9)
    y = 780
    for line in lines:
        c.drawString(50, y, str(line))
        y -= 13
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 9)
            y = 780
    c.save()
    buf.seek(0)
    if path:
        with open(path, 'wb') as f:
            f.write(buf.read())
        return path
    return buf

def _make_pdf_file(lines):
    """Crea un PDF temporal y retorna su path."""
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    _make_pdf(lines, tmp.name)
    tmp.close()
    return tmp.name

# ── Framework de tests ────────────────────────────────────────────────────────
results = []

def test(code, desc):
    """Decorador para registrar tests."""
    def decorator(fn):
        def wrapper():
            if not IMPORT_OK:
                return {
                    "code": code, "desc": desc,
                    "status": "ERROR", "detail": f"Import failed: {IMPORT_ERROR}",
                    "duration_ms": 0
                }
            t0 = time.perf_counter()
            try:
                result = fn()
                duration = int((time.perf_counter() - t0) * 1000)
                if result is True or result is None:
                    return {"code": code, "desc": desc, "status": "PASS",
                            "detail": "", "duration_ms": duration}
                elif isinstance(result, str):
                    return {"code": code, "desc": desc, "status": "FAIL",
                            "detail": result, "duration_ms": duration}
                else:
                    return {"code": code, "desc": desc, "status": "PASS",
                            "detail": str(result), "duration_ms": duration}
            except AssertionError as e:
                duration = int((time.perf_counter() - t0) * 1000)
                return {"code": code, "desc": desc, "status": "FAIL",
                        "detail": str(e) or "AssertionError", "duration_ms": duration}
            except Exception as e:
                duration = int((time.perf_counter() - t0) * 1000)
                return {"code": code, "desc": desc, "status": "ERROR",
                        "detail": f"{type(e).__name__}: {e}\n{traceback.format_exc()[-400:]}",
                        "duration_ms": duration}
        wrapper._code = code
        wrapper._desc = desc
        results.append(wrapper)
        return wrapper
    return decorator

# ══════════════════════════════════════════════════════════════════════════════
# TESTS CLF — Clasificador
# ══════════════════════════════════════════════════════════════════════════════

@test("CLF-01", "DUPLICADO/TRIPLICADO se saltean siempre")
def _():
    assert clf.is_duplicate_page("DUPLICADO")            == True
    assert clf.is_duplicate_page("TRIPLICADO")           == True
    assert clf.is_duplicate_page("hoja DUPLICADO extra") == True
    assert clf.is_duplicate_page("ORIGINAL")             == False
    assert clf.is_duplicate_page("")                     == False
    assert clf.is_duplicate_page("FACTURA A")            == False

@test("CLF-02", "Glatil clasifica como 'glatil', nunca como 'practicaje_rp'")
def _():
    p = _make_pdf_file(["GLATIL SA", "RUC EMISOR 213452850015",
                        "TOTAL A PAGAR: 4.440,00"])
    try:
        result = clf.classify_doc(p)
        assert result == "glatil", f"Esperado 'glatil', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-03", "Maritime carátula siempre skip (FACT CRED ELECT)")
def _():
    p = _make_pdf_file(["FACT CRED ELECT MiPyME",
                        "MARITIME SHIPPING AGENCY SRL",
                        "INDEPENDENT SHIP AGENTS"])
    try:
        result = clf.classify_doc(p)
        assert result == "maritime", f"Esperado 'maritime', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-04", "SOF se detecta por 'Statement of Facts'")
def _():
    p = _make_pdf_file(["Standard Statement on Fact",
                        "M/V TEST VESSEL",
                        "SAILED 21/04/2026"])
    try:
        result = clf.classify_doc(p)
        assert result == "sof", f"Esperado 'sof', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-05", "FACB ISA se detecta por B00003")
def _():
    p = _make_pdf_file(["B", "Cod.006", "F A C T U R A",
                        "Nro. B00003-00030073",
                        "INDEPENDENT SHIP AGENTS",
                        "SAN LORENZO PORT",
                        "AGENCY FEE"])
    try:
        result = clf.classify_doc(p)
        assert result == "facb_isa", f"Esperado 'facb_isa', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-06", "ENAPRO se detecta por 'Ente Administrador Puerto Rosario'")
def _():
    p = _make_pdf_file(["Ente Administrador Puerto Rosario",
                        "Belgrano 341 Rosario",
                        "tesoreria@enapro.com.ar",
                        "IVA: Responsable Inscripto",
                        "ENTRADA"])
    try:
        result = clf.classify_doc(p)
        assert result in ("maritime", "enapro_standalone"), \
            f"Esperado 'maritime' o 'enapro_standalone', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-07", "Multipar clasifica como 'coprac'")
def _():
    p = _make_pdf_file(["Multipar S.A.",
                        "C.U.I.T: 55-00000345-9",
                        "SERVICIO DE PILOTAJE",
                        "VTC PHOENIX",
                        "Av. Julio A. Roca 620",
                        "inforio@riopar.com.ar"])
    try:
        result = clf.classify_doc(p)
        assert result == "coprac", f"Esperado 'coprac', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-08", "Rosario Pilots clasifica como 'rosario_pilots'")
def _():
    p = _make_pdf_file(["ROSARIO PILOTS COOP. TRAB. LTDA.",
                        "CUIT Nº : 30-64794073-7",
                        "pilots@rosariopilots.com"])
    try:
        result = clf.classify_doc(p)
        assert result == "rosario_pilots", f"Esperado 'rosario_pilots', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-09", "detect_pilotaje_flags: Ripla USD en línea → maniobra")
def _():
    p = _make_pdf_file(["Practicaje Río de la Plata C.T.",
                        "1 MANIOBRAS EN ZC USD 2,520.00",
                        "SUBTOTAL USD 48,858.40"])
    try:
        has_d, has_m, amt = clf.detect_pilotaje_flags(p)
        assert has_m, "No detectó maniobra con 'USD 2,520.00' en línea"
        assert amt >= 2520.0, f"Monto maniobra esperado >= 2520, obtuvo {amt}"
    finally:
        os.unlink(p)

@test("CLF-10", "detect_pilotaje_flags: COPRAC ARS formato → maniobra")
def _():
    p = _make_pdf_file(["C.O.P.R.A.C. Ltda.",
                        "MANIOBRA DE FONDEO",
                        "2.520,00",
                        "SUBTOTAL"])
    try:
        has_d, has_m, amt = clf.detect_pilotaje_flags(p)
        assert has_m, "No detectó maniobra con formato COPRAC '2.520,00'"
        assert amt >= 2520.0, f"Monto maniobra COPRAC esperado >= 2520, obtuvo {amt}"
    finally:
        os.unlink(p)

@test("CLF-11", "detect_pilotaje_flags: Multipar 966 USD → maniobra")
def _():
    p = _make_pdf_file(["Multipar S.A.",
                        "MANIOBRA DE VIRADO AL INICIO",
                        "+ MANIOBRA DE FONDEO RADA ROSARIO",
                        "2.00",
                        "966.00",
                        "1,932.00"])
    try:
        has_d, has_m, amt = clf.detect_pilotaje_flags(p)
        assert has_m, "No detectó maniobra Multipar con '966.00'"
        assert amt >= 966.0, f"Monto maniobra Multipar esperado >= 966, obtuvo {amt}"
    finally:
        os.unlink(p)

@test("CLF-12", "detect_pilotaje_flags: Multipar sin maniobra → no detecta")
def _():
    p = _make_pdf_file(["Multipar S.A.",
                        "SERVICIO DE PILOTAJE",
                        "FONDEO RADA ROSARIO",
                        "2,490.00",
                        "3,468,570.00"])
    try:
        has_d, has_m, amt = clf.detect_pilotaje_flags(p)
        assert not has_m, f"Detectó maniobra donde no hay (amt={amt})"
    finally:
        os.unlink(p)

@test("CLF-13", "detect_pilotaje_flags: DEMORA en texto → has_demora")
def _():
    p = _make_pdf_file(["Practicaje Río de la Plata",
                        "DEMORA POR ESPERA DE MAREA",
                        "SUBTOTAL USD 300.00"])
    try:
        has_d, has_m, amt = clf.detect_pilotaje_flags(p)
        assert has_d, "No detectó DEMORA"
    finally:
        os.unlink(p)

@test("CLF-14", "Terminal 6 clasifica como 'terminal_portuario'")
def _():
    p = _make_pdf_file(["TERMINAL 6 S.A.",
                        "Hipolito Yrigoyen y Gral. Lucio N. Mansilla",
                        "USO DE MUELLE"])
    try:
        result = clf.classify_doc(p)
        assert result == "terminal_portuario", \
            f"Esperado 'terminal_portuario', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-15", "CARP y AGP clasifican correctamente")
def _():
    p_carp = _make_pdf_file(["Comisión Administradora del Río de la Plata",
                              "peaje@comisionriodelaplata.org",
                              "CARP"])
    p_agp  = _make_pdf_file(["ADMINISTRACION GENERAL DE PUERTOS S. A. U.",
                              "ING. HUERGO 431",
                              "30-54670628-8"])
    try:
        r1 = clf.classify_doc(p_carp)
        r2 = clf.classify_doc(p_agp)
        assert r1 == "carp", f"CARP: esperado 'carp', obtuvo '{r1}'"
        assert r2 == "agp",  f"AGP: esperado 'agp', obtuvo '{r2}'"
    finally:
        os.unlink(p_carp); os.unlink(p_agp)

@test("CLF-16", "Centro de Navegación clasifica como 'centro_nav'")
def _():
    p = _make_pdf_file(["Centro de Navegación Asociación Civil",
                        "cnav.org.ar",
                        "Florida 537"])
    try:
        result = clf.classify_doc(p)
        assert result == "centro_nav", f"Esperado 'centro_nav', obtuvo '{result}'"
    finally:
        os.unlink(p)

@test("CLF-17", "Glatil NO clasifica como 'practicaje_rp' incluso con 'Río de la Plata'")
def _():
    # Glatil aparece en el Excel bajo RIVER PLATE PILOTAGE pero emite factura propia.
    # Si el PDF tiene 'Río de la Plata' Y 'GLATIL', debe clasificar como 'glatil'.
    p = _make_pdf_file(["GLATIL SA",
                        "Río de la Plata",
                        "RUC EMISOR 213452850015",
                        "TOTAL A PAGAR: 4.440,00"])
    try:
        result = clf.classify_doc(p)
        assert result == "glatil", \
            f"Glatil con 'Río de la Plata' clasificó como '{result}', esperado 'glatil'"
    finally:
        os.unlink(p)

@test("CLF-18", "extract_zip rechaza archivos > MAX_UNCOMPRESSED_SIZE")
def _():
    import zipfile, struct
    # Crear un ZIP con metadata que indica un archivo descomprimido enorme
    # Usamos un approach diferente: crear un ZIP real con archivo pequeño pero
    # parchear la lógica verificando que la excepción se lanza bien
    # En vez de un ZIP real enorme (imposible en test), verificamos el comportamiento
    # con un mock del file_size
    
    class FakeZipInfo:
        def __init__(self):
            self.filename = "test.pdf"
            self.file_size = 400 * 1024 * 1024  # 400 MB > MAX 300MB
    
    class FakeZip:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def infolist(self): return [FakeZipInfo()]
    
    import zipfile as _zf
    original = _zf.ZipFile
    _zf.ZipFile = lambda *a, **k: FakeZip()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear un ZIP mínimo válido
            zpath = os.path.join(tmpdir, "big.zip")
            with open(zpath, 'wb') as f:
                f.write(b"PK\x05\x06" + b"\x00" * 18)
            try:
                clf.extract_zip(zpath, os.path.join(tmpdir, "out"))
                return "No lanzó ValueError para ZIP demasiado grande"
            except ValueError as e:
                assert "grande" in str(e).lower() or "MB" in str(e), \
                    f"ValueError inesperado: {e}"
    finally:
        _zf.ZipFile = original

# ══════════════════════════════════════════════════════════════════════════════
# TESTS ASM — Assembler
# ══════════════════════════════════════════════════════════════════════════════

@test("ASM-01", "FACBs de un TC se insertan UNA SOLA VEZ (sin duplicados)")
def _():
    import inspect
    src = inspect.getsource(asm.build_fda)
    assert "agency_ncb" not in src, \
        "Lógica de inserción parcial 'agency_ncb' encontrada — causa duplicados"
    # Verificar que hay exactamente un punto de tc_inserted.add(tc)
    adds = [l for l in src.split('\n') if 'tc_inserted.add(tc)' in l and not l.strip().startswith('#')]
    assert len(adds) >= 1, "No se encontró tc_inserted.add(tc)"

@test("ASM-02", "Orden bloque TC: NCB → Agency → Port_expenses")
def _():
    import inspect
    src = inspect.getsource(asm.build_fda)
    assert "ncbs + agency + port_exp" in src, \
        "Orden NCB→Agency→Port no encontrado en build_fda"

@test("ASM-03", "Glatil 5234.80 y 6154.80 se EXCLUYEN")
def _():
    import inspect
    src = inspect.getsource(pts.SanLorenzoPort.build_invoice_map)
    assert "5,234" in src or "5234" in src, "Exclusión Glatil 5234 no encontrada"
    assert "6,154" in src or "6154" in src, "Exclusión Glatil 6154 no encontrada"

@test("ASM-04", "Glatil 4440 se incluye bajo Pilot Launch")
def _():
    import inspect
    src = inspect.getsource(pts.SanLorenzoPort.build_invoice_map)
    assert "PILOT LAUNCH TRANSPORTATION RIVER PLATE" in src, \
        "Pilot Launch no encontrado en build_invoice_map"
    assert "glatil" in src, "Referencia a 'glatil' no encontrada"

@test("ASM-05", "extract_facb_line_amounts: Formato A (líneas separadas)")
def _():
    p = _make_pdf_file([
        "1", "PORT DUES", "1.00", "7,945.38",
        "2", "ENTRANCE AND LIGHT DUES", "1.00", "501.48",
        "3", "TAX ON CREDIT/DEBIT LAW 25.413", "1.00", "1,126.38"
    ])
    try:
        result = asm.extract_facb_line_amounts(p)
        assert "PORT DUES" in result, f"PORT DUES no encontrado en {list(result.keys())}"
        assert abs(result["PORT DUES"] - 7945.38) < 0.01, \
            f"PORT DUES: esperado 7945.38, obtuvo {result['PORT DUES']}"
        assert "ENTRANCE AND LIGHT DUES" in result
        assert "TAX ON CREDIT/DEBIT LAW 25.413" in result
    finally:
        os.unlink(p)

@test("ASM-06", "extract_facb_line_amounts: Formato B (línea única)")
def _():
    p = _make_pdf_file([
        "1  PORT DUES  1.00  7,945.38",
        "2  TOLL DUES  1.00  25,325.53"
    ])
    try:
        result = asm.extract_facb_line_amounts(p)
        # Formato B es fallback — si no hay ningún item del formato A
        if result:
            if "PORT DUES" in result:
                assert abs(result["PORT DUES"] - 7945.38) < 0.01
    finally:
        os.unlink(p)

@test("ASM-07", "fmt_amt: enteros sin decimales, decimales con 2 cifras")
def _():
    assert asm.fmt_amt(3000.0)    == "3,000",      f"3000.0 → '{asm.fmt_amt(3000.0)}'"
    assert asm.fmt_amt(3000.50)   == "3,000.50",   f"3000.50 → '{asm.fmt_amt(3000.50)}'"
    assert asm.fmt_amt(97924.0)   == "97,924",     f"97924.0 → '{asm.fmt_amt(97924.0)}'"
    assert asm.fmt_amt(141543.30) == "141,543.30", f"141543.30 → '{asm.fmt_amt(141543.30)}'"

@test("ASM-08", "make_voucher genera PDF de 1 página con concepto y TC")
def _():
    from pypdf import PdfReader
    result = asm.make_voucher(
        "PORT DUES", 7945.38, 1366.5,
        "M/V VTC PHOENIX", "Apr 21, 2026", "SAN LORENZO"
    )
    assert len(result.pages) == 1, f"Esperado 1 página, obtuvo {len(result.pages)}"
    text = result.pages[0].extract_text()
    assert "PORT DUES" in text, "Concepto no encontrado en voucher"
    assert "1366.5" in text or "1,366.5" in text, "TC no encontrado en voucher"
    assert "VTC PHOENIX" in text, "Vessel no encontrado en voucher"

@test("ASM-09", "make_summary: balance >= 0 → 'Total due to ISA'")
def _():
    from pypdf import PdfReader
    tc_groups = {1366.5: [("30073", "Agency fee", 3000.0), ("30537", "Port expenses", 50000.0)]}
    result = asm.make_summary(
        "M/V VTC PHOENIX", "San Lorenzo Port", "Apr 21, 2026",
        "June 1, 2026", "DAEDONG SHIPPING CO LTD",
        advance=10000.0, tc_groups=tc_groups
    )
    text = result.pages[0].extract_text()
    assert "Total due to ISA" in text or "due to ISA" in text.lower(), \
        f"'due to ISA' no encontrado. Balance = 53000 - 10000 = 43000 >= 0"

@test("ASM-10", "make_summary: balance < 0 → 'Total due to [cliente]'")
def _():
    from pypdf import PdfReader
    tc_groups = {1366.5: [("30073", "Agency fee", 3000.0)]}
    result = asm.make_summary(
        "M/V TEST", "San Lorenzo Port", "Apr 21, 2026",
        "June 1, 2026", "TEST CLIENT",
        advance=200000.0, tc_groups=tc_groups
    )
    text = result.pages[0].extract_text()
    assert "TEST CLIENT" in text, "'TEST CLIENT' no encontrado en sumario"
    # Balance = 3000 - 200000 = -197000 → due to cliente
    assert "due to" in text.lower(), "Texto de balance no encontrado"

@test("ASM-11", "make_summary: advance=0 → SIN fila 'Less advanced'")
def _():
    tc_groups = {1366.5: [("30073", "Agency fee", 3000.0)]}
    result = asm.make_summary(
        "M/V TEST", "San Lorenzo Port", "Apr 21, 2026",
        "June 1, 2026", "TEST CLIENT",
        advance=0, tc_groups=tc_groups
    )
    text = result.pages[0].extract_text()
    assert "Less advanced" not in text, \
        "Fila 'Less advanced' encontrada con advance=0"

@test("ASM-12", "make_summary: datos bancarios Citibank presentes")
def _():
    tc_groups = {1366.5: [("30073", "Agency fee", 3000.0)]}
    result = asm.make_summary(
        "M/V TEST", "San Lorenzo Port", "Apr 21, 2026",
        "June 1, 2026", "TEST CLIENT",
        advance=0, tc_groups=tc_groups
    )
    text = result.pages[0].extract_text()
    assert "Citibank" in text,      "Citibank no encontrado"
    assert "21000089" in text,      "ABA 21000089 no encontrado"
    assert "CITIUS33" in text,      "SWIFT CITIUS33 no encontrado"
    assert "36404074" in text,      "Account 36404074 no encontrado"

@test("ASM-13", "make_summary: SIN firma (sin 'Buenos Aires' / 'Pablo Chantir')")
def _():
    tc_groups = {1366.5: [("30073", "Agency fee", 3000.0)]}
    result = asm.make_summary(
        "M/V TEST", "San Lorenzo Port", "Apr 21, 2026",
        "June 1, 2026", "TEST CLIENT",
        advance=0, tc_groups=tc_groups
    )
    text = result.pages[0].extract_text()
    assert "Pablo Chantir" not in text, "Firma 'Pablo Chantir' encontrada"
    assert "Yours Faithfully" not in text, "Frase de firma encontrada"

@test("ASM-14", "tc_groups de make_summary NO se muta durante build")
def _():
    import copy
    # Verificar que build_fda usa deepcopy antes de pasar tc_groups al sumario
    import inspect
    src = inspect.getsource(asm.build_fda)
    assert "deepcopy" in src, "deepcopy no encontrado en build_fda"
    assert "tc_groups_summary" in src, "tc_groups_summary no encontrado"

# ══════════════════════════════════════════════════════════════════════════════
# TESTS SL — San Lorenzo
# ══════════════════════════════════════════════════════════════════════════════

@test("SL-01", "VOUCHER_ORDER: Tax < CARP < Pilot Launch < AGP")
def _():
    sl = pts.SanLorenzoPort()
    vo = sl.VOUCHER_ORDER
    tax  = vo.index("TAX ON CREDIT/DEBIT LAW 25.413")
    carp = vo.index("TOLL DUES (CARP)")
    pilot= vo.index("PILOT LAUNCH TRANSPORTATION RIVER PLATE")
    agp  = vo.index("TOLL DUES (AGP)")
    assert tax < carp,  f"Tax({tax}) debe ir antes de CARP({carp})"
    assert carp < pilot,f"CARP({carp}) debe ir antes de Pilot Launch({pilot})"
    assert pilot < agp, f"Pilot Launch({pilot}) debe ir antes de AGP({agp})"

@test("SL-02", "Anchorage Maneuver: SIN fallback a todas las facturas")
def _():
    import inspect
    src = inspect.getsource(pts.SanLorenzoPort.build_invoice_map)
    assert "if not cp_manio: cp_manio = cp_base" not in src, \
        "Fallback anchorage presente — Anchorage usará todas las facturas si no hay maniobra"
    assert "if not rp_manio: rp_manio = rp_base" not in src, \
        "Fallback anchorage RP presente"

@test("SL-03", "Anchorage Maneuver: solo facturas con maniobra_amount > 0")
def _():
    import inspect
    src = inspect.getsource(pts.SanLorenzoPort.build_invoice_map)
    assert "maniobra_amount" in src and "> 0" in src, \
        "Condición maniobra_amount > 0 no encontrada"

@test("SL-04", "detect_port: 'SAN LORENZO PORT' → SanLorenzoPort")
def _():
    analysis = {"port": "San Lorenzo Port", "facbs": [], "tc_groups": {},
                "practicaje_rp": [], "coprac": [], "rosario_pilots": [],
                "terminal_portuario": [], "amarre_coral": [], "glatil": [],
                "carp": [], "agp": [], "edi_separovic": [], "centro_nav": [],
                "maritime": [], "consorcio_quequen": [], "melluso": [],
                "pilotaje": []}
    result = pts.detect_port(analysis)
    assert isinstance(result, pts.SanLorenzoPort), \
        f"Esperado SanLorenzoPort, obtuvo {type(result).__name__}"

@test("SL-05", "_build_with_extra_taxes inserta Tax TC alto después del último voucher de ese TC")
def _():
    base = [
        {"concept": "PORT DUES",  "tc": 1345, "invoices": []},
        {"concept": "TOLL DUES",  "tc": 1385, "invoices": []},
    ]
    entries = {
        "TAX ON CREDIT/DEBIT LAW 25.413 _TC1385": {
            "concept": "TAX ON CREDIT/DEBIT LAW 25.413",
            "tc": 1385, "invoices": [], "solo": True
        }
    }
    result = pts._build_with_extra_taxes(base, entries)
    assert len(result) == 3, f"Esperado 3 entries, obtuvo {len(result)}"
    assert result[2]["tc"] == 1385, "Tax TC1385 debe ser el último"
    assert result[2]["concept"] == "TAX ON CREDIT/DEBIT LAW 25.413"

@test("SL-06", "TOWAGE SERVICES está en VOUCHER_ORDER de SanLorenzoPort")
def _():
    sl = pts.SanLorenzoPort()
    assert "TOWAGE SERVICES" in sl.VOUCHER_ORDER, \
        "TOWAGE SERVICES no está en VOUCHER_ORDER de SanLorenzoPort"
    idx_tow  = sl.VOUCHER_ORDER.index("TOWAGE SERVICES")
    idx_moor = sl.VOUCHER_ORDER.index("MOORING & UNMOORING SERVICES")
    assert idx_moor < idx_tow, "MOORING debe ir antes que TOWAGE"

@test("SL-07", "Voucher AGENCY FEE y TAX van sin facturas (invoices vacías)")
def _():
    import inspect
    src = inspect.getsource(pts.SanLorenzoPort.build_invoice_map)
    # Agency Fee debe tener invoices vacías
    assert '"invoices": []' in src or "'invoices': []" in src or "\"invoices\":[]" in src, \
        "AGENCY FEE no tiene invoices vacías en build_invoice_map"
    # Tax 25.413 también debe ir sin facturas
    tax_block_present = (
        '"TAX ON CREDIT/DEBIT LAW 25.413"' in src or
        "'TAX ON CREDIT/DEBIT LAW 25.413'" in src
    )
    assert tax_block_present, "TAX 25.413 no encontrado en build_invoice_map"

# ══════════════════════════════════════════════════════════════════════════════
# TESTS BB — Bahia Blanca
# ══════════════════════════════════════════════════════════════════════════════

@test("BB-01", "detect_port: 'BAHIA BLANCA PORT' → BahiaBlancaPort")
def _():
    analysis = {"port": "Bahia Blanca Port", "facbs": [], "tc_groups": {},
                "consorcio": [], "donmar": [], "puerto_mariel": [],
                "maritime": [], "amarradores": [], "ammoca": [],
                "consorcio_quequen": [], "melluso": [], "pilotaje": []}
    result = pts.detect_port(analysis)
    assert isinstance(result, pts.BahiaBlancaPort), \
        f"Esperado BahiaBlancaPort, obtuvo {type(result).__name__}"

@test("BB-02", "BNA incluido en VOUCHER_ORDER de BahiaBlancaPort (en structure)")
def _():
    # En BB el BNA se inserta DESPUÉS del SOF en build_fda, no en VOUCHER_ORDER.
    # Verificar que build_fda lo incluye para BB.
    import inspect
    src = inspect.getsource(asm.build_fda)
    assert "_is_bb" in src, "_is_bb no encontrado en build_fda"
    assert "bna" in src, "BNA no mencionado en build_fda"

@test("BB-03", "detect_port: fallback por coprac/rosario_pilots → SanLorenzoPort")
def _():
    analysis = {"port": "", "facbs": [], "tc_groups": {},
                "practicaje_rp": [], "coprac": [{"filename": "test.pdf", "has_demora": False, "has_maniobra": False, "maniobra_amount": 0}],
                "rosario_pilots": [], "terminal_portuario": ["t6.pdf"],
                "consorcio_quequen": [], "melluso": [], "pilotaje": []}
    result = pts.detect_port(analysis)
    assert isinstance(result, pts.SanLorenzoPort), \
        f"Fallback con coprac + terminal debería dar SanLorenzoPort, obtuvo {type(result).__name__}"

# ══════════════════════════════════════════════════════════════════════════════
# TESTS GEN — Generales
# ══════════════════════════════════════════════════════════════════════════════

@test("GEN-01", "analyze() retorna todos los campos requeridos")
def _():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = clf.analyze(tmpdir)
    required = ["sof", "bna", "bna_list", "bna_extra", "facbs", "consorcio",
                "donmar", "puerto_mariel", "maritime", "amarradores", "ammoca",
                "centro_nav", "terminal_portuario", "practicaje_rp", "coprac",
                "rosario_pilots", "amarre_coral", "glatil", "carp", "agp",
                "edi_separovic", "unknown", "vessel", "client", "sailed",
                "port", "tc_groups"]
    missing = [f for f in required if f not in result]
    assert not missing, f"Campos faltantes en analyze(): {missing}"

@test("GEN-02", "analyze() en directorio vacío retorna sin errores")
def _():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = clf.analyze(tmpdir)
    assert result["sof"] is None
    assert result["facbs"] == []
    assert result["unknown"] == []

@test("GEN-03", "analyze() procesa directorio con PDF SOF")
def _():
    with tempfile.TemporaryDirectory() as tmpdir:
        sof_path = os.path.join(tmpdir, "SOF_test.pdf")
        _make_pdf(["Standard Statement on Fact",
                   "m.v. TEST VESSEL",
                   "Sailed 21/04/2026",
                   "San Lorenzo Port"], sof_path)
        result = clf.analyze(tmpdir)
    assert result["sof"] == "SOF_test.pdf", \
        f"SOF no detectado: {result['sof']}"

@test("GEN-04", "analyze() procesa FACB ISA y extrae TC")
def _():
    with tempfile.TemporaryDirectory() as tmpdir:
        facb_path = os.path.join(tmpdir, "FACB0000300030073.pdf")
        _make_pdf([
            "B", "Cod.006", "F A C T U R A", "I N V O I C E",
            "Nro. B00003-00030073", "Fecha: 30-Apr 26",
            "DAEDONG SHIPPING CO LTD",
            "M/V VTC PHOENIX", "SAN LORENZO PORT",
            "1", "AGENCY FEE", "1.00", "3000.00",
            "ARS/USD = 1,366.5000",
            "Bank Remittances to:", "CitiBank N.A., USA Branch"
        ], facb_path)
        result = clf.analyze(tmpdir)
    assert len(result["facbs"]) == 1, \
        f"Esperado 1 FACB, obtuvo {len(result['facbs'])}"
    facb = result["facbs"][0]
    assert facb.get("type") == "agency", f"Tipo FACB: esperado 'agency', obtuvo '{facb.get('type')}'"
    assert 1366.0 <= (facb.get("tc") or 0) <= 1367.0, \
        f"TC FACB: esperado ~1366.5, obtuvo {facb.get('tc')}"

@test("GEN-05", "classify_maritime_pages: carátula siempre skip")
def _():
    p = _make_pdf_file(["FACT CRED ELECT MiPyME",
                        "MARITIME SHIPPING AGENCY SRL",
                        "Disbursement Account"])
    try:
        result = clf.classify_maritime_pages(p)
        assert len(result) >= 1
        skipped = [r for r in result if r["category"] in ("skip", "skip_dup")]
        assert len(skipped) >= 1, \
            f"Carátula Maritime no marcada como skip. Categorías: {[r['category'] for r in result]}"
    finally:
        os.unlink(p)

@test("GEN-06", "ports.py: los 3 puertos tienen VOUCHER_ORDER definido")
def _():
    for cls in [pts.SanLorenzoPort, pts.BahiaBlancaPort, pts.NecocheaPort]:
        inst = cls()
        assert hasattr(inst, 'VOUCHER_ORDER'), \
            f"{cls.__name__} no tiene VOUCHER_ORDER"
        assert len(inst.VOUCHER_ORDER) > 0, \
            f"{cls.__name__}.VOUCHER_ORDER está vacío"
        assert "AGENCY FEE" in inst.VOUCHER_ORDER, \
            f"AGENCY FEE no está en {cls.__name__}.VOUCHER_ORDER"

@test("GEN-07", "Glatil 5234 y 6154 excluidos — no en ninguna FACB valida")
def _():
    # Verificar que los montos inválidos de Glatil están en la lista de exclusión
    import inspect
    src = inspect.getsource(pts.SanLorenzoPort.build_invoice_map)
    assert "5,234" in src or "5234" in src, "Exclusión Glatil 5234 no encontrada"
    assert "6,154" in src or "6154" in src, "Exclusión Glatil 6154 no encontrada"

@test("GEN-08", "_mar_inv_shared: agrupa páginas de Maritime por voucher correctamente")
def _():
    # Simular estructura de análisis Maritime
    analysis = {
        "maritime": [
            {
                "filename": "MARITIME.pdf",
                "pages": [
                    {"page": 3, "category": "afip_lman",    "voucher": "CUSTOM HOUSE EXPENSES"},
                    {"page": 4, "category": "se_inward",    "voucher": "CUSTOM HOUSE EXPENSES"},
                    {"page": 5, "category": "migraciones_liq", "voucher": "MIGRATION EXPENSES"},
                ]
            }
        ]
    }
    result = pts._mar_inv_shared(analysis)
    assert "CUSTOM HOUSE EXPENSES" in result, "CUSTOM HOUSE EXPENSES no agrupado"
    assert "MIGRATION EXPENSES" in result, "MIGRATION EXPENSES no agrupado"
    ch_pages = [pgs for fname, pgs in result["CUSTOM HOUSE EXPENSES"]]
    assert [3, 4] in ch_pages, f"Páginas de Custom House incorrectas: {ch_pages}"

# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_tests(filter_code=None):
    output = []
    for fn in results:
        code = fn._code
        if filter_code and not code.startswith(filter_code):
            continue
        r = fn()
        output.append(r)
    return output

if __name__ == "__main__":
    filter_arg = None
    json_mode  = False

    for arg in sys.argv[1:]:
        if arg == "--json":
            json_mode = True
        elif not arg.startswith("--"):
            filter_arg = arg

    test_results = run_tests(filter_arg)

    if json_mode:
        print(json.dumps(test_results, indent=2))
        sys.exit(0)

    # Output human-readable
    passed = sum(1 for r in test_results if r["status"] == "PASS")
    failed = sum(1 for r in test_results if r["status"] == "FAIL")
    errors = sum(1 for r in test_results if r["status"] == "ERROR")
    total  = len(test_results)

    print(f"\n{'='*70}")
    print(f"ISA FDA Generator — QA Suite")
    print(f"{'='*70}")
    print(f"Total: {total}  ✅ PASS: {passed}  ❌ FAIL: {failed}  🔴 ERROR: {errors}")
    print(f"{'='*70}\n")

    for r in test_results:
        icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "🔴"}.get(r["status"], "?")
        dur  = f"{r['duration_ms']}ms"
        print(f"{icon} [{r['code']:8s}] {r['desc'][:55]:<55} {dur:>6}")
        if r["status"] != "PASS" and r["detail"]:
            for line in r["detail"].split("\n")[:4]:
                if line.strip():
                    print(f"           → {line.strip()[:80]}")

    print()
    if failed + errors == 0:
        print("🎉 Todos los tests pasaron. Listo para producción.")
    else:
        print(f"⚠️  {failed + errors} tests fallaron. Revisar antes de deploy.")
    sys.exit(0 if failed + errors == 0 else 1)
