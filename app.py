"""
app.py  —  ISA FDA Generator · Render.com
"""

import os, uuid, shutil, tempfile, traceback
from flask import Flask, request, jsonify, send_file, render_template_string
from classifier import extract_zip, analyze
from assembler  import build_fda
from datetime   import date as today_date

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB máximo

SESSIONS  = {}
MONTHS    = ["January","February","March","April","May","June",
             "July","August","September","October","November","December"]

def today_str():
    d = today_date.today()
    return f"{MONTHS[d.month-1]} {d.day}, {d.year}"


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ISA · FDA Generator</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     background:#f0f2f8;color:#1a1a2e;min-height:100vh}
header{background:#1428B4;color:#fff;padding:16px 32px;
       display:flex;align-items:center;gap:12px;
       box-shadow:0 2px 10px rgba(0,0,0,.3)}
header h1{font-size:1.2rem;font-weight:700}
header small{opacity:.7;font-size:.82rem}
main{max-width:820px;margin:30px auto;padding:0 16px;
     display:flex;flex-direction:column;gap:18px}
.card{background:#fff;border-radius:14px;
      box-shadow:0 1px 5px rgba(0,0,0,.09);overflow:hidden}
.card-head{background:#1428B4;color:#fff;padding:13px 22px;
           display:flex;align-items:center;gap:10px;
           font-weight:600;font-size:.93rem}
.step-num{background:rgba(255,255,255,.22);border-radius:50%;
          width:25px;height:25px;display:flex;align-items:center;
          justify-content:center;font-size:.78rem;font-weight:700}
.card-body{padding:22px}
#drop{border:2.5px dashed #1428B4;border-radius:10px;padding:42px 20px;
      text-align:center;cursor:pointer;transition:background .2s;position:relative}
#drop:hover,#drop.over{background:#eef0fb}
#drop input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%}
#drop .icon{font-size:2.2rem}
#drop p{margin-top:8px;color:#555;font-size:.92rem}
#drop strong{color:#1428B4}
#fname{margin-top:8px;font-size:.83rem;color:#1428B4;font-weight:600;min-height:18px}
#abox{display:none;margin-top:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:9px;margin-top:8px}
.chip{background:#f4f5ff;border-left:3px solid #1428B4;border-radius:7px;
      padding:8px 12px;font-size:.81rem}
.chip .lbl{font-weight:700;color:#1428B4;font-size:.72rem;text-transform:uppercase;margin-bottom:2px}
.chip.warn{border-left-color:#e67e22}.chip.warn .lbl{color:#e67e22}
.chip.ok  {border-left-color:#27ae60}.chip.ok   .lbl{color:#27ae60}
.facbs{margin-top:14px}
.facb{background:#f9f9ff;border:1px solid #dde;border-radius:8px;
      padding:9px 13px;margin-bottom:7px;
      display:flex;justify-content:space-between;align-items:center;
      font-size:.84rem;gap:8px}
.tag{background:#1428B4;color:#fff;border-radius:4px;
     padding:2px 7px;font-size:.72rem;font-weight:700}
.tag.agency{background:#27ae60}.tag.ncb{background:#e74c3c}
.mar-section{display:none;margin-top:18px}
.mar-title{font-weight:700;font-size:.88rem;color:#333;margin-bottom:8px}
.mar-fname{font-size:.82rem;color:#1428B4;font-weight:600;margin:12px 0 5px}
table{width:100%;border-collapse:collapse;font-size:.79rem}
th{background:#1428B4;color:#fff;padding:6px 10px;text-align:left}
td{padding:5px 10px;border-bottom:1px solid #eee}
tr:hover td{background:#f5f6ff}
select{font-size:.77rem;padding:3px 6px;border-radius:4px;border:1px solid #ccd}
.skip{color:#bbb}
.adv-row{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap}
.fg{display:flex;flex-direction:column;gap:5px}
label{font-size:.82rem;font-weight:600;color:#444}
input{border:1.5px solid #d0d4e8;border-radius:7px;
      padding:9px 12px;font-size:.9rem;outline:none;transition:border-color .2s}
input:focus{border-color:#1428B4}
#btn{width:100%;background:#1428B4;color:#fff;border:none;border-radius:10px;
     padding:15px;font-size:1.05rem;font-weight:700;cursor:pointer;
     transition:background .2s}
#btn:hover{background:#0f1e8a}
#btn:disabled{background:#8a96cc;cursor:not-allowed}
#spin{display:none;text-align:center;padding:22px}
.ring{width:42px;height:42px;border:4px solid #e0e3f5;border-top-color:#1428B4;
      border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
#result{display:none}
.ok-box{background:#eafaf1;border:1.5px solid #27ae60;border-radius:11px;
        padding:22px;text-align:center}
.ok-box h2{color:#1e8449;margin-bottom:8px}
.ok-box p{color:#333;font-size:.9rem;margin-bottom:18px;line-height:1.6}
.dl{display:inline-block;background:#1428B4;color:#fff;border-radius:9px;
    padding:13px 30px;font-size:.95rem;font-weight:700;text-decoration:none}
.dl:hover{background:#0f1e8a}
.err{background:#fdf2f2;border:1.5px solid #e74c3c;border-radius:11px;
     padding:18px;color:#c0392b;font-size:.85rem;white-space:pre-wrap}
</style>
</head>
<body>
<header>
  <div><h1>ISA · FDA Generator</h1>
  <small>Bahia Blanca · detección automática por contenido</small></div>
</header>
<main>

<div class="card">
  <div class="card-head"><div class="step-num">1</div>Subir ZIP</div>
  <div class="card-body">
    <div id="drop">
      <input type="file" id="zip-input" accept=".zip">
      <div class="icon">📦</div>
      <p>Arrastrá el <strong>ZIP</strong> aquí o hacé click para seleccionarlo</p>
      <div id="fname"></div>
    </div>
    <div id="abox">
      <strong>Archivos detectados automáticamente:</strong>
      <div class="grid" id="grid"></div>
      <div class="facbs" id="facbs"></div>
      <div class="mar-section" id="mar-sec">
        <div class="mar-title">Páginas de Maritime
          <small style="font-weight:400;color:#888"> — verificá y corregí si es necesario</small>
        </div>
        <div id="mar-body"></div>
      </div>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-head"><div class="step-num">2</div>Adelanto</div>
  <div class="card-body">
    <div class="adv-row">
      <div class="fg">
        <label>Adelanto (Advance) — USD</label>
        <input type="number" id="adv" min="0" step="0.01"
               placeholder="0.00" style="width:210px">
      </div>
      <div class="fg">
        <label>Fecha del FDA</label>
        <input type="text" id="fdate" style="width:195px" placeholder="April 29, 2026">
      </div>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-head"><div class="step-num">3</div>Generar</div>
  <div class="card-body">
    <button id="btn" onclick="gen()">⚡ Generar FDA</button>
    <div id="spin"><div class="ring"></div><p>Generando PDF...</p></div>
    <div id="result" style="margin-top:14px"></div>
  </div>
</div>

</main>
<script>
let sid = null;
const drop = document.getElementById("drop");
const zinp = document.getElementById("zip-input");
drop.addEventListener("dragover",  e=>{e.preventDefault();drop.classList.add("over")});
drop.addEventListener("dragleave", ()=>drop.classList.remove("over"));
drop.addEventListener("drop", e=>{e.preventDefault();drop.classList.remove("over");
  if(e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);});
zinp.addEventListener("change", ()=>{ if(zinp.files[0]) upload(zinp.files[0]); });

async function upload(file) {
  document.getElementById("fname").textContent = "⏳ Analizando...";
  document.getElementById("abox").style.display = "none";
  const fd = new FormData(); fd.append("zip", file);
  let d;
  try { d = await (await fetch("/upload",{method:"POST",body:fd})).json(); }
  catch(e){ document.getElementById("fname").textContent="❌ "+e.message; return; }
  if(d.error){ document.getElementById("fname").textContent="❌ "+d.error; return; }
  sid = d.session_id;
  document.getElementById("fname").textContent = "✓ " + file.name;
  document.getElementById("fdate").value = d.today;
  render(d.analysis);
}

function render(a) {
  const c = (v,g="ok",b="warn") => v ? g : b;
  document.getElementById("grid").innerHTML = [
    [c(a.vessel),"Buque",      a.vessel  || "⚠ no detectado"],
    [c(a.client),"Cliente",    a.client  || "⚠ no detectado"],
    [c(a.sailed),"Sailed",     a.sailed  || "⚠ no detectado"],
    [c(a.port),  "Puerto",     a.port    || "⚠ no detectado"],
    [c(a.sof),   "SOF",        a.sof     || "⚠ no detectado"],
    [c(a.bna),   "BNA",        a.bna     || "⚠ no detectado"],
    ["","Consorcio",   a.consorcio.length+" factura(s)"],
    ["","Donmar",      a.donmar.length+" factura(s)"],
    ["","Pto. Mariel", a.puerto_mariel.length+" factura(s)"],
    ["","Maritime",    a.maritime.length+" expediente(s)"],
  ].map(([cl,lb,vl])=>`<div class="chip ${cl}"><div class="lbl">${lb}</div>${vl}</div>`).join("");

  document.getElementById("facbs").innerHTML = a.facbs.length
    ? "<strong style='display:block;margin-top:14px;margin-bottom:8px'>FACBs detectadas:</strong>"
      + a.facbs.map(f=>`<div class="facb">
          <span><span class="tag ${f.type}">${f.type.toUpperCase()}</span>
          &nbsp;<strong>FACB ${f.number||'?'}</strong> — ${f.label}</span>
          <span>TC ${f.tc||'?'} · USD ${(f.total||0).toLocaleString('en-US',{minimumFractionDigits:2})}</span>
        </div>`).join("")
    : "<p style='color:#e67e22;margin-top:10px'>⚠ No se detectaron FACBs.</p>";

  const ms = document.getElementById("mar-sec");
  const mb = document.getElementById("mar-body");
  mb.innerHTML = "";
  if(a.maritime && a.maritime.length) {
    ms.style.display = "block";
    const opts = [
      ["AGENCY FEE","Agency Fee"],
      ["CUSTOM HOUSE EXPENSES","Custom House Expenses"],
      ["CUSTOM HOUSE PERMANENCE","Custom House Permanence"],
      ["CUSTOM HOUSE (BUNKERING)","Custom House (Bunkering)"],
      ["MIGRATION EXPENSES","Migration Expenses"],
      ["SANITARY DUES AND FREE PRATIQUE","Sanitary Dues"],
      ["GARBAGE COMPULSORY INSPECTION","Garbage Inspection"],
      ["WATCHMEN COMPULSORY SERVICES","Watchmen Services"],
      ["HEADCLERK COMPULSORY SERVICES","Headclerk Services"],
      ["MOORING & UNMOORING SERVICES","Mooring & Unmooring"],
      ["PEST CONTROL","Pest Control"],
      ["OSRO ANNEX 18","OSRO Annex 18"],
      ["skip","— OMITIR —"],
    ].map(([v,t])=>`<option value="${v}">${t}</option>`).join("");

    for(const m of a.maritime) {
      const rows = m.pages.map(pg=>{
        const skip = pg.category.startsWith("skip") || !pg.voucher;
        const sel  = skip ? "skip" : (pg.voucher||"skip");
        const o = opts.replace(`value="${sel}"`,`value="${sel}" selected`);
        return `<tr class="${skip?'skip':''}">
          <td><strong>p${pg.page+1}</strong></td>
          <td>${pg.category}</td>
          <td><select data-f="${m.filename}" data-p="${pg.page}">${o}</select></td>
        </tr>`;
      }).join("");
      mb.innerHTML += `<div class="mar-fname">📄 ${m.filename}</div>
        <table><tr><th>Pág.</th><th>Detectado como</th><th>Asignar a voucher</th></tr>
        ${rows}</table>`;
    }
  } else {
    ms.style.display = "none";
  }
  document.getElementById("abox").style.display = "block";
}

async function gen() {
  if(!sid){alert("Subí el ZIP primero.");return;}
  const adv  = parseFloat(document.getElementById("adv").value)||0;
  const date = document.getElementById("fdate").value.trim();
  const ov   = {};
  document.querySelectorAll("[data-f][data-p]").forEach(s=>{
    const f=s.dataset.f, p=parseInt(s.dataset.p);
    if(!ov[f]) ov[f]={};
    ov[f][p] = s.value;
  });
  document.getElementById("btn").disabled = true;
  document.getElementById("spin").style.display = "block";
  document.getElementById("result").style.display = "none";
  let d;
  try {
    d = await (await fetch("/generate",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({session_id:sid,advance:adv,date,overrides:ov})
    })).json();
  } catch(e){ d={error:e.message}; }
  document.getElementById("spin").style.display = "none";
  document.getElementById("btn").disabled = false;
  const res = document.getElementById("result");
  res.style.display = "block";
  if(d.error) {
    res.innerHTML=`<div class="err">❌ Error:\n${d.error}</div>`;
  } else {
    res.innerHTML=`<div class="ok-box">
      <h2>✅ FDA generado</h2>
      <p><strong>${d.vessel}</strong><br>
      ${d.pages} páginas · Total USD ${d.total.toLocaleString('en-US',{minimumFractionDigits:2})}
      ${d.advance>0?` · Advance USD ${d.advance.toLocaleString('en-US',{minimumFractionDigits:2})}`:''}
      <br>Balance: <strong>USD ${Math.abs(d.balance).toLocaleString('en-US',{minimumFractionDigits:2})} ${d.direction}</strong></p>
      <a class="dl" href="/download/${d.file_id}">⬇ Descargar FDA</a>
    </div>`;
  }
}
</script>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("zip")
    if not f or not f.filename.endswith(".zip"):
        return jsonify({"error": "Subí un .zip"}), 400

    work_dir = tempfile.mkdtemp(prefix="fda_", dir="/tmp")
    zip_path = os.path.join(work_dir, "upload.zip")
    f.save(zip_path)

    try:
        extract_zip(zip_path, work_dir)
    except Exception as e:
        shutil.rmtree(work_dir)
        return jsonify({"error": f"ZIP inválido: {e}"}), 400

    analysis = analyze(work_dir)
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {"work_dir": work_dir, "analysis": analysis}

    a = dict(analysis)
    a["tc_groups"] = {str(k): v for k, v in analysis["tc_groups"].items()}

    return jsonify({"session_id": sid, "analysis": a, "today": today_str()})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    sid  = data.get("session_id")
    if sid not in SESSIONS:
        return jsonify({"error": "Sesión expirada, subí el ZIP de nuevo."}), 400

    work_dir = SESSIONS[sid]["work_dir"]
    analysis = dict(SESSIONS[sid]["analysis"])

    overrides = data.get("overrides", {})
    if overrides:
        new_maritime = []
        for m in analysis["maritime"]:
            fname     = m["filename"]
            new_pages = []
            for pg in m["pages"]:
                cat = pg["category"]; voucher = pg["voucher"]
                key = str(pg["page"])
                if fname in overrides and key in overrides[fname]:
                    new_v   = overrides[fname][key]
                    voucher = None if new_v == "skip" else new_v
                    cat     = "user_override"
                new_pages.append({"page": pg["page"], "category": cat, "voucher": voucher})
            new_maritime.append({"filename": fname, "pages": new_pages})
        analysis["maritime"] = new_maritime

    advance  = float(data.get("advance", 0))
    date_str = data.get("date") or today_str()
    file_id  = str(uuid.uuid4())
    out_path = os.path.join(work_dir, f"FDA_{file_id}.pdf")

    try:
        result = build_fda(analysis, work_dir, out_path, advance, date_str)
        result["file_id"] = file_id
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": traceback.format_exc()}), 500


@app.route("/download/<file_id>")
def download(file_id):
    for sid, sess in SESSIONS.items():
        path = os.path.join(sess["work_dir"], f"FDA_{file_id}.pdf")
        if os.path.exists(path):
            vessel = sess["analysis"].get("vessel", "VESSEL")\
                .replace("M/V ", "").replace(" ", "_")
            return send_file(path, as_attachment=True,
                             download_name=f"FDA_{vessel}.pdf",
                             mimetype="application/pdf")
    return "No encontrado", 404


# Render usa la variable de entorno PORT
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
