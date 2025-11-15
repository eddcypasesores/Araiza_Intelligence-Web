from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from core.theme import apply_theme
from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import render_brand_logout_nav
from core.extractor_base import extraer_base

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LOGO_LEFT = ASSETS_DIR / "logo.jpg"
LOGO_RIGHT = ASSETS_DIR / "banks/BASE.jpeg"


def _back_href() -> str:
    params = auth_query_params()
    query = urlencode(params) if params else ""
    base = "./convertidor_estados_cuenta"
    return f"{base}?{query}" if query else base


def _render_nav() -> None:
    render_brand_logout_nav(
        "pages/convertidor_estados_cuenta.py",
        brand="Extractor Banco BASE",
        action_label="Atrás",
        action_href=_back_href(),
    )
st.set_page_config(page_title="Extractor Banco BASE", layout="centered")
apply_theme()
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
    st.markdown(
        "<h2 style='text-align:center;margin:0;'>Extractor de Estado de Cuenta Banco BASE</h2>",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    if LOGO_RIGHT.exists():
        st.image(str(LOGO_RIGHT), width=140)

st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

uploaded = st.file_uploader("PDF de Banco BASE", type=["pdf"])

if uploaded is None:
    st.info("Sube un PDF para comenzar.")
    st.stop()

uploaded.seek(0)
with st.spinner("Extrayendo movimientos..."):
    df = extraer_base(uploaded)

if df.empty:
    st.warning("No se detectaron movimientos válidos en el documento.")
    st.stop()

cargos_total = pd.to_numeric(df.get("Cargo"), errors="coerce").fillna(0).sum()
abonos_total = pd.to_numeric(df.get("Abono"), errors="coerce").fillna(0).sum()

st.success(f"Extracción completada. Movimientos detectados: {len(df)}")
tot1, tot2 = st.columns(2)
tot1.metric("Total cargos", f"${cargos_total:,.2f}")
tot2.metric("Total abonos", f"${abonos_total:,.2f}")

with st.expander("Ver movimientos extraídos"):
    st.dataframe(df, use_container_width=True, height=500)

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Banco BASE", index=False)
buffer.seek(0)

filename = f"banco_base_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
st.download_button(
    "Descargar Excel",
    data=buffer,
    file_name=filename,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
