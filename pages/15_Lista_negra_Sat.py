# 15_Lista_negra_Sat.py — ZIP XML automático + counters poscarga + reset total tras descarga
from __future__ import annotations

import io, json, time, hashlib, zipfile, sqlite3
from contextlib import closing
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

# Ajusta si tu proyecto no usa este helper:
from pages.components.admin import init_admin_section

# ------------------ Paths ------------------
DATA_DIR = Path("data"); DATA_DIR.mkdir(parents=True, exist_ok=True)
FIRMES_DIR = DATA_DIR / "firmes"; FIRMES_DIR.mkdir(parents=True, exist_ok=True)
FIRMES_MANIFEST_PATH = FIRMES_DIR / "manifest.json"
EXIGIBLES_DIR = DATA_DIR / "exigibles"; EXIGIBLES_DIR.mkdir(parents=True, exist_ok=True)
EXIGIBLES_MANIFEST_PATH = EXIGIBLES_DIR / "manifest.json"
XML_DB_PATH = DATA_DIR / "xml_index.db"   # índice SQLite

# ------------------ Init Page ------------------
init_admin_section(
    page_title="Monitoreo EFOS - Cruce de RFC",
    active_top="monitoreo",
    layout="wide",
    show_inicio=False,
)

# ------------------ CSS ------------------
st.markdown("""
<style>
.main .block-container{max-width:980px;padding-top:1rem;padding-bottom:1rem}
h1.titulo{font:700 1.9rem/1.2 ui-sans-serif;text-align:center;margin:0 0 .75rem}
.card{border:1px solid #e5e7eb;background:#fafafa;border-radius:12px;padding:1rem;margin:.5rem 0}
.hdr{font:700 1rem ui-sans-serif;margin-bottom:.5rem}
.descargar-excel-box div.stDownloadButton>button{width:100%;height:56px;font-size:1rem;font-weight:700}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="titulo">Cruce de RFC con Lista Negra del SAT</h1>', unsafe_allow_html=True)

# ------------------ Helpers ------------------
def _local_tag(tag:str)->str: 
    return tag.split("}",1)[1] if "}" in tag else tag

def _safe_float(value)->float|None:
    try:
        if value is None:
            return None
        v = str(value).strip()
        if not v:
            return None
        return float(v.replace(",", ""))
    except Exception:
        return None

def _normalize_status(value:str|None)->str:
    if not value:
        return "Activo"
    txt = value.strip()
    if not txt:
        return "Activo"
    upper = txt.upper()
    if "CANCEL" in upper:
        return "Cancelado"
    if "ACT" in upper:
        return "Activo"
    return txt

def parse_emisor_from_xml_stream(fp)->tuple[str|None,str|None,str|None,float|None,str]:
    """Streaming: extrae datos relevantes del comprobante sin cargarlo completo."""
    try:
        fecha = None
        total = None
        estatus: str | None = None
        emisor_rfc = None
        emisor_nombre = None
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

def build_excel_bytes(df_xml:pd.DataFrame, df_black:pd.DataFrame)->bytes:
    resumen_columns = ["RFC", "PROVEEDOR", "FECHA (FIRMES)", "IMPORTE"]
    desglose_columns = ["Situacion", "Fecha Timbrado", "RFC Emisor", "Razon Social Emisor", "Total", "Estatus"]

    if df_xml.empty:
        out_empty = io.BytesIO()
        with pd.ExcelWriter(out_empty, engine="xlsxwriter") as w:
            pd.DataFrame(columns=resumen_columns).to_excel(w, index=False, sheet_name="Coincidencias")
            pd.DataFrame(columns=desglose_columns).to_excel(w, index=False, sheet_name="Desglose")
        return out_empty.getvalue()

    xml_df = df_xml.copy()
    xml_df["RFC Emisor"] = xml_df["RFC Emisor"].astype(str).str.strip()
    xml_df["Total"] = pd.to_numeric(xml_df.get("Total"), errors="coerce").fillna(0.0)
    rfcs_xml = xml_df["RFC Emisor"].dropna().unique().tolist()

    blk = df_black.copy()
    if not blk.empty:
        blk["RFC"] = blk["RFC"].astype(str).str.strip()
    coincidencias = blk[blk["RFC"].isin(rfcs_xml)].copy() if not blk.empty else pd.DataFrame()

    resumen_df = pd.DataFrame(columns=resumen_columns)
    situacion_map: dict[str, str] = {}
    rfcs_coincidentes: list[str] = []
    if not coincidencias.empty:
        rfcs_coincidentes = (
            coincidencias["RFC"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )
        if "SUPUESTO" in coincidencias.columns:
            situacion_map = (
                coincidencias.groupby("RFC")["SUPUESTO"]
                .first()
                .astype(str)
                .str.strip()
                .str.upper()
                .to_dict()
            )
        coincidencias_ordenadas = coincidencias.copy()
        if "FECHA DE PRIMERA PUBLICACION" in coincidencias_ordenadas.columns:
            coincidencias_ordenadas = coincidencias_ordenadas.sort_values(
                "FECHA DE PRIMERA PUBLICACION", ascending=False
            )
        resumen_df = coincidencias_ordenadas.groupby("RFC", as_index=False).first()
        resumen_df = resumen_df.drop(columns=["TIPO PERSONA", "ENTIDAD FEDERATIVA", "SUPUESTO"], errors="ignore")
        resumen_df = resumen_df.rename(
            columns={
                "RAZON SOCIAL": "PROVEEDOR",
                "FECHA DE PRIMERA PUBLICACION": "FECHA (FIRMES)",
            }
        )
        if "FECHA (FIRMES)" in resumen_df.columns:
            resumen_df["FECHA (FIRMES)"] = pd.to_datetime(
                resumen_df["FECHA (FIRMES)"], errors="coerce"
            ).dt.date
        resumen_df["IMPORTE"] = resumen_df["RFC"].map(
            xml_df[xml_df["RFC Emisor"].isin(rfcs_coincidentes)].groupby("RFC Emisor")["Total"].sum()
        ).fillna(0.0)
        desired_cols = [c for c in ["RFC", "PROVEEDOR", "FECHA (FIRMES)", "IMPORTE"] if c in resumen_df.columns]
        resumen_df = resumen_df[desired_cols] if desired_cols else resumen_df
        if "RFC" in resumen_df.columns:
            resumen_df.sort_values("RFC", inplace=True)

    desglose_df = xml_df[xml_df["RFC Emisor"].isin(rfcs_coincidentes)].copy() if rfcs_coincidentes else xml_df.iloc[0:0].copy()
    if situacion_map:
        desglose_df["Situacion"] = desglose_df["RFC Emisor"].map(situacion_map).fillna("DESCONOCIDO")
    else:
        desglose_df["Situacion"] = "DESCONOCIDO"
    desglose_df = desglose_df.rename(
        columns={
            "Fecha Timbrado": "Fecha Timbrado",
            "Nombre Emisor": "Razon Social Emisor",
        }
    )
    if "Fecha Timbrado" in desglose_df.columns:
        desglose_df["Fecha Timbrado"] = pd.to_datetime(
            desglose_df["Fecha Timbrado"], errors="coerce"
        ).dt.date
    desglose_df["Total"] = pd.to_numeric(desglose_df.get("Total"), errors="coerce").fillna(0.0)
    for col, default in [
        ("Fecha Timbrado", pd.NaT),
        ("Razon Social Emisor", ""),
        ("Estatus", "Activo"),
    ]:
        if col not in desglose_df.columns:
            desglose_df[col] = default
    for col in desglose_columns:
        if col not in desglose_df.columns:
            if col == "Total":
                desglose_df[col] = 0.0
            elif col == "Fecha Timbrado":
                desglose_df[col] = pd.NaT
            elif col == "Situacion":
                desglose_df[col] = "DESCONOCIDO"
            else:
                desglose_df[col] = ""
    if not desglose_df.empty:
        desglose_df.sort_values(["RFC Emisor", "Fecha Timbrado"], inplace=True, kind="mergesort")
    desglose_df = desglose_df[desglose_columns]

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        resumen_df.to_excel(w, index=False, sheet_name="Coincidencias")
        desglose_df.to_excel(w, index=False, sheet_name="Desglose")
    return out.getvalue()

# ---- Firmes/Exigibles: solo lectura desde manifest ----
def _read_manifest(manifest_path: Path)->dict|None:
    if manifest_path.exists():
        try: 
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception: 
            return None
    return None

def _load_sat_reference(manifest_path: Path, base_dir: Path)->pd.DataFrame:
    manifest = _read_manifest(manifest_path)
    if not manifest: return pd.DataFrame()
    stored_name = manifest.get("stored_as","")
    if not stored_name: return pd.DataFrame()
    p = base_dir / stored_name
    if not p.exists(): return pd.DataFrame()
    try:
        name_lower = p.name.lower()
        if name_lower.endswith(".csv"):
            df = pd.read_csv(p, encoding="latin-1")
        elif name_lower.endswith((".xlsx",".xls")):
            df = pd.read_excel(p)
        else:
            df = pd.read_csv(p, encoding="latin-1")
    except Exception:
        return pd.DataFrame()
    if df.empty or "RFC" not in df.columns: return pd.DataFrame()
    df["RFC"] = df["RFC"].astype(str).str.strip()
    return df

def load_firmes_from_disk()->pd.DataFrame:
    return _load_sat_reference(FIRMES_MANIFEST_PATH, FIRMES_DIR)

def load_exigibles_from_disk()->pd.DataFrame:
    return _load_sat_reference(EXIGIBLES_MANIFEST_PATH, EXIGIBLES_DIR)

def _has_rfc_column(df: pd.DataFrame | None) -> bool:
    return isinstance(df, pd.DataFrame) and (not df.empty) and ("RFC" in df.columns)

def _combine_blacklists(*dfs: pd.DataFrame)->pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for df in dfs:
        if _has_rfc_column(df):
            frame = df.copy()
            frame["RFC"] = frame["RFC"].astype(str).str.strip()
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

# ---- SQLite índice ZIP ----
def _db_init(db_path:Path):
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
        # En caso de que la tabla exista de versiones previas sin las columnas nuevas.
        for col, ddl in (
            ("fecha", "ALTER TABLE xml_emisores ADD COLUMN fecha TEXT"),
            ("total", "ALTER TABLE xml_emisores ADD COLUMN total REAL"),
            ("estatus", "ALTER TABLE xml_emisores ADD COLUMN estatus TEXT"),
        ):
            try:
                con.execute(f"SELECT {col} FROM xml_emisores LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    con.execute(ddl)
                except sqlite3.OperationalError:
                    pass
        con.commit()

def _sha1(b:bytes)->str:
    h=hashlib.sha1(); h.update(b); return h.hexdigest()

def bulk_index_zip(zip_bytes:bytes, db_path:Path, prog=None, batch:int=1000)->tuple[int,int,float]:
    _db_init(db_path); t0=time.time()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf, closing(sqlite3.connect(str(db_path))) as con:
        cur=con.cursor()
        files=[i for i in zf.infolist() if (not i.is_dir()) and i.filename.lower().endswith(".xml")]
        total=len(files); ins=0; proc=0; buf=[]
        for i,info in enumerate(files,1):
            with zf.open(info,"r") as fp:
                raw=fp.read()
            sha=_sha1(raw)
            rfc, nom, fecha, total, estatus = parse_emisor_from_xml_stream(io.BytesIO(raw))
            buf.append(
                (
                    info.filename,
                    sha,
                    (rfc or "").strip(),
                    (nom or "").strip(),
                    fecha,
                    total,
                    estatus,
                )
            )
            if len(buf)>=batch:
                cur.executemany(
                    "INSERT OR IGNORE INTO xml_emisores(filename,sha1,rfc,nombre,fecha,total,estatus) VALUES(?,?,?,?,?,?,?)",
                    buf,
                )
                con.commit(); ins += cur.rowcount or 0; proc += len(buf); buf.clear()
                if prog: prog.progress(min(proc/max(total,1),1.0))
        if buf:
            cur.executemany(
                "INSERT OR IGNORE INTO xml_emisores(filename,sha1,rfc,nombre,fecha,total,estatus) VALUES(?,?,?,?,?,?,?)",
                buf,
            )
            con.commit(); ins += cur.rowcount or 0; proc += len(buf); buf.clear()
            if prog: prog.progress(1.0)
    return proc, ins, time.time()-t0

def index_as_df(db_path:Path, limit:int|None=None)->pd.DataFrame:
    if not db_path.exists(): 
        return pd.DataFrame(columns=["Archivo XML","RFC Emisor","Nombre Emisor"])
    with closing(sqlite3.connect(str(db_path))) as con:
        q="SELECT filename, rfc, nombre, fecha, total, estatus FROM xml_emisores"; 
        if limit: q+=f" LIMIT {int(limit)}"
        df=pd.read_sql_query(q, con)
    return df.rename(
        columns={
            "filename":"Archivo XML",
            "rfc":"RFC Emisor",
            "nombre":"Nombre Emisor",
            "fecha":"Fecha Timbrado",
            "total":"Total",
            "estatus":"Estatus",
        }
    )

def index_doc_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    with closing(sqlite3.connect(str(db_path))) as con:
        n = con.execute("SELECT COUNT(*) FROM xml_emisores").fetchone()[0]
    return int(n or 0)

def index_rfc_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    with closing(sqlite3.connect(str(db_path))) as con:
        n = con.execute(
            "SELECT COUNT(DISTINCT rfc) FROM xml_emisores WHERE rfc IS NOT NULL AND rfc<>''"
        ).fetchone()[0]
    return int(n or 0)

# ------------------ Reset helpers ------------------
def _clear_xml_index_file():
    try:
        if XML_DB_PATH.exists():
            XML_DB_PATH.unlink()
    except Exception:
        pass

def _reset_page_state(keep_reference_data: bool = True):
    """Reinicia buffers y widgets. Cambia el key del uploader para vaciarlo."""
    ss = st.session_state
    # Flags y buffers ZIP
    for k in ["zip_bytes", "zip_selected", "zip_indexing", "zip_done", "post_download_reset"]:
        if k in ss: del ss[k]
    # Data
    ss["parsed_df"] = pd.DataFrame(
        columns=["Archivo XML","RFC Emisor","Nombre Emisor","Fecha Timbrado","Total","Estatus"]
    )
    ss["archivos_xml_nombres"] = []
    if not keep_reference_data:
        ss["firmes_df"] = pd.DataFrame()
        ss["exigibles_df"] = pd.DataFrame()
    ss["blacklist_df"] = _combine_blacklists(
        ss.get("firmes_df"),
        ss.get("exigibles_df"),
    )
    # Forzar que el uploader quede vacío cambiando su key (nonce)
    ss["uploader_nonce"] = ss.get("uploader_nonce", 0) + 1

# ------------------ Estado inicial ------------------
ss = st.session_state
if "init_done" not in ss:
    ss["firmes_df"] = load_firmes_from_disk()
    ss["exigibles_df"] = load_exigibles_from_disk()
    ss["uploader_nonce"] = 0              # base para key dinámico del uploader
    _clear_xml_index_file()               # contadores = 0; no residuos
    _reset_page_state(keep_reference_data=True)   # sin archivos ni contadores visibles
    ss["init_done"] = True

ss["blacklist_df"] = _combine_blacklists(
    ss.get("firmes_df"),
    ss.get("exigibles_df"),
)

# Si venimos de una descarga y se pidió reset, ejecútalo (y rerender)
if ss.get("post_download_reset"):
    _clear_xml_index_file()
    _reset_page_state(keep_reference_data=True)
    ss["post_download_reset"] = False
    st.rerun()

# ------------------ Callbacks ------------------
def _on_zip_selected():
    up = ss.get(f"zip_bulk_uploader_{ss['uploader_nonce']}")
    if not up:
        ss["zip_selected"]=False
        ss["zip_indexing"]=False
        ss["zip_done"]=False
        return
    ss["zip_bytes"] = up.read()
    ss["zip_selected"]=True
    ss["zip_indexing"]=True
    ss["zip_done"]=False

def _after_download():
    # Marcar reset total; el cuerpo principal lo hará fuera del callback
    ss["post_download_reset"] = True

# ------------------ UI: ZIP ------------------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="hdr">1) Carga masiva (ZIP con miles de XML)</div>', unsafe_allow_html=True)

# Key dinámico para vaciar el uploader tras reset:
zip_uploader_key = f"zip_bulk_uploader_{ss['uploader_nonce']}"

st.file_uploader(
    "Sube tu .zip (se indexa automáticamente)",
    type=["zip"], accept_multiple_files=False, key=zip_uploader_key,
    on_change=_on_zip_selected, label_visibility="collapsed"
)

# Ejecutar indexación silenciosa
if ss.get("zip_indexing") and ss.get("zip_selected") and ("zip_bytes" in ss):
    ph = st.progress(0.0)
    try:
        total, nuevos, secs = bulk_index_zip(ss["zip_bytes"], XML_DB_PATH, prog=ph, batch=1000)
        ss["zip_done"]=True
        ss["zip_indexing"]=False
        ss["parsed_df"] = index_as_df(XML_DB_PATH, limit=None)
        ss["archivos_xml_nombres"] = ss["parsed_df"]["Archivo XML"].tolist()
    except Exception:
        ss["zip_done"]=False
        ss["zip_indexing"]=False
st.markdown('</div>', unsafe_allow_html=True)

# --- Métricas del índice (solo visibles SI hay ZIP cargado e indexado) ---
show_metrics = bool(ss.get("zip_done")) and not ss.get("parsed_df", pd.DataFrame()).empty
if show_metrics:
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        st.metric("XML indexados", f"{index_doc_count(XML_DB_PATH):,}")
    with mcol2:
        st.metric("RFC únicos en índice", f"{index_rfc_count(XML_DB_PATH):,}")

# ------------------ Archivos SAT ------------------
tengo_xml = not ss.get("parsed_df", pd.DataFrame()).empty
firmes_df = ss.get("firmes_df")
exigibles_df = ss.get("exigibles_df")
black = ss.get("blacklist_df", pd.DataFrame())
tengo_firmes = _has_rfc_column(firmes_df)
tengo_exigibles = _has_rfc_column(exigibles_df)
tengo_blacklist = _has_rfc_column(black)

warning_message = None
redirect_target = None
redirect_label = None

if not tengo_firmes and not tengo_exigibles:
    warning_message = "No existen los archivos Firmes ni Exigibles. Cárgalos antes de continuar."
    redirect_target = "pages/17_Archivo_firmes.py"
    redirect_label = "Ir a Archivo Firmes"
elif not tengo_firmes:
    warning_message = "No existe el archivo Firmes. Cárgalo para habilitar el cruce."
    redirect_target = "pages/17_Archivo_firmes.py"
    redirect_label = "Ir a Archivo Firmes"
elif not tengo_exigibles:
    warning_message = "No existe el archivo Exigibles. Cárgalo para habilitar el cruce."
    redirect_target = "pages/21_Archivo_exigibles.py"
    redirect_label = "Ir a Archivo Exigibles"

if warning_message:
    st.warning(warning_message)
    if st.button(redirect_label, use_container_width=True, key="go_missing_sat_file"):
        try:
            st.switch_page(redirect_target)
        except Exception:
            st.stop()

# ------------------ Descarga (único botón) + reset total tras clic ------------------
if tengo_xml and tengo_blacklist:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="hdr">3) Cruce y descarga</div>', unsafe_allow_html=True)
    try:
        xls = build_excel_bytes(ss["parsed_df"], black)
        st.markdown('<div class="descargar-excel-box">', unsafe_allow_html=True)
        st.download_button(
            "Descargar coincidencias (Excel)",
            data=xls,
            file_name="Cruce_RFC_vs_Lista_Negra_SAT.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_xlsx",
            on_click=_after_download,   # tras descargar, reset total + uploader vacío
        )
        st.markdown('</div>', unsafe_allow_html=True)
    except Exception:
        pass
    st.markdown('</div>', unsafe_allow_html=True)
