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
from core.extractor_american_express import extraer_american_express

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LEFT_LOGO = ASSETS_DIR / "logo.jpg"
RIGHT_LOGO = ASSETS_DIR / "banks/American_Express.jpeg"


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
        df.to_excel(writer, sheet_name="Movimientos Amex", index=False)
    buffer.seek(0)
    return buffer.getvalue()


def _totals(df: pd.DataFrame) -> dict[str, float]:
    cargos = pd.to_numeric(df.get("Cargo"), errors="coerce").fillna(0).sum()
    abonos = pd.to_numeric(df.get("Abono"), errors="coerce").fillna(0).sum()
    saldo_final = pd.to_numeric(df.get("Saldo"), errors="coerce").dropna()
    saldo_val = float(saldo_final.iloc[-1]) if not saldo_final.empty else cargos - abonos
    return {"cargos": float(cargos), "abonos": float(abonos), "saldo": saldo_val}


def _render_nav() -> None:
    render_brand_logout_nav(
        "pages/convertidor_estados_cuenta.py",
        brand="Extractor American Express",
        action_label="Atrás",
        action_href=_back_href(),
    )


st.set_page_config(page_title="Extractor American Express", layout="wide")
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
    .block-container { padding-top:80px !important; max-width:980px; }

    .header-grid{
      width:100%;
      display:grid;
      grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
      align-items:center;
      gap:16px;
      margin-bottom:10px;
    }
    .header-left{ justify-self:start; }
    .header-center{ justify-self:center; text-align:center; }
    .header-right{ justify-self:end; }
    .header-title{ font-weight:800; margin:0; font-size:48px; color:#0f172a; }
    .section-divider{ border:0; border-top:1px solid #e5e7eb; margin:14px 0 20px 0; }
    .uploader-label{ font-size:16px; margin:0 0 6px 0; }
    [data-testid="stFileUploader"] button {
        background-color:#579EF7;
        color:#fff;
        border-radius:8px;
        padding:8px 16px;
    }
    [data-testid="stFileUploader"] button:hover { background-color:#3f89e0; }
    .hint {
      background:#eaf2ff;
      border:1px solid #d9e6ff;
      border-radius:8px;
      padding:14px 16px;
      color:#0f1d40;
      margin-top:10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

left_logo_src = _img_to_data_uri(LEFT_LOGO)
right_logo_src = _img_to_data_uri(RIGHT_LOGO)

st.markdown(
    f"""
    <div class="header-grid">
      <div class="header-left">{('<img src="'+left_logo_src+'" alt="Araiza logo" style="height:120px;">') if left_logo_src else ''}</div>
      <div class="header-center"><h1 class="header-title">EXTRACTOR AMERICAN EXPRESS</h1></div>
      <div class="header-right">{('<img src="'+right_logo_src+'" alt="Logo American Express" style="height:110px;">') if right_logo_src else ''}</div>
    </div>
    <hr class="section-divider"/>
    """,
    unsafe_allow_html=True,
)

os.makedirs("output", exist_ok=True)

st.markdown('<p class="uploader-label">Sube tu PDF de American Express</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["pdf"], label_visibility="collapsed")

if uploaded_file is None:
    st.markdown('<div class="hint">Sube un PDF para comenzar.</div>', unsafe_allow_html=True)
else:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        with st.spinner("Procesando PDF..."):
            df = extraer_american_express(tmp_path)

        if df.empty:
            st.warning("No se detectaron movimientos. Verifica que el PDF sea un estado de cuenta legible (no escaneado).")
        else:
            summary = _totals(df)
            st.success("¡Extracción completada!")
            st.subheader("📋 Vista previa de movimientos")
            st.dataframe(df.head(200), use_container_width=True)

            st.subheader("📑 Resumen")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total cargos", f"${summary['cargos']:,.2f}")
            c2.metric("Total abonos", f"${summary['abonos']:,.2f}")
            c3.metric("Saldo final estimado", f"${summary['saldo']:,.2f}")

            data_xlsx = _df_to_excel_bytes(df)
            periodo = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Movimientos_Amex_{periodo}.xlsx"

            st.download_button(
                label="⬇️ Descargar Excel",
                data=data_xlsx,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            ruta_out = Path("output") / filename
            with ruta_out.open("wb") as fout:
                fout.write(data_xlsx)
            st.caption(f"Archivo guardado también en: {ruta_out}")
    except Exception as exc:
        st.error(f"Ocurrió un error al procesar el PDF: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
