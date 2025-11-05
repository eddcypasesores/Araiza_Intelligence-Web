# pages/Riesgos_fiscales.py
from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path
from typing import List, Tuple, Iterable, Dict

import pandas as pd
import streamlit as st
from lxml import etree as ET


# -----------------------------------------------------------------------------
# Configuración base
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Riesgo Fiscal | Araiza Intelligence",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Integración opcional con tu sistema de auth/nav si existe
try:
    from core.auth import ensure_session_from_token  # type: ignore
    ensure_session_from_token()
except Exception:
    pass  # ejecuta sin auth si no está disponible en el entorno

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FIRMES_DIR = DATA_DIR / "firmes"
EXIGIBLES_DIR = DATA_DIR / "exigibles"
EXPORTS_DIR = DATA_DIR / "exports"
PAGES_DIR = ROOT / "pages"

# -----------------------------------------------------------------------------
# Estado (clave única para evitar "pegado" de uploaders tras rerun)
# -----------------------------------------------------------------------------
def _ensure_state():
    ss = st.session_state
    ss.setdefault("rf_uploader_key", "rf_zip_1")
    ss.setdefault("tc_uploader_key", "rf_tc_1")
    ss.setdefault("rf_loaded_zip_name", None)
    ss.setdefault("rf_xml_ok", [])          # List[Tuple[name, bytes]]
    ss.setdefault("rf_xml_issues", [])      # List[str]
    ss.setdefault("rf_df_xml", None)        # DataFrame resultante de leer XML
    ss.setdefault("rf_df_firmes", None)
    ss.setdefault("rf_df_exigibles", None)
    ss.setdefault("rf_df_tc", None)
    ss.setdefault("rf_cross_done", False)
    ss.setdefault("rf_counts", dict(total=0, unicos=0))
    ss.setdefault("rf_export_ready", False)

_ensure_state()

# -----------------------------------------------------------------------------
# Utilidades UI
# -----------------------------------------------------------------------------
def pill(text: str):
    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:6px 10px;
            border-radius:999px;
            background:#eef2ff;
            color:#3730a3;
            font-weight:600;
            font-size:12px;">
            {text}
        </span>
        """,
        unsafe_allow_html=True,
    )

def section(title: str, subtitle: str | None = None, extra_right: str | None = None):
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader(title)
        if subtitle:
            st.caption(subtitle)
    with c2:
        if extra_right:
            st.markdown(f"<div style='text-align:right'>{extra_right}</div>", unsafe_allow_html=True)
    st.divider()


# -----------------------------------------------------------------------------
# Lectura de Tipo de Cambio
# -----------------------------------------------------------------------------
def _read_excel_bytes(name: str, raw: bytes) -> pd.DataFrame:
    ext = name.lower().rsplit(".", 1)[-1]
    bio = io.BytesIO(raw)
    if ext == "xlsx":
        return pd.read_excel(bio, engine="openpyxl")
    elif ext == "xls":
        return pd.read_excel(bio, engine="xlrd")
    else:
        bio.seek(0)
        return pd.read_excel(bio)

def _load_tipo_cambio_local() -> pd.DataFrame | None:
    xlsx = DATA_DIR / "Tipo Cambio.xlsx"
    xls = DATA_DIR / "Tipo Cambio.xls"
    try_paths = []
    if xlsx.exists():
        try_paths.append((xlsx, "openpyxl"))
    if xls.exists():
        try_paths.append((xls, "xlrd"))

    for pth, eng in try_paths:
        try:
            return pd.read_excel(pth, engine=eng)
        except Exception as e:
            st.warning(f"No pude leer '{pth.name}' con {eng}: {e}")
    return None

def tipo_cambio_input() -> pd.DataFrame | None:
    st.markdown("### Tipo de cambio")
    up = st.file_uploader(
        "Sube archivo de tipo de cambio (.xlsx/.xls)",
        type=["xlsx", "xls"], key=st.session_state.tc_uploader_key
    )
    df_tc = None

    if up is not None:
        try:
            df_tc = _read_excel_bytes(up.name, up.read())
            st.success(f"Tipo de cambio cargado: {up.name}")
            with st.expander("Opciones avanzadas"):
                if st.checkbox("Guardar copia en /data como Tipo Cambio.xlsx", value=False):
                    try:
                        DATA_DIR.mkdir(parents=True, exist_ok=True)
                        target = DATA_DIR / "Tipo Cambio.xlsx"
                        df_tc.to_excel(target, index=False)
                        st.info(f"Guardado en: {target}")
                    except Exception as e:
                        st.warning(f"No se pudo guardar en /data: {e}")
        except ImportError:
            st.error(
                "Falta un motor de Excel. Para .xlsx instala **openpyxl**; para .xls instala **xlrd** "
                "(agrégalo a requirements.txt y vuelve a desplegar)."
            )
        except Exception as e:
            st.error(f"Error leyendo tipo de cambio: {e}")
    else:
        df_tc = _load_tipo_cambio_local()
        if df_tc is not None:
            st.info("Tipo de cambio cargado desde `/data`.")
    return df_tc


# -----------------------------------------------------------------------------
# Extracción de XML desde ZIP (CORREGIDA)
# -----------------------------------------------------------------------------
def _extract_xml_from_zip(blob: bytes, container_name: str) -> Tuple[List[Tuple[str, bytes]], List[str]]:
    ok: List[Tuple[str, bytes]] = []
    issues: List[str] = []
    processed = 0

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            members = [m for m in zf.infolist() if (not m.is_dir()) and m.filename.lower().endswith(".xml")]

            if not members:
                issues.append(f"{container_name} (sin XML)")
                return ok, issues

            for member in members:
                try:
                    xml_bytes = zf.read(member)
                    if not xml_bytes:
                        raise ValueError("Archivo vacío")
                    # Valida XML
                    ET.fromstring(xml_bytes)
                    ok.append((member.filename, xml_bytes))
                    processed += 1
                    if processed % 1000 == 0:
                        st.info(f"{container_name}: {processed:,} XML procesados...", icon="ℹ️")
                except Exception:
                    issues.append(f"{container_name}:{member.filename}")

    except zipfile.BadZipFile:
        issues.append(f"{container_name} (ZIP inválido)")
    except Exception as e:
        issues.append(f"{container_name} (error ZIP: {e})")

    return ok, issues


# -----------------------------------------------------------------------------
# Parseo de XML CFDI (mínimo robusto)
# -----------------------------------------------------------------------------
NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/3",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}

def _parse_emisor_rfc(xml_bytes: bytes) -> str | None:
    try:
        root = ET.fromstring(xml_bytes)
        emisor = root.find(".//cfdi:Emisor", namespaces=NS)
        if emisor is not None:
            return (emisor.attrib.get("Rfc") or emisor.attrib.get("rfc") or "").strip()
    except Exception:
        return None
    return None

def _iter_xml_summary(xmls: List[Tuple[str, bytes]]) -> Iterable[Dict[str, str]]:
    for name, xb in xmls:
        rfc = _parse_emisor_rfc(xb) or ""
        yield {"archivo": name, "rfc_emisor": rfc}


# -----------------------------------------------------------------------------
# Lectura “Firmes / Exigibles”
# -----------------------------------------------------------------------------
def _load_csv_if_exists(path: Path, friendly_name: str) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        st.warning(f"No pude leer {friendly_name}: {e}")
        return None

def load_firmes_exigibles() -> Tuple[pd.DataFrame | None, pd.DataFrame | None]:
    df_firmes = _load_csv_if_exists(FIRMES_DIR / "firmes_latest.csv", "firmes_latest.csv")
    df_exigibles = _load_csv_if_exists(EXIGIBLES_DIR / "exigibles_latest.csv", "exigibles_latest.csv")
    return df_firmes, df_exigibles


# -----------------------------------------------------------------------------
# Cruce de datos (simple por RFC emisor)
# -----------------------------------------------------------------------------
def cross_data(df_xml: pd.DataFrame, df_firmes: pd.DataFrame | None, df_exigibles: pd.DataFrame | None) -> pd.DataFrame:
    out = df_xml.copy()
    if df_firmes is not None and "rfc" in {c.lower() for c in df_firmes.columns}:
        df_f = df_firmes.rename(columns={c: c.lower() for c in df_firmes.columns})
        out["en_firmes"] = out["rfc_emisor"].str.upper().isin(df_f["rfc"].astype(str).str.upper())
    else:
        out["en_firmes"] = False

    if df_exigibles is not None and "rfc" in {c.lower() for c in df_exigibles.columns}:
        df_e = df_exigibles.rename(columns={c: c.lower() for c in df_exigibles.columns})
        out["en_exigibles"] = out["rfc_emisor"].str.upper().isin(df_e["rfc"].astype(str).str.upper())
    else:
        out["en_exigibles"] = False

    return out


# -----------------------------------------------------------------------------
# Export a Excel
# -----------------------------------------------------------------------------
def export_excel(df: pd.DataFrame) -> bytes:
    buff = io.BytesIO()
    with pd.ExcelWriter(buff, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="Resultado")
    return buff.getvalue()


# -----------------------------------------------------------------------------
# Acciones / Botones
# -----------------------------------------------------------------------------
def reset_all():
    ss = st.session_state
    ss.rf_xml_ok = []
    ss.rf_xml_issues = []
    ss.rf_df_xml = None
    ss.rf_df_firmes = None
    ss.rf_df_exigibles = None
    ss.rf_cross_done = False
    ss.rf_counts = dict(total=0, unicos=0)
    ss.rf_export_ready = False
    # Cambia keys para “limpiar” uploaders
    ss.rf_uploader_key = f"rf_zip_{int(os.urandom(2).hex(), 16)}"
    ss.tc_uploader_key = f"rf_tc_{int(os.urandom(2).hex(), 16)}"
    st.experimental_rerun()


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
st.title("Riesgo Fiscal")

# --- Tipo de cambio (opcional para tus cálculos) ---
df_tc = tipo_cambio_input()
st.divider()

# --- Cargar ZIP ---
section("1) Cargar ZIP de XML", "Sube el contenedor con todos tus CFDI timbrados")
zip_file = st.file_uploader("ZIP con XML", type=["zip"], key=st.session_state.rf_uploader_key)
c1, c2 = st.columns([1, 1])
with c1:
    btn_read_zip = st.button("Leer ZIP", use_container_width=True)
with c2:
    btn_retry = st.button("Reintentar / Limpiar", type="secondary", use_container_width=True)

if btn_retry:
    reset_all()

if btn_read_zip:
    if not zip_file:
        st.warning("Primero selecciona un archivo ZIP.")
    else:
        st.info("Leyendo ZIP…")
        ok, issues = _extract_xml_from_zip(zip_file.read(), zip_file.name)
        st.session_state.rf_xml_ok = ok
        st.session_state.rf_xml_issues = issues
        st.session_state.rf_loaded_zip_name = zip_file.name

if st.session_state.rf_xml_ok:
    total = len(st.session_state.rf_xml_ok)
    # Construye DF básico (solo después de “Leer XML”)
    section("2) Leer XML", "Extrae RFC Emisor y prepara el índice de análisis")
    c1, c2, c3 = st.columns(3)
    with c1:
        pill(f"Documentos XML: {total:,}")
    # RFC únicos
    df_preview = pd.DataFrame(list(_iter_xml_summary(st.session_state.rf_xml_ok)))
    rfc_unicos = df_preview["rfc_emisor"].str.upper().replace("", pd.NA).dropna().nunique()
    st.session_state.rf_counts = dict(total=total, unicos=int(rfc_unicos))
    with c2:
        pill(f"RFC únicos: {st.session_state.rf_counts['unicos']:,}")
    with c3:
        if st.session_state.rf_xml_issues:
            pill(f"Archivos con problema: {len(st.session_state.rf_xml_issues):,}")

    if st.button("Generar índice de XML", use_container_width=True):
        st.session_state.rf_df_xml = df_preview
        st.success("Índice generado.")
        with st.expander("Ver muestra (5)"):
            st.dataframe(df_preview.head(5), use_container_width=True)

# --- Cruce con listas Firmes/Exigibles ---
if st.session_state.rf_df_xml is not None:
    section("3) Cruce con Firmes / Exigibles", "Se cruzará por RFC del Emisor")

    df_firmes, df_exigibles = load_firmes_exigibles()
    st.session_state.rf_df_firmes = df_firmes
    st.session_state.rf_df_exigibles = df_exigibles

    falta_firmes = df_firmes is None
    falta_exigibles = df_exigibles is None

    msg = []
    if falta_firmes:
        msg.append("No existe **firmes_latest.csv** en `/data/firmes`.")
    if falta_exigibles:
        msg.append("No existe **exigibles_latest.csv** en `/data/exigibles`.")

    if msg:
        st.warning(" ".join(msg))
        # Botón para ir a la página de carga si existe
        dest = PAGES_DIR / "17_Archivo_firmes.py"
        if dest.exists():
            st.page_link(str(dest.relative_to(ROOT)), label="➡️ Ir a cargar Firmes/Exigibles")
    else:
        if st.button("Cruzar datos", use_container_width=True):
            try:
                df_out = cross_data(st.session_state.rf_df_xml, df_firmes, df_exigibles)
                st.session_state.rf_df_xml = df_out
                st.session_state.rf_cross_done = True
                st.success("Cruce completado.")
                with st.expander("Ver muestra (20)"):
                    st.dataframe(df_out.head(20), use_container_width=True)
            except Exception as e:
                st.error(f"Error en cruce: {e}")

# --- Exportar y Reiniciar ---
if st.session_state.get("rf_cross_done") and st.session_state.rf_df_xml is not None:
    section("4) Exportar y finalizar", "Descarga el resultado y limpia el estado")

    # Garantiza carpeta de export
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        xls_bytes = export_excel(st.session_state.rf_df_xml)
        st.session_state.rf_export_ready = True
        st.download_button(
            "⬇️ Descargar Excel",
            data=xls_bytes,
            file_name="riesgo_fiscal.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"No se pudo generar Excel: {e}")

    st.caption("Al presionar **Reiniciar** se vacía todo (uploaders, contadores y tablas).")

    if st.button("🔄 Reiniciar", type="secondary", use_container_width=True):
        reset_all()


# -----------------------------------------------------------------------------
# Pie de página / ayuda
# -----------------------------------------------------------------------------
with st.expander("Ayuda y notas"):
    st.markdown(
        """
- **ZIP con XML**: Se validan y se ignoran archivos corruptos sin detener el proceso.
- **Progreso**: Para lotes muy grandes se muestra un avance cada 1,000 XML.
- **Firmes/Exigibles**: Coloca `firmes_latest.csv` en `data/firmes/` y `exigibles_latest.csv` en `data/exigibles/`.
- **Tipo de Cambio**: Puedes subirlo desde la UI o colocarlo en `data/` como `Tipo Cambio.xlsx`/`.xls`.
- **Reset total**: tras descargar, usa **Reiniciar**; también puedes usar **Reintentar/Limpiar** en la sección ZIP.
        """
    )
