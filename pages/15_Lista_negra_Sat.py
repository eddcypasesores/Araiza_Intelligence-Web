# pages/15_Lista_negra_Sat.py
from __future__ import annotations

import os, io, json, time, hashlib, zipfile, sqlite3, shutil, threading, tempfile, traceback
from contextlib import closing
from pathlib import Path
from typing import BinaryIO, Dict, Any
from uuid import uuid4
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

# =============================================================================
# Config de página
# =============================================================================
st.set_page_config(
    page_title="Lista Negra SAT — Flujo con pasos",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# Barra fija superior (usa tu render_nav si existe; si no, fallback)
# =============================================================================
def _inject_sticky_nav_css():
    st.markdown(
        """
        <style>
          .ai-sticky-nav {
            position: sticky; top: 0; z-index: 1000;
            background: #0f172a; border-bottom: 1px solid rgba(255,255,255,.08);
            padding: 10px 14px;
          }
          .ai-sticky-nav .title { color:#fff; font-weight:700; letter-spacing:.3px; margin-right:18px; }
          .ai-sticky-nav a { color:#e2e8f0; text-decoration:none; margin-right:14px; font-weight:500; }
          .ai-sticky-nav a:hover { color:#fff; }
          .main .block-container{padding-top:0!important}
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_sticky_nav_fallback():
    _inject_sticky_nav_css()
    st.markdown(
        """
        <div class="ai-sticky-nav">
          <span class="title">Araiza Intelligence</span>
          <a href="/">Inicio</a>
          <a href="?p=calculadora">Calculadora</a>
          <a href="?p=efos" style="font-weight:700">EFOS / Lista Negra</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

try:
    from core.navigation import render_nav as _render_nav  # type: ignore
    try:
        _render_nav(st)
    except Exception:
        render_sticky_nav_fallback()
except Exception:
    render_sticky_nav_fallback()

# =============================================================================
# Rutas de trabajo (Railway-ready)
# =============================================================================
ROOT_FROM_ENV = os.getenv("APP_DATA_DIR")  # p. ej. /data/ais_lista_negra_sat
BASE_ROOT = Path(ROOT_FROM_ENV) if ROOT_FROM_ENV else Path(tempfile.gettempdir()) / "ais_lista_negra_sat"

DATA_DIR = BASE_ROOT
FIRMES_DIR = DATA_DIR / "firmes"
EXIGIBLES_DIR = DATA_DIR / "exigibles"
ZIP_UPLOAD_DIR = DATA_DIR / "zip_uploads"
EXPORT_DIR = DATA_DIR / "exports"
for d in (DATA_DIR, FIRMES_DIR, EXIGIBLES_DIR, ZIP_UPLOAD_DIR, EXPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)

XML_DB_PATH = DATA_DIR / "xml_index.db"
FIRMES_MANIFEST_PATH = FIRMES_DIR / "manifest.json"
EXIGIBLES_MANIFEST_PATH = EXIGIBLES_DIR / "manifest.json"

# Parámetros
DEFAULT_BATCH = 150
POLL_INTERVAL = 0.7
HEARTBEAT_MAX_AGE = 10  # s

# =============================================================================
# Estilos locales
# =============================================================================
st.markdown("""
<style>
h1.titulo{font:700 1.9rem/1.2 ui-sans-serif;text-align:center;margin:.5rem 0 .75rem}
.card{border:1px solid #e5e7eb;background:#fafafa;border-radius:12px;padding:1rem;margin:.75rem 0}
.hdr{font:700 1rem ui-sans-serif;margin-bottom:.5rem}
.stepok{color:#065f46;font-weight:700}
.stepbad{color:#991b1b;font-weight:700}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="titulo">Lista Negra SAT — Proceso con pasos</h1>', unsafe_allow_html=True)

# =============================================================================
# Utils XML / Excel / DB
# =============================================================================
def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag

def _safe_float(value) -> float | None:
    try:
        if value is None: return None
        v = str(value).strip()
        if not v: return None
        return float(v.replace(",", ""))
    except Exception:
        return None

def _normalize_status(value: str | None) -> str:
    if not value: return "Activo"
    txt = value.strip()
    if not txt: return "Activo"
    u = txt.upper()
    if "CANCEL" in u: return "Cancelado"
    if "ACT" in u: return "Activo"
    return txt

def parse_emisor_from_xml_stream(fp) -> tuple[str | None, str | None, str | None, float | None, str]:
    try:
        fecha = None; total = None; estatus = None; emisor_rfc = None; emisor_nombre = None
        it = ET.iterparse(fp, events=("start",))
        for _, el in it:
            tag = _local_tag(el.tag).lower()
            if tag == "comprobante":
                if fecha is None:
                    fecha = el.attrib.get("Fecha") or el.attrib.get("fecha") or el.attrib.get("FechaTimbrado")
                if total is None:
                    total = _safe_float(el.attrib.get("Total") or el.attrib.get("total") or el.attrib.get("Monto"))
                if estatus is None:
                    estatus = el.attrib.get("Estado") or el.attrib.get("estado") or el.attrib.get("Estatus") or el.attrib.get("estatus")
            if tag == "emisor":
                emisor_rfc = el.attrib.get("Rfc") or el.attrib.get("RFC") or el.attrib.get("rfc")
                emisor_nombre = el.attrib.get("Nombre") or el.attrib.get("NOMBRE") or el.attrib.get("nombre")
                break
        return (
            (emisor_rfc or "").strip() or None,
            (emisor_nombre or "").strip() or None,
            fecha.strip() if isinstance(fecha, str) else fecha,
            total,
            _normalize_status(estatus),
        )
    except ET.ParseError:
        return None, None, None, None, "Activo"

def _db_init(db_path: Path):
    with closing(sqlite3.connect(str(db_path))) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS xml_emisores(
            filename TEXT NOT NULL,
            sha1 TEXT NOT NULL,
            rfc TEXT,
            nombre TEXT,
            fecha TEXT,
            total REAL,
            estatus TEXT,
            PRIMARY KEY(sha1))""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_rfc ON xml_emisores(rfc)")
        con.commit()

def _sha1(b: bytes) -> str:
    h = hashlib.sha1(); h.update(b); return h.hexdigest()

def bulk_index_zip(zip_path: Path, db_path: Path, *, progress_cb=None, batch: int = 200) -> tuple[int,int,float]:
    _db_init(db_path)
    t0 = time.time()
    processed = 0; inserted = 0; total_files = 0
    with zipfile.ZipFile(str(zip_path), "r") as zf, closing(sqlite3.connect(str(db_path))) as con:
        cur = con.cursor()
        files = [i for i in zf.infolist() if (not i.is_dir()) and i.filename.lower().endswith(".xml")]
        total_files = len(files)
        buf = []
        for info in files:
            with zf.open(info, "r") as fp:
                raw = fp.read()
            sha = _sha1(raw)
            rfc, nom, fecha, total_xml, estatus = parse_emisor_from_xml_stream(io.BytesIO(raw))
            buf.append((info.filename, sha, (rfc or "").strip(), (nom or "").strip(), fecha, total_xml, estatus))
            if len(buf) >= batch:
                cur.executemany(
                    "INSERT OR IGNORE INTO xml_emisores(filename,sha1,rfc,nombre,fecha,total,estatus) VALUES(?,?,?,?,?,?,?)",
                    buf
                )
                con.commit()
                inserted += cur.rowcount or 0
                processed += len(buf)
                buf.clear()
                if progress_cb: progress_cb(processed, total_files, inserted)
        if buf:
            cur.executemany(
                "INSERT OR IGNORE INTO xml_emisores(filename,sha1,rfc,nombre,fecha,total,estatus) VALUES(?,?,?,?,?,?,?)",
                buf
            )
            con.commit()
            inserted += cur.rowcount or 0
            processed += len(buf)
            buf.clear()
            if progress_cb: progress_cb(processed, total_files, inserted)
    return processed, inserted, time.time() - t0

def index_doc_count(db_path: Path) -> int:
    if not db_path.exists(): return 0
    with closing(sqlite3.connect(str(db_path))) as con:
        return int(con.execute("SELECT COUNT(*) FROM xml_emisores").fetchone()[0] or 0)

def index_rfc_count(db_path: Path) -> int:
    if not db_path.exists(): return 0
    with closing(sqlite3.connect(str(db_path))) as con:
        return int(con.execute("SELECT COUNT(DISTINCT rfc) FROM xml_emisores WHERE IFNULL(rfc,'')<>''").fetchone()[0] or 0)

def _chunked(iterable, size=500):
    bucket=[]
    for item in iterable:
        bucket.append(item)
        if len(bucket)>=size:
            yield bucket; bucket=[]
    if bucket: yield bucket

def _load_xml_matches_from_db(db_path: Path, rfcs: list[str]) -> pd.DataFrame:
    columns = ["Archivo XML","RFC Emisor","Nombre Emisor","Fecha Timbrado","Total","Estatus"]
    rfcs = [r.strip() for r in rfcs if isinstance(r,str) and r.strip()]
    if not rfcs: return pd.DataFrame(columns=columns)
    frames=[]
    with closing(sqlite3.connect(str(db_path))) as con:
        for batch in _chunked(rfcs, 800):
            placeholders = ",".join("?" for _ in batch)
            q = ("SELECT filename AS 'Archivo XML', rfc AS 'RFC Emisor', nombre AS 'Nombre Emisor', "
                 "fecha AS 'Fecha Timbrado', total AS 'Total', estatus AS 'Estatus' "
                 f"FROM xml_emisores WHERE rfc IN ({placeholders})")
            frames.append(pd.read_sql_query(q, con, params=batch))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)

def build_excel_bytes(xml_source: Path, df_black: pd.DataFrame) -> bytes:
    # usa la BD para traer coincidencias y construir hojas
    resumen_columns = ["RFC","PROVEEDOR","FECHA (FIRMES)","IMPORTE"]
    desglose_columns = ["Situacion","Fecha Timbrado","RFC Emisor","Razon Social Emisor","Total","Estatus"]

    blk = df_black.copy()
    if not blk.empty and "RFC" in blk.columns:
        blk["RFC"] = blk["RFC"].astype(str).str.strip()
    else:
        blk = pd.DataFrame(columns=["RFC"])

    xml_df = _load_xml_matches_from_db(xml_source, blk["RFC"].dropna().unique().tolist()) if not blk.empty else pd.DataFrame()
    if xml_df.empty or blk.empty:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as w:
            pd.DataFrame(columns=resumen_columns).to_excel(w, index=False, sheet_name="Coincidencias")
            pd.DataFrame(columns=desglose_columns).to_excel(w, index=False, sheet_name="Desglose")
        return out.getvalue()

    xml_df["RFC Emisor"] = xml_df["RFC Emisor"].astype(str).str.strip()
    xml_df["Total"] = pd.to_numeric(xml_df.get("Total"), errors="coerce").fillna(0.0)
    rfcs_xml = xml_df["RFC Emisor"].dropna().unique().tolist()

    coincidencias = blk[blk["RFC"].isin(rfcs_xml)].copy()
    resumen_df = pd.DataFrame(columns=resumen_columns)
    situacion_map={}
    rfcs_coincidentes=[]
    if not coincidencias.empty:
        rfcs_coincidentes = coincidencias["RFC"].dropna().astype(str).str.strip().unique().tolist()
        if "SUPUESTO" in coincidencias.columns:
            situacion_map = coincidencias.groupby("RFC")["SUPUESTO"].first().astype(str).str.strip().str.upper().to_dict()
        c_ord = coincidencias.copy()
        if "FECHA DE PRIMERA PUBLICACION" in c_ord.columns:
            c_ord = c_ord.sort_values("FECHA DE PRIMERA PUBLICACION", ascending=False)
        resumen_df = c_ord.groupby("RFC", as_index=False).first()
        resumen_df = resumen_df.drop(columns=["TIPO PERSONA","ENTIDAD FEDERATIVA","SUPUESTO"], errors="ignore")
        resumen_df = resumen_df.rename(columns={"RAZON SOCIAL":"PROVEEDOR","FECHA DE PRIMERA PUBLICACION":"FECHA (FIRMES)"})
        if "FECHA (FIRMES)" in resumen_df.columns:
            resumen_df["FECHA (FIRMES)"] = pd.to_datetime(resumen_df["FECHA (FIRMES)"], errors="coerce").dt.date
        resumen_df["IMPORTE"] = resumen_df["RFC"].map(
            xml_df[xml_df["RFC Emisor"].isin(rfcs_coincidentes)].groupby("RFC Emisor")["Total"].sum()
        ).fillna(0.0)
        keep = [c for c in ["RFC","PROVEEDOR","FECHA (FIRMES)","IMPORTE"] if c in resumen_df.columns]
        resumen_df = resumen_df[keep] if keep else resumen_df
        if "RFC" in resumen_df.columns: resumen_df.sort_values("RFC", inplace=True)

    desglose_df = (xml_df[xml_df["RFC Emisor"].isin(rfcs_coincidentes)].copy()
                   if rfcs_coincidentes else xml_df.iloc[0:0].copy())
    desglose_df["Situacion"] = desglose_df["RFC Emisor"].map(situacion_map).fillna("DESCONOCIDO") if situacion_map else "DESCONOCIDO"
    desglose_df = desglose_df.rename(columns={"Nombre Emisor":"Razon Social Emisor"})
    if "Fecha Timbrado" in desglose_df.columns:
        desglose_df["Fecha Timbrado"] = pd.to_datetime(desglose_df["Fecha Timbrado"], errors="coerce").dt.date
    desglose_df["Total"] = pd.to_numeric(desglose_df.get("Total"), errors="coerce").fillna(0.0)
    for col, default in [("Fecha Timbrado", pd.NaT), ("Razon Social Emisor",""), ("Estatus","Activo")]:
        if col not in desglose_df.columns: desglose_df[col] = default
    for col in desglose_columns:
        if col not in desglose_df.columns:
            if col=="Total": desglose_df[col]=0.0
            elif col=="Fecha Timbrado": desglose_df[col]=pd.NaT
            elif col=="Situacion": desglose_df[col]="DESCONOCIDO"
            else: desglose_df[col]=""
    if not desglose_df.empty:
        desglose_df.sort_values(["RFC Emisor","Fecha Timbrado"], inplace=True, kind="mergesort")
    desglose_df = desglose_df[desglose_columns]

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        resumen_df.to_excel(w, index=False, sheet_name="Coincidencias")
        desglose_df.to_excel(w, index=False, sheet_name="Desglose")
    return out.getvalue()

# =============================================================================
# Firmes/Exigibles — autodetección + manifest y subida directa
# =============================================================================
def _read_manifest(manifest_path: Path) -> dict | None:
    if manifest_path.exists():
        try: return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception: return None
    return None

def _write_manifest(manifest_path: Path, stored_as: str) -> None:
    try:
        manifest_path.write_text(json.dumps({"stored_as": stored_as}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _looks_like_sat_file(path: Path) -> bool:
    try:
        n = path.name.lower()
        if n.endswith(".csv"):
            df = pd.read_csv(path, nrows=50, encoding="latin-1")
        elif n.endswith((".xlsx",".xls")):
            df = pd.read_excel(path, nrows=50)
        else:
            return False
        return isinstance(df, pd.DataFrame) and ("RFC" in df.columns)
    except Exception:
        return False

def _find_best_sat_file(base_dir: Path, manifest_path: Path) -> Path | None:
    m = _read_manifest(manifest_path)
    if m and m.get("stored_as"):
        cand = base_dir / m["stored_as"]
        if cand.exists() and _looks_like_sat_file(cand): return cand
    files = list(base_dir.glob("*.csv")) + list(base_dir.glob("*.xlsx")) + list(base_dir.glob("*.xls"))
    if not files: return None
    def score(p: Path) -> tuple[int,float]:
        n = p.name.lower()
        kw = 2 if ("firmes" in n or "firme" in n or "exigible" in n or "exigibles" in n) else 1
        return (kw, p.stat().st_mtime)
    files.sort(key=score, reverse=True)
    for f in files:
        if _looks_like_sat_file(f):
            _write_manifest(manifest_path, f.name)
            return f
    return None

def _load_sat_reference_from_path(path: Path) -> pd.DataFrame:
    n = path.name.lower()
    if n.endswith(".csv"):
        df = pd.read_csv(path, encoding="latin-1")
    elif n.endswith((".xlsx",".xls")):
        df = pd.read_excel(path)
    else:
        return pd.DataFrame()
    if df.empty or "RFC" not in df.columns: return pd.DataFrame()
    df["RFC"] = df["RFC"].astype(str).str.strip()
    return df

def _load_sat_reference(manifest_path: Path, base_dir: Path) -> pd.DataFrame:
    best = _find_best_sat_file(base_dir, manifest_path)
    if not best: return pd.DataFrame()
    try: return _load_sat_reference_from_path(best)
    except Exception: return pd.DataFrame()

def load_firmes_from_disk() -> pd.DataFrame:
    return _load_sat_reference(FIRMES_MANIFEST_PATH, FIRMES_DIR)

def load_exigibles_from_disk() -> pd.DataFrame:
    return _load_sat_reference(EXIGIBLES_MANIFEST_PATH, EXIGIBLES_DIR)

def _has_rfc_column(df: pd.DataFrame | None) -> bool:
    return isinstance(df, pd.DataFrame) and (not df.empty) and ("RFC" in df.columns)

def _combine_blacklists(*dfs: pd.DataFrame) -> pd.DataFrame:
    frames=[]
    for df in dfs:
        if _has_rfc_column(df):
            f = df.copy(); f["RFC"] = f["RFC"].astype(str).str.strip(); frames.append(f)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# =============================================================================
# Estado y helpers de la UI por pasos
# =============================================================================
ss = st.session_state
def _init_state():
    ss.setdefault("firmes_df", load_firmes_from_disk())
    ss.setdefault("exigibles_df", load_exigibles_from_disk())
    ss["blacklist_df"] = _combine_blacklists(ss.get("firmes_df"), ss.get("exigibles_df"))
    ss.setdefault("uploader_nonce", 0)
    # pasos
    ss.setdefault("step1_zip_path", "")       # ruta al ZIP guardado
    ss.setdefault("step2_done", False)        # índice leído
    ss.setdefault("step3_done", False)        # cruce listo
    ss.setdefault("step4_ready", False)       # excel listo
    ss.setdefault("excel_path", "")
    ss.setdefault("last_error", "")
    ss.setdefault("last_trace", "")
    ss.setdefault("progress_info", {"processed":0,"total":0,"inserted":0})
_init_state()

def _reset_after_download():
    # limpiezas suaves, conservando archivos de referencia
    ss["uploader_nonce"] += 1
    ss["step1_zip_path"] = ""
    ss["step2_done"] = False
    ss["step3_done"] = False
    ss["step4_ready"] = False
    ss["excel_path"] = ""
    ss["last_error"] = ""
    ss["last_trace"] = ""
    ss["progress_info"] = {"processed":0,"total":0,"inserted":0}

# =============================================================================
# Paso 0 — Subir Firmes / Exigibles
# =============================================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="hdr">Paso 0) Subir archivos SAT (Firmes / Exigibles)</div>', unsafe_allow_html=True)

def _has_rfc_column_in_upload(uploaded_file) -> bool:
    name = (uploaded_file.name or "").lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, nrows=50, encoding="latin-1")
        elif name.endswith((".xlsx",".xls")):
            df = pd.read_excel(uploaded_file, nrows=50)
        else:
            return False
        return isinstance(df, pd.DataFrame) and ("RFC" in df.columns)
    except Exception:
        return False

c1, c2 = st.columns(2)
with c1:
    st.caption("Sube **Firmes** (.csv/.xlsx/.xls). Debe incluir columna `RFC`.")
    up_firmes = st.file_uploader("Firmes", type=["csv","xlsx","xls"], key=f"up_firmes_{ss['uploader_nonce']}")
    if up_firmes is not None:
        try:
            if not _has_rfc_column_in_upload(up_firmes):
                st.error("El archivo Firmes no tiene columna `RFC`.")
            else:
                safe_name = f"firmes_{int(time.time())}_{Path(up_firmes.name).name}"
                dest = FIRMES_DIR / safe_name
                up_firmes.seek(0)
                with dest.open("wb") as fh:
                    shutil.copyfileobj(up_firmes, fh, length=1024*1024)
                _write_manifest(FIRMES_MANIFEST_PATH, safe_name)
                ss["firmes_df"] = load_firmes_from_disk()
                ss["blacklist_df"] = _combine_blacklists(ss.get("firmes_df"), ss.get("exigibles_df"))
                st.success(f"Firmes cargado: {safe_name}")
        except Exception as exc:
            ss["last_error"] = f"Firmes: {exc}"
            ss["last_trace"] = traceback.format_exc()
            st.exception(exc)

with c2:
    st.caption("Sube **Exigibles** (.csv/.xlsx/.xls). Debe incluir columna `RFC`.")
    up_exig = st.file_uploader("Exigibles", type=["csv","xlsx","xls"], key=f"up_exigibles_{ss['uploader_nonce']}")
    if up_exig is not None:
        try:
            if not _has_rfc_column_in_upload(up_exig):
                st.error("El archivo Exigibles no tiene columna `RFC`.")
            else:
                safe_name = f"exigibles_{int(time.time())}_{Path(up_exig.name).name}"
                dest = EXIGIBLES_DIR / safe_name
                up_exig.seek(0)
                with dest.open("wb") as fh:
                    shutil.copyfileobj(up_exig, fh, length=1024*1024)
                _write_manifest(EXIGIBLES_MANIFEST_PATH, safe_name)
                ss["exigibles_df"] = load_exigibles_from_disk()
                ss["blacklist_df"] = _combine_blacklists(ss.get("firmes_df"), ss.get("exigibles_df"))
                st.success(f"Exigibles cargado: {safe_name}")
        except Exception as exc:
            ss["last_error"] = f"Exigibles: {exc}"
            ss["last_trace"] = traceback.format_exc()
            st.exception(exc)

tengo_firmes = _has_rfc_column(ss.get("firmes_df"))
tengo_exigibles = _has_rfc_column(ss.get("exigibles_df"))
if not (tengo_firmes and tengo_exigibles):
    st.warning("Aún faltan **Firmes** y/o **Exigibles** para poder cruzar datos.")
st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# Paso 1 — Cargar ZIP (solo guardar archivo)
# =============================================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="hdr">Paso 1) Cargar archivo ZIP de XML</div>', unsafe_allow_html=True)

def _on_pick_zip():
    key = f"zip_pick_{ss['uploader_nonce']}"
    up = ss.get(key)
    if not up:
        return
    try:
        safe_name = Path(getattr(up, "name", "cfdi.zip") or "cfdi.zip").name
        dest = ZIP_UPLOAD_DIR / f"{int(time.time()*1000)}_{safe_name}"
        up.seek(0)
        with dest.open("wb") as fh:
            shutil.copyfileobj(up, fh, length=1024*1024)
        ss["step1_zip_path"] = str(dest)
        ss["step2_done"] = False
        ss["step3_done"] = False
        ss["step4_ready"] = False
        ss["excel_path"] = ""
        ss["last_error"] = ""
        ss["last_trace"] = ""
        ss["progress_info"] = {"processed":0,"total":0,"inserted":0}
        st.success(f"ZIP guardado: {dest.name}")
    except Exception as exc:
        ss["last_error"] = f"Cargar ZIP: {exc}"
        ss["last_trace"] = traceback.format_exc()
        st.exception(exc)

zip_key = f"zip_pick_{ss['uploader_nonce']}"
st.file_uploader("Selecciona el ZIP (no se procesa hasta el paso 2)", type=["zip"], key=zip_key, on_change=_on_pick_zip)
if ss.get("step1_zip_path"):
    p = Path(ss["step1_zip_path"])
    st.caption(f"Archivo seleccionado: **{p.name}** ({p.stat().st_size/1024/1024:,.2f} MB)")
else:
    st.info("Selecciona un archivo ZIP para continuar con el paso 2.")
st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# Paso 2 — Leer XML (indexar ZIP a SQLite) + Reintentar
# =============================================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="hdr">Paso 2) Leer XML del ZIP e indexar</div>', unsafe_allow_html=True)

# Worker simple con heartbeat y retry manual
_ZIP_JOBS: Dict[str, Dict[str, Any]] = {}
_ZIP_LOCK = threading.Lock()

def _job_update(job_id: str, **payload):
    payload.setdefault("heartbeat", int(time.time()))
    with _ZIP_LOCK:
        if job_id in _ZIP_JOBS:
            _ZIP_JOBS[job_id].update(payload)

def _job_get(job_id: str) -> Dict[str, Any] | None:
    with _ZIP_LOCK:
        return dict(_ZIP_JOBS.get(job_id) or {}) or None

def _job_start(zip_path: Path, batch: int = DEFAULT_BATCH) -> str:
    job_id = f"{int(time.time()*1000)}_{uuid4().hex}"
    with _ZIP_LOCK:
        _ZIP_JOBS[job_id] = {
            "status":"queued","progress":0.0,"processed":0,"inserted":0,"total":0,
            "zip_path":str(zip_path),"error":None,"heartbeat":int(time.time()),"batch":batch
        }
    threading.Thread(target=_job_worker, args=(job_id,zip_path,batch), daemon=True).start()
    return job_id

def _job_worker(job_id: str, zip_path: Path, batch: int):
    def _progress(processed:int, total:int, inserted:int):
        prog = (processed / max(1,total)) if total else 0.0
        _job_update(job_id, processed=processed, total=total, inserted=inserted, progress=prog)
    try:
        _job_update(job_id, status="running")
        processed, inserted, secs = bulk_index_zip(zip_path, XML_DB_PATH, progress_cb=_progress, batch=batch)
        _job_update(job_id, status="done", seconds=secs, processed=processed, total=processed, inserted=inserted, progress=1.0)
    except Exception as exc:
        _job_update(job_id, status="error", error=str(exc))

def _job_restart(job_id: str):
    rec = _job_get(job_id)
    if not rec: return
    zp = Path(rec["zip_path"])
    if not zp.exists(): return
    _job_update(job_id, status="queued", error=None, progress=0.0, processed=0, inserted=0, total=0)
    threading.Thread(target=_job_worker, args=(job_id,zp,int(rec.get("batch") or DEFAULT_BATCH)), daemon=True).start()

# UI botones paso 2
col_2a, col_2b, col_2c = st.columns([0.4,0.3,0.3])
if col_2a.button("📖 Leer XML (indexar ZIP)", use_container_width=True, disabled=not ss.get("step1_zip_path")):
    try:
        # borrar BD anterior para pruebas limpias
        if XML_DB_PATH.exists(): XML_DB_PATH.unlink()
        job_id = _job_start(Path(ss["step1_zip_path"]), batch=DEFAULT_BATCH)
        ss["zip_job_id"] = job_id
        ss["step2_done"] = False
        ss["last_error"] = ""
        ss["last_trace"] = ""
    except Exception as exc:
        ss["last_error"] = f"Leer XML: {exc}"
        ss["last_trace"] = traceback.format_exc()
        st.exception(exc)

if col_2b.button("🔁 Reintentar lectura", use_container_width=True, disabled=not ss.get("zip_job_id")):
    try:
        _job_restart(ss["zip_job_id"])
    except Exception as exc:
        ss["last_error"] = f"Reintentar: {exc}"
        ss["last_trace"] = traceback.format_exc()
        st.exception(exc)

if col_2c.button("🧹 Limpiar índice", use_container_width=True):
    try:
        if XML_DB_PATH.exists(): XML_DB_PATH.unlink()
        ss["step2_done"] = False
        st.success("Índice limpio.")
    except Exception as exc:
        ss["last_error"] = f"Limpiar índice: {exc}"
        ss["last_trace"] = traceback.format_exc()
        st.exception(exc)

job_id = ss.get("zip_job_id")
if job_id:
    info = _job_get(job_id)
    if info:
        st.progress(float(info.get("progress") or 0.0))
        pr = int(info.get("processed") or 0); tot = int(info.get("total") or 0); ins = int(info.get("inserted") or 0)
        st.caption(f"Progreso: {pr:,}/{tot:,} (insertados {ins:,}) | estado: {info.get('status')}")
        if info.get("status") in {"queued","running"}:
            time.sleep(POLL_INTERVAL)
            st.rerun()
        elif info.get("status") == "done":
            ss["step2_done"] = True
            st.success(f"Lectura OK — XML indexados: {index_doc_count(XML_DB_PATH):,} | RFC únicos: {index_rfc_count(XML_DB_PATH):,}")
        elif info.get("status") == "error":
            ss["last_error"] = f"Lectura ZIP: {info.get('error')}"
            st.error(f"Error al leer ZIP: {info.get('error')}")
else:
    st.info("Inicia la lectura con el botón **Leer XML (indexar ZIP)**.")

st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# Paso 3 — Cruzar datos
# =============================================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="hdr">Paso 3) Cruzar datos (XML vs Firmes/Exigibles)</div>', unsafe_allow_html=True)

col3a, col3b = st.columns([0.5,0.5])
with col3a:
    if st.button("🔍 Cruzar datos", use_container_width=True, disabled=not (ss.get("step2_done") and _has_rfc_column(ss.get("blacklist_df")))):
        try:
            # simple prueba de consulta para verificar cruce
            blk = ss["blacklist_df"]
            rfcs = blk["RFC"].dropna().astype(str).str.strip().unique().tolist() if "RFC" in blk.columns else []
            if not rfcs:
                st.warning("No hay RFC en Firmes/Exigibles.")
            else:
                df_match = _load_xml_matches_from_db(XML_DB_PATH, rfcs)
                ss["step3_done"] = True
                st.success(f"Cruce OK: {len(df_match):,} filas coincidentes.")
                with st.expander("Ver muestra de coincidencias (hasta 20)", expanded=False):
                    st.dataframe(df_match.head(20), use_container_width=True)
        except Exception as exc:
            ss["last_error"] = f"Cruzar datos: {exc}"
            ss["last_trace"] = traceback.format_exc()
            st.exception(exc)

with col3b:
    st.caption("Requisitos: haber completado el **Paso 2** y contar con **Firmes/Exigibles** válidos (columna `RFC`).")

st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# Paso 4 — Descargar Excel
# =============================================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="hdr">Paso 4) Descargar Excel</div>', unsafe_allow_html=True)

col4a, col4b = st.columns([0.55,0.45])

with col4a:
    if st.button("🧾 Generar Excel", use_container_width=True, disabled=not (ss.get("step2_done") and _has_rfc_column(ss.get("blacklist_df")))):
        try:
            bytes_data = build_excel_bytes(XML_DB_PATH, ss["blacklist_df"])
            export_name = f"Cruce_RFC_vs_Lista_Negra_SAT_{int(time.time()*1000)}.xlsx"
            export_path = EXPORT_DIR / export_name
            export_path.write_bytes(bytes_data)
            ss["excel_path"] = str(export_path)
            ss["step4_ready"] = True
            st.success("Excel generado. Puedes descargarlo.")
        except Exception as exc:
            ss["last_error"] = f"Generar Excel: {exc}"
            ss["last_trace"] = traceback.format_exc()
            st.exception(exc)

with col4b:
    if ss.get("step4_ready") and ss.get("excel_path") and Path(ss["excel_path"]).exists():
        try:
            data_bytes = Path(ss["excel_path"]).read_bytes()
            st.download_button(
                "⬇️ Descargar Excel",
                data=data_bytes,
                file_name=Path(ss["excel_path"]).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_xlsx_final",
                on_click=_reset_after_download,
            )
        except Exception as exc:
            ss["last_error"] = f"Descargar Excel: {exc}"
            ss["last_trace"] = traceback.format_exc()
            st.exception(exc)
    else:
        st.info("Primero genera el Excel.")

st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# Panel de depuración
# =============================================================================
with st.expander("🛠️ Depuración / Estado interno", expanded=False):
    st.write("**Rutas**")
    st.code(f"DATA_DIR         = {DATA_DIR}\nXML_DB_PATH      = {XML_DB_PATH}\nZIP_UPLOAD_DIR   = {ZIP_UPLOAD_DIR}\nEXPORT_DIR       = {EXPORT_DIR}\nFIRMES_DIR       = {FIRMES_DIR}\nEXIGIBLES_DIR    = {EXIGIBLES_DIR}", language="bash")
    st.write("**Paso 1**")
    st.json({"step1_zip_path": ss.get("step1_zip_path")})
    st.write("**Paso 2**")
    st.json({"step2_done": ss.get("step2_done"), "xml_docs": index_doc_count(XML_DB_PATH), "xml_rfcs": index_rfc_count(XML_DB_PATH)})
    st.write("**Paso 3**")
    st.json({"step3_done": ss.get("step3_done"), "have_blacklist": _has_rfc_column(ss.get("blacklist_df"))})
    st.write("**Paso 4**")
    st.json({"step4_ready": ss.get("step4_ready"), "excel_path": ss.get("excel_path")})
    if ss.get("last_error"):
        st.error(ss["last_error"])
        if ss.get("last_trace"):
            with st.expander("Traceback"):
                st.code(ss["last_trace"], language="python")
