from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from core.theme import apply_theme
from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import render_brand_logout_nav
from core.extractor_scotiabank import extraer_scotiabank

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LEFT_LOGO = ASSETS_DIR / "logo.jpg"
RIGHT_LOGO = ASSETS_DIR / "banks/scotiabank.jpeg"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _back_href() -> str:
    params = auth_query_params()
    query = urlencode(params) if params else ""
    base = "./convertidor_estados_cuenta"
    return f"{base}?{query}" if query else base


def _img_to_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Scotiabank")
    buffer.seek(0)
    return buffer.getvalue()


def _summary(df: pd.DataFrame) -> dict[str, float]:
    cargos = pd.to_numeric(df.get("Cargo"), errors="coerce").fillna(0).sum()
    abonos = pd.to_numeric(df.get("Abono"), errors="coerce").fillna(0).sum()
    saldos = pd.to_numeric(df.get("Saldo"), errors="coerce").dropna()
    saldo_final = float(saldos.iloc[-1]) if not saldos.empty else abonos - cargos
    return {"cargos": float(cargos), "abonos": float(abonos), "saldo": saldo_final}


def _render_nav() -> None:
    render_brand_logout_nav(
        "pages/convertidor_estados_cuenta.py",
        brand="Extractor Scotiabank",
        action_label="Atras",
        action_href=_back_href(),
    )


def _render_header() -> None:
    c1, c2, c3 = st.columns([1.2, 5, 1.2], gap="large")
    left_logo = _img_to_data_uri(LEFT_LOGO)
    right_logo = _img_to_data_uri(RIGHT_LOGO)
    with c1:
        if left_logo:
            st.markdown(f"<img src='{left_logo}' class='logo-img' alt='Araiza logo'>", unsafe_allow_html=True)
    with c2:
        st.markdown("<h2 class='brand-title'>EXTRACTOR SCOTIABANK</h2>", unsafe_allow_html=True)
    with c3:
        if right_logo:
            st.markdown(f"<img src='{right_logo}' class='logo-img' alt='Scotiabank logo'>", unsafe_allow_html=True)


st.set_page_config(page_title="Extractor Scotiabank", layout="wide")
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
      #root > div:nth-child(1) > div[data-testid="stSidebarNav"] {
        display:none !important;
      }
      body, html, [data-testid="stAppViewContainer"] {
        background:#f5f6fb !important;
      }
      .block-container{
        max-width:100% !important;
        padding:80px 2rem 2rem;
      }
      .logo-img{
        height:150px;
        width:auto;
        object-fit:contain;
        display:block;
        margin:0 auto;
      }
      .brand-title{
        margin:0;
        text-align:center;
        font-weight:800;
        letter-spacing:.4px;
        line-height:1.1;
        font-size:clamp(36px,4.4vw,60px);
      }
      hr.header-sep{
        margin:.75rem 0 1rem;
        border:none;
        height:1px;
        background:rgba(0,0,0,.08);
      }
      [data-testid="stMetric"]{ background:#f8f9fa; border-radius:12px; padding:.75rem; }
      .hint{
        background:#eef2ff;
        border:1px solid #dde3ff;
        border-radius:10px;
        padding:12px 16px;
        color:#0f172a;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

_render_header()
st.markdown("<hr class='header-sep'/>", unsafe_allow_html=True)
st.caption("Sube tu PDF de Scotiabank y generaremos un Excel con los movimientos detectados.")

uploaded = st.file_uploader("Sube el estado de cuenta en PDF", type=["pdf"])

if uploaded is None:
    st.markdown("<div class='hint'>Sube un PDF para comenzar.</div>", unsafe_allow_html=True)
else:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        with st.spinner("Procesando PDF..."):
            df = extraer_scotiabank(tmp_path)

        if df.empty:
            st.warning("No se encontraron movimientos. Verifica que el PDF contenga lineas con fecha.")
        else:
            st.success(f"Movimientos extraidos: {len(df)}")
            st.dataframe(df.head(200), use_container_width=True, hide_index=True)

            summary = _summary(df)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total cargos", f"${summary['cargos']:,.2f}")
            c2.metric("Total abonos", f"${summary['abonos']:,.2f}")
            c3.metric("Saldo final estimado", f"${summary['saldo']:,.2f}")

            with st.expander("Ver tabla completa"):
                st.dataframe(df, use_container_width=True, height=520)

            data_xlsx = _df_to_excel_bytes(df)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"movimientos_scotiabank_{timestamp}.xlsx"
            file_path = OUTPUT_DIR / filename
            file_path.write_bytes(data_xlsx)

            csv_bytes = df.to_csv(index=False).encode("utf-8")

            cols = st.columns(2)
            cols[0].download_button(
                "Descargar Excel",
                data_xlsx,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            cols[1].download_button(
                "Descargar CSV",
                csv_bytes,
                file_name=filename.replace(".xlsx", ".csv"),
                mime="text/csv",
                use_container_width=True,
            )

            st.caption(f"Archivo guardado en: {file_path}")
    except Exception as exc:
        st.error("Ocurrio un error durante la extraccion.")
        st.exception(exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
