from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import _NAV_CSS as BRAND_NAV_CSS, _navbar_logo_data
from core.extractor_banorte import procesar_pdf


ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LOGO_LEFT = ASSETS_DIR / "logo1.jpeg"
LOGO_RIGHT = ASSETS_DIR / "logo2.jpg"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def _back_href() -> str:
    params = auth_query_params()
    query = urlencode(params) if params else ""
    base = "./convertidor_estados_cuenta"
    return f"{base}?{query}" if query else base


def _render_nav() -> None:
    st.markdown(BRAND_NAV_CSS, unsafe_allow_html=True)
    logo_src = _navbar_logo_data()
    nav_html = (
        '<div class="custom-nav">'
        '<div class="nav-brand">'
        f'<img src="{logo_src}" alt="Araiza Intelligence" />'
        "<span>Araiza Intelligence</span>"
        "</div>"
        '<div class="nav-actions">'
        f'<a href="{_back_href()}" target="_self">&larr; Regresar</a>'
        "</div>"
        "</div>"
    )
    st.markdown(nav_html, unsafe_allow_html=True)


st.set_page_config(page_title="Extractor Banorte", layout="centered")
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
    st.markdown("<h2 style='text-align:center;margin:0;'>Extractor de Estado de Cuenta Banorte</h2>", unsafe_allow_html=True)
with col3:
    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    if LOGO_RIGHT.exists():
        st.image(str(LOGO_RIGHT), width=140)

st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

archivo = st.file_uploader("Sube tu estado de cuenta en PDF", type=["pdf"])

if archivo:
    tmp_path = OUTPUT_DIR / archivo.name
    tmp_path.write_bytes(archivo.read())
    st.success("Archivo cargado correctamente. Procesando...")

    try:
        path_excel, df = procesar_pdf(tmp_path.as_posix())

        for col in ["Cargo", "Abono"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        total_cargo = df["Cargo"].sum()
        total_abono = df["Abono"].sum()

        st.success(f"Extracción completada. Movimientos detectados: {len(df)}")
        tot1, tot2 = st.columns(2)
        tot1.metric("Total Cargos", f"${total_cargo:,.2f}")
        tot2.metric("Total Abonos", f"${total_abono:,.2f}")

        with st.expander("Ver movimientos extraídos"):
            st.dataframe(df, use_container_width=True)

        with open(path_excel, "rb") as fh:
            st.download_button(
                label="Descargar Excel",
                data=fh,
                file_name=Path(path_excel).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    except Exception as exc:
        st.error(f"Ocurrió un error al procesar el archivo: {exc}")
else:
    st.info("Sube un PDF para comenzar.")
