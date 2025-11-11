from __future__ import annotations

import hashlib
import io
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import _NAV_CSS as BRAND_NAV_CSS, _navbar_logo_data
from core.extractor_bbva import extract_bbva_pdf_to_df

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LOGO_LEFT = ASSETS_DIR / "logo.jpg"
LOGO_RIGHT = ASSETS_DIR / "banks/bbva.jpeg"


def _nav_back_href() -> str:
    params = auth_query_params()
    query = urlencode(params) if params else ""
    base = "./convertidor_estados_cuenta"
    return f"{base}?{query}" if query else base


def _render_nav() -> None:
    st.markdown(BRAND_NAV_CSS, unsafe_allow_html=True)
    logo_src = _navbar_logo_data()
    back_href = _nav_back_href()
    nav_html = (
        '<div class="custom-nav">'
        '<div class="nav-brand">'
        f'<img src="{logo_src}" alt="Araiza Intelligence" />'
        "<span>Araiza Intelligence</span>"
        "</div>"
        '<div class="nav-actions">'
        f'<a href="{back_href}" target="_self">&larr; Regresar</a>'
        "</div>"
        "</div>"
    )
    st.markdown(nav_html, unsafe_allow_html=True)


st.set_page_config(page_title="Extractor BBVA", layout="centered")
ensure_session_from_token()
_render_nav()
st.markdown(
    """
    <style>
    [data-testid="stSidebar"],
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    #MainMenu,
    [data-testid="collapsedControl"],
    #root > div:nth-child(1) > div[data-testid="stSidebarNav"] { display:none !important; }
    body, html, [data-testid="stAppViewContainer"] { background:#f5f6fb !important; }
    .block-container { padding-top:80px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns([1, 4, 1])
with col1:
    if LOGO_LEFT.exists():
        st.image(str(LOGO_LEFT), width=110)
with col2:
    st.markdown("<h2 style='text-align:center;margin:0;'>Extractor de Estados de Cuenta BBVA</h2>", unsafe_allow_html=True)
with col3:
    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    if LOGO_RIGHT.exists():
        st.image(str(LOGO_RIGHT), width=140)

st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

st.caption("Extracción sin OCR usando pdfplumber · Deploy listo para Render")

st.subheader("1. Carga el estado de cuenta")
uploaded = st.file_uploader("Selecciona el archivo PDF", type=["pdf"], label_visibility="visible")
catalogo_cuentas = st.file_uploader(
    "Catálogo de cuentas (opcional)",
    type=["csv", "xlsx", "xls"],
    help="Si cuentas con un catálogo para enriquecer los conceptos puedes subirlo aquí.",
)


def _load_catalog_df(uploaded) -> pd.DataFrame | None:
    if uploaded is None:
        return None
    try:
        if uploaded.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)
    except Exception as exc:
        st.warning(f"No se pudo leer el catálogo: {exc}")
        return None
    return df


def _match_catalog_column(df: pd.DataFrame, options: list[str]) -> str | None:
    for col in df.columns:
        low = str(col).lower()
        if any(opt in low for opt in options):
            return col
    return None


def _enrich_with_catalog(df: pd.DataFrame, catalog: pd.DataFrame) -> None:
    if catalog is None or df.empty or "Cuenta" not in df.columns:
        return
    key_col = _match_catalog_column(catalog, ["cuenta", "clabe", "numero"])
    value_col = _match_catalog_column(catalog, ["concepto", "descripcion", "descripción", "nombre", "detalle"])
    if not key_col or not value_col:
        st.info("El catálogo no tiene columnas reconocibles (se buscó 'Cuenta' y 'Concepto/Descripción').")
        return
    work = catalog[[key_col, value_col]].dropna()
    if work.empty:
        return
    work[key_col] = work[key_col].astype(str).str.strip()
    work[value_col] = work[value_col].astype(str).str.strip()
    mapping = work.drop_duplicates(subset=[key_col]).set_index(key_col)[value_col]

    cuenta_series = df["Cuenta"].astype(str).str.strip()
    concept_fill = cuenta_series.map(mapping)
    mask_concept = df["Concepto"].astype(str).str.strip() == ""
    df.loc[mask_concept, "Concepto"] = concept_fill[mask_concept].fillna(df.loc[mask_concept, "Concepto"])

    descripcion_fill = cuenta_series.map(mapping)
    mask_desc = df["Descripción"].astype(str).str.strip() == ""
    df.loc[mask_desc, "Descripción"] = descripcion_fill[mask_desc].fillna(df.loc[mask_desc, "Descripción"])


@st.cache_data(show_spinner=False)
def _run_extraction(file_bytes: bytes) -> pd.DataFrame:
    return extract_bbva_pdf_to_df(io.BytesIO(file_bytes))


if uploaded:
    st.info(f"Archivo: **{uploaded.name}** · {uploaded.size / 1024:.1f} KB")
    if st.button("Convertir a Excel", type="primary"):
        try:
            file_bytes = uploaded.read()
            df = _run_extraction(file_bytes)
            catalog_df = _load_catalog_df(catalogo_cuentas)
            if catalog_df is not None:
                _enrich_with_catalog(df, catalog_df)
            if df.empty:
                st.warning("No se detectaron movimientos. Verifica que el PDF contenga movimientos.")
            else:
                cargos_total = pd.to_numeric(df.get("Cargos"), errors="coerce").fillna(0).sum()
                abonos_total = pd.to_numeric(df.get("Abonos"), errors="coerce").fillna(0).sum()

                st.success(f"Extracción completada con éxito. Movimientos detectados: {len(df)}")
                tot1, tot2 = st.columns(2)
                tot1.metric("Total cargos", f"${cargos_total:,.2f}")
                tot2.metric("Total abonos", f"${abonos_total:,.2f}")

                with st.expander("Ver movimientos extraídos"):
                    st.dataframe(df, use_container_width=True, hide_index=True)

                out = io.BytesIO()
                with pd.ExcelWriter(out, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="BBVA")
                out.seek(0)

                digest = hashlib.md5(file_bytes).hexdigest()[:8]
                fname = f"bbva_{datetime.now():%Y%m%d}_{digest}.xlsx"

                st.download_button(
                    "Descargar Excel",
                    data=out,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except Exception as exc:
            st.error("Ocurrió un error durante la extracción.")
            st.exception(exc)
else:
    st.info("Sube un PDF para comenzar.")
