from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
import tempfile

import pandas as pd
import streamlit as st

from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import _NAV_CSS as BRAND_NAV_CSS, _navbar_logo_data
from core.extractor_banbajio import extraer_movimientos

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LOGO_LEFT = ASSETS_DIR / "logo1.jpeg"
LOGO_RIGHT = ASSETS_DIR / "logo2.jpg"


def _back_href() -> str:
    params = auth_query_params()
    query = urlencode(params) if params else ""
    base = "./convertidor_estados_cuenta"
    return f"{base}?{query}" if query else base


def _render_nav() -> None:
    st.markdown(BRAND_NAV_CSS, unsafe_allow_html=True)
    logo_src = _navbar_logo_data()
    back_link = _back_href()
    nav_html = (
        '<div class="custom-nav">'
        '<div class="nav-brand">'
        f'<img src="{logo_src}" alt="Araiza Intelligence" />'
        "<span>Araiza Intelligence</span>"
        "</div>"
        '<div class="nav-actions">'
        f'<a href="{back_link}" target="_self">&larr; Regresar</a>'
        "</div>"
        "</div>"
    )
    st.markdown(nav_html, unsafe_allow_html=True)


st.set_page_config(page_title="Extractor BanBajío", layout="centered")
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
    [data-testid="stFileUploader"] button {
        background-color:#579EF7;
        color:#fff;
        border-radius:8px;
        padding:8px 16px;
    }
    [data-testid="stFileUploader"] button:hover { background-color:#3f89e0; }
    </style>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns([1, 4, 1])
with col1:
    if LOGO_LEFT.exists():
        st.image(str(LOGO_LEFT), width=110)
with col2:
    st.markdown("<h2 style='text-align:center;margin:0;'>Extractor de Estados de Cuenta BanBajío</h2>", unsafe_allow_html=True)
with col3:
    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    if LOGO_RIGHT.exists():
        st.image(str(LOGO_RIGHT), width=140)

st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

uploaded = st.file_uploader("Selecciona el PDF de BanBajío", type=["pdf"])


if uploaded:
    st.info(f"Archivo: **{uploaded.name}** · {uploaded.size / 1024:.1f} KB")
    if st.button("Convertir a Excel", type="primary"):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            df = extraer_movimientos(tmp_path)

            if df.empty:
                st.warning("No se detectaron movimientos en el PDF. Verifica el archivo.")
            else:
                depositos_total = pd.to_numeric(df.get("Depósitos"), errors="coerce").fillna(0).sum()
                retiros_total = pd.to_numeric(df.get("Retiros"), errors="coerce").fillna(0).sum()

                st.success(f"Extracción completada. Movimientos detectados: {len(df)}")
                tot1, tot2 = st.columns(2)
                tot1.metric("Total depósitos", f"${depositos_total:,.2f}")
                tot2.metric("Total retiros", f"${retiros_total:,.2f}")

                with st.expander("Ver movimientos extraídos"):
                    st.dataframe(df, use_container_width=True)

                buffer = io.BytesIO()
                df.to_excel(buffer, index=False)
                buffer.seek(0)
                fname = f"banbajio_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

                st.download_button(
                    label="Descargar Excel",
                    data=buffer,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except Exception as exc:
            st.error(f"Ocurrió un error al procesar el PDF: {exc}")
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
else:
    st.info("Sube un PDF para comenzar.")
