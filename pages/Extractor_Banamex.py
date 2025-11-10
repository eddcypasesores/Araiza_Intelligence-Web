from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
import tempfile

import pandas as pd
import streamlit as st

from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import _NAV_CSS as BRAND_NAV_CSS, _navbar_logo_data
from extractor import extraer_datos_banamex_formato_final

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LOGO_LEFT = ASSETS_DIR / "logo1.jpeg"
LOGO_RIGHT = ASSETS_DIR / "logo2.jpg"


def _build_back_href() -> str:
    params = auth_query_params()
    query = urlencode(params) if params else ""
    base = "./convertidor_estados_cuenta"
    return f"{base}?{query}" if query else base


def _render_back_nav() -> None:
    st.markdown(BRAND_NAV_CSS, unsafe_allow_html=True)
    logo_src = _navbar_logo_data()
    back_href = _build_back_href()
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


st.set_page_config(page_title="Extractor Banamex", layout="centered")
ensure_session_from_token()
_render_back_nav()
st.markdown(
    """
    <style>
    [data-testid="stSidebar"],
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    #MainMenu,
    [data-testid="collapsedControl"] { display:none !important; }
    #root > div:nth-child(1) > div[data-testid="stSidebarNav"] { display:none !important; }
    body, html, [data-testid="stAppViewContainer"] { background:#f5f6fb !important; }
    .block-container { padding-top:80px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.lower()
        if key in lower_map:
            return lower_map[key]
    for column in df.columns:
        if any(cand.lower() in column.lower() for cand in candidates):
            return column
    return None


def _to_float_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
    )
    cleaned = cleaned.str.replace(r"^\(([\d\.]+)\)$", r"-\1", regex=True)
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


col1, col2, col3 = st.columns([1, 4, 1])
with col1:
    if LOGO_LEFT.exists():
        st.image(str(LOGO_LEFT), width=110)
with col2:
    st.markdown(
        "<h2 style='text-align:center;margin:0;'>Extractor de Estados de Cuenta Banamex</h2>",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    if LOGO_RIGHT.exists():
        st.image(str(LOGO_RIGHT), width=140)

st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

archivo = st.file_uploader("Selecciona tu estado de cuenta en PDF", type=["pdf"])

if archivo is None:
    st.info("Sube un PDF para comenzar.")
    st.stop()

with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
    tmp.write(archivo.read())
    tmp_path = Path(tmp.name)

st.info("Procesando archivo PDF...")

try:
    df = extraer_datos_banamex_formato_final(str(tmp_path))
    if df is None or df.empty:
        st.warning("No se detectaron movimientos validos en el documento.")
    else:
        cargos_col = _find_col(df, ["cargo", "cargos", "debitos", "debito"])
        abonos_col = _find_col(df, ["abono", "abonos", "creditos", "credito"])

        total_cargo = float(_to_float_series(df[cargos_col]).sum()) if cargos_col else 0.0
        total_abono = float(_to_float_series(df[abonos_col]).sum()) if abonos_col else 0.0

        st.success(f"Extraccion completada con exito. Movimientos detectados: {len(df)}")
        st.subheader("Totales")
        tot1, tot2 = st.columns(2)
        tot1.metric("Total cargos", f"${total_cargo:,.2f}")
        tot2.metric("Total abonos", f"${total_abono:,.2f}")

        with st.expander("Ver movimientos extraidos"):
            st.caption(f"Tabla completa de {len(df)} filas.")
            st.dataframe(df, use_container_width=True, height=500)

        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_name = output_dir / f"banamex_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

        try:
            df.to_excel(output_name, index=False)
            download_data = output_name.read_bytes()
            filename = output_name.name
        except Exception:
            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)
            download_data = buffer.getvalue()
            filename = f"banamex_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

        st.download_button(
            label="Descargar Excel",
            data=download_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
except Exception as exc:
    st.error(f"Ocurrio un error al extraer datos: {exc}")
finally:
    try:
        os.remove(tmp_path)
    except Exception:
        pass
