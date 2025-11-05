# pages/15_Lista_negra_Sat.py
from __future__ import annotations

import os, io, json, time, hashlib, zipfile, sqlite3, shutil, threading, tempfile
from contextlib import closing
from pathlib import Path
from typing import BinaryIO, Iterable, Dict, Any, Optional
from uuid import uuid4
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# Config básica de la página
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Lista Negra SAT — Carga masiva",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# Barra de menú fija superior (usa tu render_nav si existe; si no, fallback)
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Rutas de trabajo (Railway-ready: usa Volume si existe APP_DATA_DIR)
# -----------------------------------------------------------------------------
ROOT_FROM_ENV = os.getenv("APP_DATA_DIR")  # ej: /data/ais_lista_negra_sat
BASE_ROOT = Path(ROOT_FROM_ENV) if ROOT_FROM_ENV else Path(tempfile.gettempdir()) / "ais_lista_negra_sat"

DATA_DIR = BASE_ROOT
FIRMES_DIR = DATA_DIR / "firmes"
EXIGIBLES_DIR = DATA_DIR / "exigibles"
ZIP_UPLOAD_DIR = DATA_DIR / "zip_uploads"
EXPORT_DIR = DATA_DIR / "exports"
JOBS_DIR = DATA_DIR / "jobs"

for d in (DATA_DIR, FIRMES_DIR, EXIGIBLES_DIR, ZIP_UPLOAD_DIR, EXPORT_DIR, JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

XML_DB_PATH = DATA_DIR / "xml_index.db"
FIRMES_MANIFEST_PATH = FIRMES_DIR / "manifest.json"
EXIGIBLES_MANIFEST_PATH = EXIGIBLES_DIR / "manifest.json"

# Parametrización
MAX_MB = 600           # ligado a --server.maxUploadSize del deploy
DEFAULT_BATCH = 150    # tamaño de lote (baja picos de RAM/CPU)
POLL_INTERVAL = 0.7    # segundos para polling UI
HEARTBEAT_MAX_AGE = 10 # s sin latido => relanzar worker

# -----------------------------------------------------------------------------
# Estilos locales
# -----------------------------------------------------------------------------
st.markdown("""
<style>
h1.titulo{font:700 1.9rem/1.2 ui-sans-serif;text-align:center;margin:.5rem 0 .75rem}
.card{border:1px solid #e5e7eb;background:#fafafa;border-radius:12px;padding:1rem;margin:.75rem 0}
.hdr{font:700 1rem ui-sans-serif;margin-bottom:.5rem}
.descargar-excel-box div.stDownloadButton>button{width:100%;height:56px;font-size:1rem;font-weight:700}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="titulo">Cruce de RFC con Lista Negra del SAT</h1>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Utilidades XML / normalización
# -----------------------------------------------------------------------------
def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag

def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        v = str(value).strip()
        if not v:
            return None
        return float(v.replace(",", ""))
    except Exception:
        return None

def _normalize_status(value: str | None) -> str:
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

def parse_emisor_from_xml_stream(fp) -> tuple[str | None, str | None, str | None, float | None, str]:
    """Extrae Emisor RFC/Nombre, Fecha, Total y Estatus sin cargar todo el XML en memoria."""
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

# -----------------------------------------------------------------------------
# Excel builder (Coincidencias / Desglose) — formato funcional original
# -----------------------------------------------------------------------------
def _chunked(iterable, size: int = 500):
    bucket: list[str] = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket

def _load_xml_matches_from_db(db_path: Path, rfcs: list[str]) -> pd.DataFrame:
    columns = [
        "Archivo XML", "RFC Emisor", "Nombre Emisor",
        "Fecha Timbrado", "Total", "Estatus",
    ]
    rfcs = [r.strip() for r in rfcs if isinstance(r, str) and r.strip()]
    if not rfcs:
        return pd.DataFrame(columns=columns)

    frames: list[pd.DataFrame] = []
    with closing(sqlite3.connect(str(db_path))) as con:
        for batch in _chunked(rfcs, 800):
            placeholders = ",".join("?" for _ in batch)
            query = (
                "SELECT filename AS 'Archivo XML', rfc AS 'RFC Emisor', nombre AS 'Nombre Emisor', "
                "fecha AS 'Fecha Timbrado', total AS 'Total', estatus AS 'Estatus' "
                f"FROM xml_emisores WHERE rfc IN ({placeholders})"
            )
            frames.append(pd.read_sql_query(query, con, params=batch))
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)

def build_excel_bytes(xml_source: pd.DataFrame | Path | str, df_black: pd.DataFrame) -> bytes:
    # Hojas: Coincidencias / Desglose
    resumen_columns = ["RFC", "PROVEEDOR", "FECHA (FIRMES)", "IMPORTE"]
    desglose_columns = ["Situacion", "Fecha Timbrado", "RFC Emisor", "Razon Social Emisor", "Total", "Estatus"]

    blk = df_black.copy()
    if not blk.empty and "RFC" in blk.columns:
        blk["RFC"] = blk["RFC"].astype(str).str.strip()
    else:
        blk = pd.DataFrame(columns=["RFC"])

    if isinstance(xml_source, (str, Path)):
        xml_df = _load_xml_matches_from_db(Path(xml_source), blk["RFC"].dropna().unique().tolist())
    else:
        xml_df = xml_source.copy()

    if xml_df.empty or blk.empty:
        out_empty = io.BytesIO()
        with pd.ExcelWriter(out_empty, engine="xlsxwriter") as w:
            pd.DataFrame(columns=resumen_columns).to_excel(w, index=False, sheet_name="Coincidencias")
            pd.DataFrame(columns=desglose_columns).to_excel(w, index=False, sheet_name="Desglose")
        return out_empty.getvalue()

    xml_df["RFC Emisor"] = xml_df["RFC Emisor"].astype(str).str.strip()
    xml_df["Total"] = pd.to_numeric(xml_df.get("Total"), errors="coerce").fillna(0.0)
    rfcs_xml = xml_df["RFC Emisor"].dropna().unique().tolist()

    coincidencias = blk[blk["RFC"].isin(rfcs_xml)].copy()
    resumen_df = pd.DataFrame(columns=resumen_columns)
    situacion_map: dict[str, str] = {}
    rfcs_coincidentes: list[str] = []
    if not coincidencias.empty:
        rfcs_coincidentes = coincidencias["RFC"].dropna().astype(str).str.strip().unique().tolist()
        if "SUPUESTO" in coincidencias.columns:
            situacion_map = (
                coincidencias.groupby("RFC")["SUPUESTO"].first()
                .astype(str).str.strip().str.upper().to_dict()
            )

        coincidencias_ordenadas = coincidencias.copy()
        if "FECHA DE PRIMERA PUBLICACION" in coincidencias_ordenadas.columns:
            coincidencias_ordenadas = coincidencias_ordenadas.sort_values(
                "FECHA DE PRIMERA PUBLICACION", ascending=False
            )
        resumen_df = coincidencias_ordenadas.groupby("RFC", as_index=False).first()
        resumen_df = resumen_df.drop(columns=["TIPO PERSONA", "ENTIDAD FEDERATIVA", "SUPUESTO"], errors="ignore")
        resumen_df = resumen_df.rename(
            columns={"RAZON SOCIAL": "PROVEEDOR", "FECHA DE PRIMERA PUBLICACION": "FECHA (FIRMES)"}
        )
        if "FECHA (FIRMES)" in resumen_df.columns:
            resumen_df["FECHA (FIRMES)"] = pd.to_datetime(resumen_df["FECHA (FIRMES)"], errors="coerce").dt.date
        resumen_df["IMPORTE"] = resumen_df["RFC"].map(
            xml_df[xml_df["RFC Emisor"].isin(rfcs_coincidentes)].groupby("RFC Emisor")["Total"].sum()
        ).fillna(0.0)

        desired_cols = [c for c in ["RFC", "PROVEEDOR", "FECHA (FIRMES)", "IMPORTE"] if c in resumen_df.columns]
        resumen_df = resumen_df[desired_cols] if desired_cols else resumen_df
        if "RFC" in resumen_df.columns:
            resumen_df.sort_values("RFC", inplace=True)

    desglose_df = (xml_df[xml_df["RFC Emisor"].isin(rfcs_coincidentes)].copy()
                   if rfcs_coincidentes else xml_df.iloc[0:0].copy())
    if situacion_map:
        desglose_df["Situacion"] = desglose_df["RFC Emisor"].map(situacion_map).fillna("DESCONOCIDO")
    else:
        desglose_df["Situacion"] = "DESCONOCIDO"
    desglose_df = desglose_df.rename(columns={"Nombre Emisor": "Razon Social Emisor"})
    if "Fecha Timbrado" in desglose_df.columns:
        desglose_df["Fecha Timbrado"] = pd.to_datetime(desglose_df["Fecha Timbrado"], errors="coerce").dt.date
    desglose_df["Total"] = pd.to_numeric(desglose_df.get("Total"), errors="coerce").fillna(0.0)

    for col, default in [("Fecha Timbrado", pd.NaT), ("Razon Social Emisor", ""), ("Estatus", "Activo")]:
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

# -----------------------------------------------------------------------------
# Firmes/Exigibles — Autodetección + manifest (PARCHE solicitado)
# -----------------------------------------------------------------------------
def _read_manifest(manifest_path: Path) -> dict | None:
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def _write_manifest(manifest_path: Path, stored_as: str) -> None:
    try:
        manifest_path.write_text(json.dumps({"stored_as": stored_as}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _looks_like_sat_file(path: Path) -> bool:
    """Heurística: debe tener columna RFC (lee primeras filas)."""
    try:
        n = path.name.lower()
        if n.endswith(".csv"):
            df = pd.read_csv(path, nrows=50, encoding="latin-1")
        elif n.endswith((".xlsx", ".xls")):
            df = pd.read_excel(path, nrows=50)
        else:
            return False
        return isinstance(df, pd.DataFrame) and ("RFC" in df.columns)
    except Exception:
        return False

def _find_best_sat_file(base_dir: Path, manifest_path: Path) -> Path | None:
    # 1) if manifest válido → úsalo
    m = _read_manifest(manifest_path)
    if m and m.get("stored_as"):
        cand = base_dir / m["stored_as"]
        if cand.exists() and _looks_like_sat_file(cand):
            return cand
    # 2) buscar candidatos por nombre/fecha
    files = list(base_dir.glob("*.csv")) + list(base_dir.glob("*.xlsx")) + list(base_dir.glob("*.xls"))
    if not files:
        return None

    def score(p: Path) -> tuple[int, float]:
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
    elif n.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        return pd.DataFrame()
    if df.empty or "RFC" not in df.columns:
        return pd.DataFrame()
    df["RFC"] = df["RFC"].astype(str).str.strip()
    return df

def _load_sat_reference(manifest_path: Path, base_dir: Path) -> pd.DataFrame:
    best = _find_best_sat_file(base_dir, manifest_path)
    if not best:
        return pd.DataFrame()
    try:
        return _load_sat_reference_from_path(best)
    except Exception:
        return pd.DataFrame()

def load_firmes_from_disk() -> pd.DataFrame:
    return _load_sat_reference(FIRMES_MANIFEST_PATH, FIRMES_DIR)

def load_exigibles_from_disk() -> pd.DataFrame:
    return _load_sat_reference(EXIGIBLES_MANIFEST_PATH, EXIGIBLES_DIR)

def _has_rfc_column(df: pd.DataFrame | None) -> bool:
    return isinstance(df, pd.DataFrame) and (not df.empty) and ("RFC" in df.columns)

def _combine_blacklists(*dfs: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for df in dfs:
        if _has_rfc_column(df):
            frame = df.copy()
            frame["RFC"] = frame["RFC"].astype(str).str.strip()
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

# -----------------------------------------------------------------------------
# SQLite / Indexación de XML (streaming, INSERT OR IGNORE)
# -----------------------------------------------------------------------------
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
        # Migraciones defensivas
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

def _sha1(b: bytes) -> str:
    h = hashlib.sha1(); h.update(b); return h.hexdigest()

def bulk_index_zip(zip_source: bytes | str | Path | BinaryIO, db_path: Path, *, progress_cb=None, batch: int = 200) -> tuple[int, int, float]:
    _db_init(db_path)
    t0 = time.time()
    stream: BinaryIO
    close_stream = False
    if isinstance(zip_source, (str, Path)):
        stream = open(zip_source, "rb"); close_stream = True
    elif isinstance(zip_source, bytes):
        stream = io.BytesIO(zip_source)
    else:
        stream = zip_source

    processed = 0
    inserted = 0
    total_files = 0

    try:
        try: stream.seek(0)
        except Exception: pass

        with zipfile.ZipFile(stream) as zf, closing(sqlite3.connect(str(db_path))) as con:
            cur = con.cursor()
            files = [i for i in zf.infolist() if (not i.is_dir()) and i.filename.lower().endswith(".xml")]
            total_files = len(files)
            buf: list[tuple[str, str, str, str, str | None, float | None, str]] = []

            for info in files:
                with zf.open(info, "r") as fp:
                    raw = fp.read()
                sha = _sha1(raw)
                rfc, nom, fecha, total_xml, estatus = parse_emisor_from_xml_stream(io.BytesIO(raw))
                buf.append((info.filename, sha, (rfc or "").strip(), (nom or "").strip(), fecha, total_xml, estatus))

                if len(buf) >= batch:
                    cur.executemany(
                        "INSERT OR IGNORE INTO xml_emisores(filename,sha1,rfc,nombre,fecha,total,estatus) "
                        "VALUES(?,?,?,?,?,?,?)",
                        buf,
                    )
                    con.commit()
                    inserted += cur.rowcount or 0
                    processed += len(buf)
                    buf.clear()
                    if progress_cb:
                        progress_cb(processed, total_files, inserted)

            if buf:
                cur.executemany(
                    "INSERT OR IGNORE INTO xml_emisores(filename,sha1,rfc,nombre,fecha,total,estatus) "
                    "VALUES(?,?,?,?,?,?,?)",
                    buf,
                )
                con.commit()
                inserted += cur.rowcount or 0
                processed += len(buf)
                buf.clear()
                if progress_cb:
                    progress_cb(processed, total_files, inserted)
    finally:
        if close_stream:
            try: stream.close()
            except Exception: pass

    duration = time.time() - t0
    if progress_cb:
        progress_cb(processed, total_files or processed, inserted)
    return processed, inserted, duration

def index_doc_count(db_path: Path) -> int:
    if not db_path.exists(): return 0
    with closing(sqlite3.connect(str(db_path))) as con:
        n = con.execute("SELECT COUNT(*) FROM xml_emisores").fetchone()[0]
    return int(n or 0)

def index_rfc_count(db_path: Path) -> int:
    if not db_path.exists(): return 0
    with closing(sqlite3.connect(str(db_path))) as con:
        n = con.execute("SELECT COUNT(DISTINCT rfc) FROM xml_emisores WHERE rfc IS NOT NULL AND rfc<>''").fetchone()[0]
    return int(n or 0)

def index_as_df(db_path: Path, limit: int | None = None) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame(columns=["Archivo XML", "RFC Emisor", "Nombre Emisor"])
    with closing(sqlite3.connect(str(db_path))) as con:
        q = "SELECT filename, rfc, nombre, fecha, total, estatus FROM xml_emisores"
        if limit: q += f" LIMIT {int(limit)}"
        df = pd.read_sql_query(q, con)
    return df.rename(columns={
        "filename": "Archivo XML",
        "rfc": "RFC Emisor",
        "nombre": "Nombre Emisor",
        "fecha": "Fecha Timbrado",
        "total": "Total",
        "estatus": "Estatus",
    })

# -----------------------------------------------------------------------------
# Jobs en memoria + Heartbeat + Supervisor (AUTO-REINTENTO)
# -----------------------------------------------------------------------------
_ZIP_JOBS: Dict[str, Dict[str, Any]] = {}
_ZIP_JOBS_LOCK = threading.Lock()

class _ZipJobCancelled(RuntimeError):
    pass

def _zip_job_update(job_id: str, **payload: Any) -> None:
    payload.setdefault("heartbeat", int(time.time()))
    with _ZIP_JOBS_LOCK:
        rec = _ZIP_JOBS.get(job_id)
        if rec:
            rec.update(payload)

def _zip_job_get(job_id: str | None) -> Dict[str, Any] | None:
    if not job_id: return None
    with _ZIP_JOBS_LOCK:
        rec = _ZIP_JOBS.get(job_id)
        return dict(rec) if rec else None

def _zip_job_flag_cancel(job_id: str | None) -> None:
    if not job_id: return
    _zip_job_update(job_id, cancel_requested=True)

def _zip_job_should_cancel(job_id: str) -> bool:
    with _ZIP_JOBS_LOCK:
        rec = _ZIP_JOBS.get(job_id)
        return bool(rec and rec.get("cancel_requested"))

def _zip_job_clear(job_id: str | None) -> None:
    if not job_id: return
    with _ZIP_JOBS_LOCK:
        _ZIP_JOBS.pop(job_id, None)

def _zip_job_start(zip_path: Path, *, batch: int = 1000, reuse_id: str | None = None) -> str:
    job_id = reuse_id or f"{int(time.time()*1000)}_{uuid4().hex}"
    record: Dict[str, Any] = {
        "status": "queued", "progress": 0.0, "processed": 0, "inserted": 0,
        "total": 0, "error": None, "zip_path": str(zip_path),
        "started": time.time(), "finished": None, "cancel_requested": False,
        "batch": batch, "heartbeat": int(time.time()),
    }
    with _ZIP_JOBS_LOCK:
        _ZIP_JOBS[job_id] = record
    worker = threading.Thread(target=_zip_job_worker, args=(job_id, zip_path, batch), daemon=True)
    worker.start()
    return job_id

def _zip_job_restart(job_id: str) -> None:
    rec = _zip_job_get(job_id)
    if not rec: return
    zp = Path(rec.get("zip_path", ""))
    if not zp.exists(): return
    _zip_job_update(job_id, status="queued")
    worker = threading.Thread(target=_zip_job_worker, args=(job_id, zp, int(rec.get("batch") or DEFAULT_BATCH)), daemon=True)
    worker.start()

def _zip_supervise_and_autoretry(job_id: str) -> None:
    rec = _zip_job_get(job_id)
    if not rec: return
    if rec.get("status") not in {"queued", "running"}: return
    hb = int(rec.get("heartbeat") or 0)
    if hb and (int(time.time()) - hb) > HEARTBEAT_MAX_AGE:
        _zip_job_restart(job_id)

def _zip_job_worker(job_id: str, zip_path: Path, batch: int) -> None:
    def _progress(processed: int, total: int, inserted: int) -> None:
        progress = (processed / max(1, total)) if total else 0.0
        _zip_job_update(job_id, processed=processed, total=total, inserted=inserted, progress=progress)
        if _zip_job_should_cancel(job_id):
            raise _ZipJobCancelled()

    try:
        _zip_job_update(job_id, status="running")
        total, inserted, secs = bulk_index_zip(zip_path, XML_DB_PATH, progress_cb=_progress, batch=batch)
        _zip_job_update(job_id, status="done", processed=total, total=total, inserted=inserted,
                        progress=1.0, seconds=secs, finished=time.time())
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
    except _ZipJobCancelled:
        _zip_job_update(job_id, status="cancelled", finished=time.time())
    except Exception as exc:
        _zip_job_update(job_id, status="error", error=str(exc), finished=time.time())

# -----------------------------------------------------------------------------
# Estado inicial + helpers de UI
# -----------------------------------------------------------------------------
ss = st.session_state

def _clear_xml_index_file():
    try:
        if XML_DB_PATH.exists():
            XML_DB_PATH.unlink()
    except Exception:
        pass

def _reset_page_state(keep_reference_data: bool = True):
    job_id = ss.pop("zip_job_id", None)
    if job_id:
        _zip_job_flag_cancel(job_id)
    for key in ["zip_selected","zip_indexing","zip_done","post_download_reset",
                "zip_last_summary","zip_download_ready","zip_download_error","zip_download_path"]:
        ss.pop(key, None)
    if not keep_reference_data:
        ss["firmes_df"] = pd.DataFrame(); ss["exigibles_df"] = pd.DataFrame()
    ss["blacklist_df"] = _combine_blacklists(ss.get("firmes_df"), ss.get("exigibles_df"))
    ss["uploader_nonce"] = ss.get("uploader_nonce", 0) + 1

if "init_done" not in ss:
    ss["firmes_df"] = load_firmes_from_disk()
    ss["exigibles_df"] = load_exigibles_from_disk()
    ss["uploader_nonce"] = 0
    _clear_xml_index_file()
    _reset_page_state(keep_reference_data=True)
    ss["init_done"] = True

ss["blacklist_df"] = _combine_blacklists(ss.get("firmes_df"), ss.get("exigibles_df"))
if ss.get("post_download_reset"):
    _clear_xml_index_file()
    _reset_page_state(keep_reference_data=True)
    ss["post_download_reset"] = False
    st.rerun()

def _on_zip_selected():
    key = f"zip_bulk_uploader_{ss['uploader_nonce']}"
    up = ss.get(key)
    if not up:
        ss["zip_selected"] = False; ss["zip_indexing"] = False; ss["zip_done"] = False
        prev = ss.pop("zip_job_id", None)
        if prev: _zip_job_flag_cancel(prev)
        return

    prev = ss.pop("zip_job_id", None)
    if prev: _zip_job_flag_cancel(prev)

    for k in ["zip_last_summary","zip_download_path","zip_download_ready","zip_download_error"]:
        ss.pop(k, None)

    safe_name = Path(getattr(up, "name", "upload.zip") or "upload.zip").name
    dest = ZIP_UPLOAD_DIR / f"{int(time.time()*1000)}_{safe_name}"

    try:
        try: up.seek(0)
        except Exception: pass
        with dest.open("wb") as fh:
            shutil.copyfileobj(up, fh, length=1024*1024)  # 1MB chunks
        try: up.seek(0)
        except Exception: pass
    except Exception:
        try: dest.unlink()
        except Exception: pass
        ss["zip_selected"] = False; ss["zip_indexing"] = False; ss["zip_done"] = False
        st.error("No fue posible almacenar el ZIP seleccionado. Intenta de nuevo.")
        return

    job_id = _zip_job_start(dest, batch=DEFAULT_BATCH)
    ss["zip_job_id"] = job_id
    ss["zip_selected"] = True
    ss["zip_indexing"] = True
    ss["zip_done"] = False

def _after_download():
    ss["post_download_reset"] = True

# -----------------------------------------------------------------------------
# UI — Sección 1: Carga masiva ZIP
# -----------------------------------------------------------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="hdr">1) Carga masiva (ZIP con miles de XML)</div>', unsafe_allow_html=True)

zip_uploader_key = f"zip_bulk_uploader_{ss['uploader_nonce']}"
st.file_uploader(
    "Sube tu .zip (se indexa automáticamente)",
    type=["zip"], accept_multiple_files=False, key=zip_uploader_key,
    on_change=_on_zip_selected, label_visibility="collapsed"
)

job_id = ss.get("zip_job_id")
job_info = _zip_job_get(job_id)
if job_info:
    # Supervisor: auto-reintento si no hay heartbeat reciente
    _zip_supervise_and_autoretry(job_id)

    progress_value = float(job_info.get("progress") or 0.0)
    st.progress(progress_value)
    processed = int(job_info.get("processed") or 0)
    total = int(job_info.get("total") or 0)
    status = str(job_info.get("status") or "queued")
    inserted = int(job_info.get("inserted") or 0)

    if total:
        st.caption(f"Procesando XML {processed:,} de {total:,} (insertados {inserted:,})")
    else:
        st.caption(f"Procesando XML {processed:,} (insertados {inserted:,})")

    if status in {"queued", "running"}:
        ss["zip_indexing"] = True
        time.sleep(POLL_INTERVAL)
        st.rerun()
    elif status == "done":
        ss["zip_last_summary"] = {"procesados": processed, "insertados": inserted, "tiempo": float(job_info.get("seconds") or 0.0)}
        ss["zip_done"] = True
        ss["zip_indexing"] = False
        _zip_job_clear(job_id)
        ss.pop("zip_job_id", None)
    elif status == "cancelled":
        st.info("Procesamiento de ZIP cancelado.")
        ss["zip_indexing"] = False; ss["zip_done"] = False
        _zip_job_clear(job_id); ss.pop("zip_job_id", None)
    elif status == "error":
        detail = job_info.get("error") or "Error interno desconocido"
        st.error(f"No fue posible procesar el ZIP. Detalle: {detail}")
        ss["zip_indexing"] = False; ss["zip_done"] = False
        _zip_job_clear(job_id); ss.pop("zip_job_id", None)
else:
    ss.setdefault("zip_indexing", False)

st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Métricas del índice (solo si terminó ZIP)
# -----------------------------------------------------------------------------
summary = ss.get("zip_last_summary") or {}
doc_count = index_doc_count(XML_DB_PATH)
show_metrics = bool(ss.get("zip_done")) and bool(summary or doc_count)
if show_metrics:
    c1, c2 = st.columns(2)
    with c1: st.metric("XML indexados", f"{doc_count:,}")
    with c2: st.metric("RFC únicos en índice", f"{index_rfc_count(XML_DB_PATH):,}")
    if summary:
        st.caption(f"Última carga: {summary['procesados']:,} XML procesados, {summary['insertados']:,} nuevos, {summary['tiempo']:.1f}s.")

# -----------------------------------------------------------------------------
# Firmes/Exigibles — Carga automática + botón de re-scan
# -----------------------------------------------------------------------------
firmes_df = ss.get("firmes_df")
exigibles_df = ss.get("exigibles_df")
black = ss.get("blacklist_df", pd.DataFrame())

with st.expander("¿Problemas para detectar Firmes/Exigibles?"):
    if st.button("Re-escanear archivos SAT (Firmes/Exigibles)", use_container_width=True):
        ss["firmes_df"] = load_firmes_from_disk()
        ss["exigibles_df"] = load_exigibles_from_disk()
        ss["blacklist_df"] = _combine_blacklists(ss.get("firmes_df"), ss.get("exigibles_df"))
        st.success("Listas recargadas desde disco (se actualizaron manifests si fue necesario).")
        st.rerun()

tengo_firmes = _has_rfc_column(ss.get("firmes_df"))
tengo_exigibles = _has_rfc_column(ss.get("exigibles_df"))
black = _combine_blacklists(ss.get("firmes_df"), ss.get("exigibles_df"))
ss["blacklist_df"] = black
tengo_blacklist = _has_rfc_column(black)

warning_message = None; redirect_target = None; redirect_label = None
if not tengo_firmes and not tengo_exigibles:
    warning_message = "No existen los archivos **Firmes** ni **Exigibles** en disco. Colócalos en el volume."
elif not tengo_firmes:
    warning_message = "No existe el archivo **Firmes**. Colócalo en la carpeta /firmes del volume."
elif not tengo_exigibles:
    warning_message = "No existe el archivo **Exigibles**. Colócalo en la carpeta /exigibles del volume."
if warning_message:
    st.warning(warning_message)

# -----------------------------------------------------------------------------
# Sección 3: Cruce y descarga de Excel + reset total tras descargar
# -----------------------------------------------------------------------------
tengo_xml = bool(doc_count)
if tengo_xml and tengo_blacklist:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="hdr">3) Cruce y descarga</div>', unsafe_allow_html=True)

    col_gen, col_download = st.columns([0.55, 0.45])
    with col_gen:
        if st.button("Generar coincidencias (Excel)", use_container_width=True, key="generate_excel_btn"):
            existing_path = ss.pop("zip_download_path", None)
            if existing_path:
                try: Path(existing_path).unlink()
                except Exception: pass
            try:
                bytes_data = build_excel_bytes(XML_DB_PATH, black)
                export_name = f"Cruce_RFC_vs_Lista_Negra_SAT_{int(time.time()*1000)}.xlsx"
                export_path = EXPORT_DIR / export_name
                export_path.write_bytes(bytes_data)
                ss["zip_download_path"] = str(export_path)
                ss["zip_download_ready"] = True
                ss["zip_download_error"] = None
                st.success("Excel generado correctamente. Usa el botón de descarga.")
            except Exception as exc:
                ss["zip_download_ready"] = False
                ss["zip_download_error"] = str(exc)
                st.error("No fue posible generar el Excel. Revisa el log e inténtalo de nuevo.")

    download_error = ss.get("zip_download_error")
    if download_error and not ss.get("zip_download_ready"):
        st.error(f"Error al generar el archivo: {download_error}")

    download_path_value = ss.get("zip_download_path")
    download_ready = ss.get("zip_download_ready") and download_path_value
    with col_download:
        if download_ready:
            download_path = Path(download_path_value)
            if download_path.exists():
                try:
                    data_bytes = download_path.read_bytes()
                    st.download_button(
                        "⬇️ Descargar coincidencias (Excel)",
                        data=data_bytes,
                        file_name=download_path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_xlsx",
                        on_click=lambda: ss.update({"post_download_reset": True}),
                    )
                except Exception as exc:
                    st.error(f"No se pudo leer el archivo generado. Detalle: {exc}")
            else:
                st.warning("El archivo generado ya no está disponible. Genera uno nuevo.")
                ss["zip_download_ready"] = False
                ss.pop("zip_download_path", None)
        else:
            st.info("Genera el Excel para habilitar la descarga.")

    st.markdown("</div>", unsafe_allow_html=True)
