# 15_Lista_negra_Sat.py — Alternativa 1 (recomendada): Carga masiva ZIP + indexado SQLite
from __future__ import annotations

import io
import json
import time
import hashlib
import zipfile
import sqlite3
from contextlib import closing
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

# Dependencias internas del proyecto
from core.auth import persist_login
from core.db import portal_set_password
from core.streamlit_compat import rerun
from pages.components.admin import init_admin_section


# =============================================================================
# Forzar cambio de contraseña si aplica
# =============================================================================
def _enforce_password_change(conn) -> None:
    if not st.session_state.get("must_change_password"):
        return

    st.warning("Debes actualizar tu contrasena antes de continuar.")
    with st.form("monitoreo_force_password_change", clear_on_submit=False):
        new_password = st.text_input("Nueva contrasena", type="password")
        confirm_password = st.text_input("Confirmar contrasena", type="password")
        submitted = st.form_submit_button("Actualizar contrasena", use_container_width=True)

    if not submitted:
        st.stop()

    new_password = (new_password or "").strip()
    confirm_password = (confirm_password or "").strip()
    if len(new_password) < 8:
        st.error("La contrasena debe tener al menos 8 caracteres.")
        st.stop()
    if new_password != confirm_password:
        st.error("Las contrasenas no coinciden.")
        st.stop()

    try:
        portal_set_password(
            conn,
            st.session_state.get("usuario", "") or "",
            new_password,
            require_change=False,
        )
        permisos_actuales = st.session_state.get("permisos") or []
        persist_login(
            st.session_state.get("usuario", ""),
            permisos_actuales,
            must_change_password=False,
            user_id=st.session_state.get("portal_user_id"),
        )
        st.success("Contrasena actualizada correctamente.")
        rerun()
    except Exception as exc:
        st.error(f"No fue posible actualizar la contrasena: {exc}")
        st.stop()


# =============================================================================
# Rutas / archivos persistentes
# =============================================================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

FIRMES_DIR = DATA_DIR / "firmes"
FIRMES_DIR.mkdir(parents=True, exist_ok=True)

MANIFEST_PATH = FIRMES_DIR / "manifest.json"

XML_DB_PATH = DATA_DIR / "xml_index.db"  # índice persistente de XML


# =============================================================================
# Inicialización de UI/base
# =============================================================================
conn = init_admin_section(
    page_title="Monitoreo EFOS - Cruce de RFC",
    active_top="monitoreo",
    layout="wide",
    show_inicio=False,
)
_enforce_password_change(conn)


# =============================================================================
# CSS
# =============================================================================
st.markdown(
    """
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 980px; }
    h1.titulo-sat { text-align: center; font-family: Arial, sans-serif; font-size: 2rem; font-weight: 700; line-height: 1.2; margin-bottom: 1.5rem; }
    .card-box { border: 1px solid #e5e7eb; background-color: #fafafa; border-radius: 10px; padding: 1rem 1rem; margin-bottom: 1rem; }
    .accion-titulo { font-family: Arial, sans-serif; font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem; }
    .info-texto, .error-texto { font-family: Arial, sans-serif; font-size: 0.95rem; font-weight: 500; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.75rem; }
    .info-texto { background-color: #eef2ff; color: #111827; border: 1px solid #c7d2fe; }
    .error-texto { background-color: #fee2e2; color: #7f1d1d; border: 1px solid #ef4444; }
    .lista-archivos-box { font-family: Arial, sans-serif; font-size: 0.9rem; background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; padding: 0.75rem 1rem; max-height: 220px; overflow-y: auto; margin-bottom: 0.5rem; }
    .descargar-excel-box { width: 100%; max-width: 360px; margin: 0.5rem 0 0.25rem 0; }
    .descargar-excel-box div.stDownloadButton > button { width: 100%; height: 56px; font-size: 1rem; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Helpers XML / Firmes
# =============================================================================
def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_emisor_from_xml(xml_bytes: bytes) -> tuple[str | None, str | None]:
    """(Uso puntual). Para el modo masivo usamos la versión streaming."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None, None
    for node in root.iter():
        if _local_tag(node.tag).lower() == "emisor":
            rfc = node.attrib.get("Rfc") or node.attrib.get("RFC") or node.attrib.get("rfc")
            nombre = node.attrib.get("Nombre") or node.attrib.get("NOMBRE") or node.attrib.get("nombre")
            return rfc, nombre
    return None, None


def parse_emisor_from_xml_stream(fp) -> tuple[str | None, str | None]:
    """Versión streaming: encuentra <cfdi:Emisor> y termina (memoria mínima)."""
    try:
        it = ET.iterparse(fp, events=("start",))
        for _event, elem in it:
            if _local_tag(elem.tag).lower() == "emisor":
                rfc = elem.attrib.get("Rfc") or elem.attrib.get("RFC") or elem.attrib.get("rfc")
                nombre = elem.attrib.get("Nombre") or elem.attrib.get("NOMBRE") or elem.attrib.get("nombre")
                return rfc, nombre
        return None, None
    except ET.ParseError:
        return None, None


def load_blacklist_file(handle) -> pd.DataFrame:
    """Lee Firmes (CSV/XLSX) y normaliza columna RFC."""
    name_lower = getattr(handle, "name", "firmes_subido").lower()
    if name_lower.endswith(".csv"):
        df = pd.read_csv(handle, encoding="latin-1")
    elif name_lower.endswith(".xlsx") or name_lower.endswith(".xls"):
        df = pd.read_excel(handle)
    else:
        # intento CSV por defecto
        try:
            df = pd.read_csv(handle, encoding="latin-1")
        except Exception:
            df = pd.DataFrame()

    if "RFC" in df.columns:
        df["RFC"] = df["RFC"].astype(str).str.strip()
    return df


def build_coincidencias_excel_bytes(df_xml: pd.DataFrame, df_blacklist: pd.DataFrame) -> bytes:
    """Cruza RFCs y devuelve bytes XLSX listo para descargar."""
    rfcs_xml_unicos = df_xml["RFC Emisor"].astype(str).str.strip().unique().tolist()
    df_blacklist_norm = df_blacklist.copy()
    df_blacklist_norm["RFC"] = df_blacklist_norm["RFC"].astype(str).str.strip()
    coincidencias = df_blacklist_norm[df_blacklist_norm["RFC"].isin(rfcs_xml_unicos)].copy()
    final_df = coincidencias if not coincidencias.empty else pd.DataFrame(columns=df_blacklist_norm.columns)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        final_df.to_excel(writer, index=False, sheet_name="Coincidencias")
    return output.getvalue()


def read_manifest() -> dict | None:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def load_firmes_from_disk() -> pd.DataFrame:
    """Intenta cargar Firmes previamente guardado en disco, usando manifest."""
    manifest = read_manifest()
    if not manifest:
        return pd.DataFrame()
    stored_name = manifest.get("stored_as", "")
    if not stored_name:
        return pd.DataFrame()
    stored_path = FIRMES_DIR / stored_name
    if not stored_path.exists():
        return pd.DataFrame()

    try:
        with stored_path.open("rb") as handle:
            df = load_blacklist_file(handle)
    except Exception:
        return pd.DataFrame()

    if df.empty or "RFC" not in df.columns:
        return pd.DataFrame()
    return df


# =============================================================================
# SQLite: índice masivo de XML
# =============================================================================
def _db_init(db_path: Path):
    with closing(sqlite3.connect(str(db_path))) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS xml_emisores(
            filename TEXT NOT NULL,
            sha1 TEXT NOT NULL,
            rfc TEXT,
            nombre TEXT,
            PRIMARY KEY (sha1)
        )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_xml_emisores_rfc ON xml_emisores(rfc)")
        con.commit()


def _sha1_bytes(b: bytes) -> str:
    h = hashlib.sha1()
    h.update(b)
    return h.hexdigest()


def bulk_index_zip(zip_bytes: bytes, db_path: Path, progress_placeholder=None, batch_size: int = 1000) -> tuple[int, int, float]:
    """
    Indexa masivamente archivos XML de un ZIP:
      - SHA1 para deduplicar
      - Extrae RFC/Nombre de <cfdi:Emisor> en streaming
      - Inserta con INSERT OR IGNORE (evita reprocesar)
    Retorna: (procesados_total, insertados_nuevos, segundos)
    """
    _db_init(db_path)
    t0 = time.time()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf, closing(sqlite3.connect(str(db_path))) as con:
        cur = con.cursor()
        infos = [i for i in zf.infolist() if (not i.is_dir()) and i.filename.lower().endswith(".xml")]
        total = len(infos)
        inserted = 0
        processed = 0
        buf = []

        for idx, info in enumerate(infos, start=1):
            with zf.open(info, "r") as fp:
                raw = fp.read()
            sha1 = _sha1_bytes(raw)
            # parseo en streaming
            rfc, nombre = parse_emisor_from_xml_stream(io.BytesIO(raw))

            buf.append((info.filename, sha1, (rfc or "").strip(), (nombre or "").strip()))

            if len(buf) >= batch_size:
                cur.executemany(
                    "INSERT OR IGNORE INTO xml_emisores(filename, sha1, rfc, nombre) VALUES (?, ?, ?, ?)",
                    buf
                )
                con.commit()
                inserted += cur.rowcount if cur.rowcount is not None else 0
                processed += len(buf)
                buf.clear()

                if progress_placeholder:
                    progress_placeholder.progress(min(processed / max(total, 1), 1.0), text="Indexando ZIP…")

        # Resto
        if buf:
            cur.executemany(
                "INSERT OR IGNORE INTO xml_emisores(filename, sha1, rfc, nombre) VALUES (?, ?, ?, ?)",
                buf
            )
            con.commit()
            inserted += cur.rowcount if cur.rowcount is not None else 0
            processed += len(buf)
            buf.clear()

        if progress_placeholder:
            progress_placeholder.progress(1.0, text="Indexación finalizada")

    dt = time.time() - t0
    return processed, inserted, dt


def read_index_as_dataframe(db_path: Path, limit: int | None = None) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame(columns=["Archivo XML", "RFC Emisor", "Nombre Emisor"])
    with closing(sqlite3.connect(str(db_path))) as con:
        q = "SELECT filename, rfc, nombre FROM xml_emisores"
        if limit:
            q += f" LIMIT {int(limit)}"
        df = pd.read_sql_query(q, con)
    return df.rename(columns={"filename": "Archivo XML", "rfc": "RFC Emisor", "nombre": "Nombre Emisor"})


def get_unique_rfcs(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame(columns=["RFC Emisor"])
    with closing(sqlite3.connect(str(db_path))) as con:
        df = pd.read_sql_query(
            "SELECT DISTINCT rfc AS 'RFC Emisor' FROM xml_emisores WHERE rfc IS NOT NULL AND rfc <> ''",
            con,
        )
    return df


# =============================================================================
# Estado de sesión inicial
# =============================================================================
if "parsed_df" not in st.session_state:
    st.session_state.parsed_df = pd.DataFrame(columns=["Archivo XML", "RFC Emisor", "Nombre Emisor"])

if "archivos_xml_nombres" not in st.session_state:
    st.session_state.archivos_xml_nombres = []

if "blacklist_df" not in st.session_state:
    disk_df = load_firmes_from_disk()
    st.session_state.blacklist_df = disk_df if not disk_df.empty else pd.DataFrame()

if "status_msg" not in st.session_state:
    st.session_state.status_msg = ""
    st.session_state.status_is_error = False

if "mostrar_lista_xml" not in st.session_state:
    st.session_state.mostrar_lista_xml = False


# =============================================================================
# Encabezado
# =============================================================================
st.markdown('<h1 class="titulo-sat">Cruce de RFC con Lista Negra del SAT</h1>', unsafe_allow_html=True)

# Bandeas de estado
tengo_firmes = (not st.session_state.blacklist_df.empty) and ("RFC" in st.session_state.blacklist_df.columns)


# =============================================================================
# ALTERNATIVA 1 — Carga masiva por ZIP + índice SQLite (recomendada para 10k+ XML)
# =============================================================================
st.markdown('<div class="card-box">', unsafe_allow_html=True)
st.markdown('<div class="accion-titulo">Carga masiva (ZIP con miles de XML)</div>', unsafe_allow_html=True)

col_zip, col_btns = st.columns([2, 1], vertical_alignment="center")

with col_zip:
    zip_file = st.file_uploader(
        "Sube un .zip con tus XML (ideal para 10,000+ archivos)",
        type=["zip"],
        accept_multiple_files=False,
        key="zip_bulk_uploader",
    )

with col_btns:
    do_index = st.button("Indexar ZIP", type="primary", use_container_width=True, key="zip_index_btn")
    reset_idx = st.button("Reiniciar índice", use_container_width=True, key="zip_reset_btn")

# Reiniciar índice (opcional)
if reset_idx:
    try:
        if XML_DB_PATH.exists():
            XML_DB_PATH.unlink()
        st.success("Índice eliminado. Puedes volver a indexar un ZIP.")
    except Exception as e:
        st.error(f"No se pudo eliminar el índice: {e}")

# Indexar ZIP
if do_index:
    if not zip_file:
        st.error("Primero selecciona un archivo .zip.")
    else:
        ph = st.progress(0.0, text="Preparando…")
        data = zip_file.read()
        total, nuevos, secs = bulk_index_zip(data, XML_DB_PATH, progress_placeholder=ph, batch_size=1000)
        st.info(f"Procesados: {total:,} | Nuevos en índice: {nuevos:,} | Tiempo: {secs:,.1f} s")

# Resumen del índice y “usar índice” como XML cargados
if XML_DB_PATH.exists():
    colL, colR = st.columns([3, 2])
    with colL:
        df_preview = read_index_as_dataframe(XML_DB_PATH, limit=300)
        st.dataframe(df_preview, use_container_width=True, height=280)

    with colR:
        rfcs_idx = get_unique_rfcs(XML_DB_PATH)
        st.metric("RFC únicos en índice", f"{len(rfcs_idx):,}")
        if st.button("Usar índice como XML cargados", key="use_index_btn", use_container_width=True):
            # Integra con el flujo existente (sin volver a leer el ZIP):
            st.session_state.parsed_df = read_index_as_dataframe(XML_DB_PATH, limit=None)
            st.session_state.archivos_xml_nombres = st.session_state.parsed_df["Archivo XML"].tolist()
            st.session_state.status_msg = f"Se tomaron {len(st.session_state.parsed_df):,} XML desde el índice."
            st.session_state.status_is_error = False
            st.rerun()

st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# Firmes: si no hay, instrucción para cargar desde menú superior (tu flujo actual)
# =============================================================================
tengo_xml = not st.session_state.parsed_df.empty

if tengo_xml and not tengo_firmes:
    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    st.markdown('<div class="accion-titulo">Cargar archivo Firmes (SAT)</div>', unsafe_allow_html=True)
    st.write(
        "Actualiza el archivo Firmes desde la opción **Archivo Firmes** en la barra superior. "
        "Cuando termines, presiona **Reintentar** para recargar."
    )
    if st.button("Reintentar", key="firmes_reload_btn"):
        rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# Panel informativo de estado + listado (opcional) de XML
# =============================================================================
if st.session_state.status_msg:
    css_class = "error-texto" if st.session_state.status_is_error else "info-texto"
    st.markdown(f'<div class="{css_class}">{st.session_state.status_msg}</div>', unsafe_allow_html=True)

if tengo_xml:
    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    cols = st.columns([1, 3])
    with cols[0]:
        if st.button("Mostrar / ocultar archivos cargados", key="toggle_xml_btn"):
            st.session_state.mostrar_lista_xml = not st.session_state.mostrar_lista_xml
    with cols[1]:
        st.caption("Puedes trabajar con el índice sin cargar todos los nombres si sólo cruzarás RFC.")

    if st.session_state.mostrar_lista_xml:
        if st.session_state.archivos_xml_nombres:
            listado = "<br>".join(f"- {n}" for n in st.session_state.archivos_xml_nombres[:1000])
            extra = ""
            if len(st.session_state.archivos_xml_nombres) > 1000:
                extra = f"<br>… y {len(st.session_state.archivos_xml_nombres) - 1000:,} más"
            st.markdown(f'<div class="lista-archivos-box">{listado}{extra}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="lista-archivos-box">No hay listado de archivos materializado.</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# Generar y descargar Excel (cuando hay XML + Firmes válidos)
# =============================================================================
tengo_todo = tengo_xml and tengo_firmes
if tengo_todo:
    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    st.markdown('<div class="accion-titulo">Cruce y descarga</div>', unsafe_allow_html=True)

    # Cruce directo sobre DataFrame 'parsed_df' (que puede venir del índice)
    try:
        excel_bytes_ready = build_coincidencias_excel_bytes(
            st.session_state.parsed_df, st.session_state.blacklist_df
        )
        st.markdown('<div class="descargar-excel-box">', unsafe_allow_html=True)
        st.download_button(
            label="Generar y descargar Excel",
            data=excel_bytes_ready,
            file_name="Cruce_RFC_vs_Lista_Negra_SAT.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_excel_btn_final",
        )
        st.markdown("</div>", unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"No fue posible generar el Excel: {exc}")

    st.markdown("</div>", unsafe_allow_html=True)
