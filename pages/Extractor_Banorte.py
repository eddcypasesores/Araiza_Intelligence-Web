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
from core.extractor_banorte import procesar_pdf

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LEFT_LOGO = ASSETS_DIR / "logo.jpg"
RIGHT_LOGO = ASSETS_DIR / "banks/banorte.jpeg"
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


def _totals(df: pd.DataFrame) -> dict[str, float]:
    cargos = pd.to_numeric(df.get("Cargo"), errors="coerce").fillna(0).sum()
    abonos = pd.to_numeric(df.get("Abono"), errors="coerce").fillna(0).sum()
    saldos = pd.to_numeric(df.get("Saldo"), errors="coerce").dropna()
    saldo_val = float(saldos.iloc[-1]) if not saldos.empty else cargos - abonos
    return {"cargos": float(cargos), "abonos": float(abonos), "saldo": saldo_val}


def _run_extractor(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, bytes | None, str]:
    safe_name = Path(filename).name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(file_bytes)
        tmp_path = tmp_pdf.name
    try:
        xlsx_path, df = procesar_pdf(tmp_path)
        excel_bytes = Path(xlsx_path).read_bytes() if xlsx_path and Path(xlsx_path).exists() else None
        suggested = Path(xlsx_path).name if xlsx_path else Path(safe_name).with_suffix(".xlsx").name
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return df, excel_bytes, suggested


def _render_nav() -> None:
    render_brand_logout_nav(
        "pages/convertidor_estados_cuenta.py",
        brand="Extractor Banorte",
        action_label="Atrás",
        action_href=_back_href(),
    )


st.set_page_config(page_title="Extractor Banorte", layout="wide")
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
    :root {
      --header-logo-height: clamp(110px, 14vw, 170px);
      --section-gap: .50rem;
    }
    .block-container{
      max-width:100% !important;
      padding:80px 2rem 2rem;
    }
    .logo {
      height: var(--header-logo-height);
      width:auto;
      object-fit:contain;
      display:block;
      margin:0 auto;
    }
    .header-center {
      display:flex;
      align-items:center;
      justify-content:center;
      height:100%;
    }
    .header-title  {
      margin:0;
      text-align:center;
      font-weight:800;
      line-height:1.15;
      letter-spacing:.2px;
      font-size:clamp(22px,3.2vw,40px);
    }
    .header-divider{
      border:0;
      border-top:1px solid #e6e6e6;
      margin:.25rem 0 1rem 0;
    }
    .section-title {
      font-size:.90rem;
      font-weight:600;
      line-height:1.2;
      margin:0 0 var(--section-gap) 0;
    }
    div[data-testid="stFileUploader"] { margin-top:0 !important; }
    [data-testid="stFileUploader"] button {
      background-color:#579EF7;
      color:#fff;
      border-radius:8px;
      padding:8px 16px;
    }
    [data-testid="stFileUploader"] button:hover { background-color:#3f89e0; }
    [data-testid="stMetric"]{ background:#f8f9fa; border-radius:12px; padding:.75rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns([1, 5, 1])
with c1:
    left_logo = _img_to_data_uri(LEFT_LOGO)
    if left_logo:
        st.markdown(f"<img src='{left_logo}' alt='Logo Araiza' class='logo'>", unsafe_allow_html=True)
with c2:
    st.markdown("<div class='header-center'><h1 class='header-title'>EXTRACTOR BANORTE</h1></div>", unsafe_allow_html=True)
with c3:
    right_logo = _img_to_data_uri(RIGHT_LOGO)
    if right_logo:
        st.markdown(f"<img src='{right_logo}' alt='Logo Banorte' class='logo'>", unsafe_allow_html=True)

st.markdown("<hr class='header-divider'>", unsafe_allow_html=True)

st.markdown("<p class='section-title'>Sube tu PDF de Banorte</p>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["pdf"], label_visibility="collapsed")

if uploaded_file is None:
    st.info("Sube un PDF para comenzar.")
else:
    file_bytes = uploaded_file.read()
    with st.spinner("Procesando PDF…"):
        try:
            df, excel_bytes, suggested_name = _run_extractor(file_bytes, uploaded_file.name)
        except Exception as exc:
            st.error("❌ Error al procesar el archivo.")
            st.exception(exc)
            st.stop()

    if df is None or df.empty:
        st.warning("No se encontraron movimientos en el PDF.")
    else:
        st.subheader("📋 Movimientos extraídos")
        st.dataframe(df.head(200), use_container_width=True)

        summary = _totals(df)
        cA, cB, cC = st.columns(3)
        cA.metric("💸 Total Cargos", f"${summary['cargos']:,.2f}")
        cB.metric("💰 Total Abonos", f"${summary['abonos']:,.2f}")
        cC.metric("📊 Saldo final estimado", f"${summary['saldo']:,.2f}")

        with st.expander("🔎 Ver tabla completa"):
            st.dataframe(df, use_container_width=True, height=520)

        # Persist Excel/CSV
        if excel_bytes is None:
            excel_bytes = BytesIO()
            df.to_excel(excel_bytes, index=False, sheet_name="Banorte")
            excel_bytes.seek(0)
            excel_payload = excel_bytes.getvalue()
        else:
            excel_payload = excel_bytes

        target_path = OUTPUT_DIR / suggested_name
        target_path.write_bytes(excel_payload)

        cols = st.columns(2)
        cols[0].download_button(
            "📥 Descargar Excel",
            data=excel_payload,
            file_name=suggested_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        csv_buffer.seek(0)
        cols[1].download_button(
            "⬇️ Descargar CSV",
            data=csv_buffer.getvalue(),
            file_name=Path(suggested_name).with_suffix(".csv").name,
            mime="text/csv",
            use_container_width=True,
        )

        st.caption(f"Archivo guardado también en: {target_path}")
