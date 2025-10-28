"""Portada pública de Araiza Intelligence."""

from pathlib import Path
import base64
import streamlit as st

from core.auth import ensure_session_from_token
from core.navigation import render_nav

st.set_page_config(page_title="Araiza Intelligence", layout="wide")

ensure_session_from_token()

# -------- CSS específico de la portada --------
CUSTOM_CSS = """
<style>
  :root {
    --brand-red: #dc2626;
    --brand-red-dark: #b91c1c;
  }

  .module-hero {
    display: flex;
    flex-wrap: wrap;
    gap: clamp(22px, 4vw, 36px);
    align-items: center;
    margin-top: clamp(12px, 3vw, 24px);
  }

  .module-hero > div {
    flex: 1 1 320px;
    min-width: 0;
    display: flex;
  }

  .module-column {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: clamp(14px, 2vw, 22px);
    width: 100%;
  }

  .module-copy {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    gap: clamp(10px, 1.6vw, 18px);
  }

  .module-copy h1 {
    font-size: clamp(26px, 3vw, 34px);
    font-weight: 800;
    color: #0f172a;
    margin: 0;
  }

  .module-copy p {
    font-size: clamp(14px, 1.4vw, 16px);
    line-height: 1.45;
    color: #334155;
    margin: 0;
  }

  .module-list {
    margin: 0 0 0 clamp(16px, 2vw, 22px);
    padding: 0;
    list-style-position: inside;
    color: #0f172a;
    font-size: clamp(13px, 1.35vw, 15px);
    line-height: 1.4;
  }

  .module-list li {
    margin-bottom: clamp(4px, 1vw, 6px);
  }

  .module-list.two-columns {
    column-count: 2;
    column-gap: clamp(16px, 3vw, 28px);
  }

  .module-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: clamp(12px, 2.5vw, 18px);
  }

  .module-actions button[kind="primary"] {
    min-width: 200px;
  }

  .module-features {
    margin-top: clamp(12px, 2.5vw, 20px);
  }

  .module-features-title {
    font-weight: 700;
    color: #0f172a;
    margin: 0;
  }

  .module-cover {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .module-cover img {
    width: clamp(220px, 38vw, 420px);
    height: auto;
    max-height: 300px;
    border-radius: 18px;
    box-shadow: 0 18px 32px rgba(15, 23, 42, 0.16);
    object-fit: cover;
  }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

render_nav(active_top="inicio", active_child=None, show_inicio=False, show_cta=False)

# -------- Resolver imagen --------
APP_DIR = Path(__file__).resolve().parent
ASSET_DIRS = [
    APP_DIR / "assets",
    APP_DIR.parent / "assets",
    APP_DIR.parent / "static",
    Path.cwd() / "assets",
    Path.cwd() / "static",
    Path.cwd() / "COSTOS TRASLADOS APP" / "assets",
]
def resolve_asset(name: str):
    p = Path(name)
    if p.exists(): return p
    for d in ASSET_DIRS:
        q = d / Path(name).name
        if q.exists(): return q
    return None
def to_data_url(p: Path):
    try:
        mime = "image/png" if p.suffix.lower()==".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    except Exception:
        return None

# Use the project logo on the general home
img_path = (
    resolve_asset("assets/logo.jpg")
    or resolve_asset("logo.jpg")
)
img_data = to_data_url(img_path) if img_path else None

# -------- HERO unificado --------
with st.container():
    st.markdown('<div class="module-hero">', unsafe_allow_html=True)
    st.markdown('<div class="module-column">', unsafe_allow_html=True)
    st.markdown('<div class="module-copy">', unsafe_allow_html=True)
    st.markdown('<h1>Araiza Intelligence</h1>', unsafe_allow_html=True)
    st.markdown(
        """
        <p>
          Somos la unidad de anal&iacute;tica y automatizaci&oacute;n del Grupo Araiza. Transformamos datos operativos en decisiones estrat&eacute;gicas mediante herramientas inteligentes que integran geolocalizaci&oacute;n, modelos de costos y tableros ejecutivos.
        </p>
        <p>
          Con la Calculadora de Traslados estima en segundos el costo real de cada ruta y alinea a tus equipos de log&iacute;stica con tarifas transparentes y actualizadas.
        </p>
        <p>
          Complementa la operaci&oacute;n con m&oacute;dulos especializados de riesgo fiscal y paneles administrativos pensados para equipos directivos.
        </p>
        <div class="module-features">
          <p class="module-features-title">&iquest;Qu&eacute; hacemos?</p>
          <ul class="module-list two-columns">
            <li>Modelamos escenarios log&iacute;sticos con datos en tiempo real.</li>
            <li>Automatizamos c&aacute;lculos de costos y presupuestos de traslados.</li>
            <li>Monitoreamos alertas de riesgo fiscal y cumplimiento.</li>
            <li>Conectamos a tus equipos con indicadores accionables.</li>
            <li>Dise&ntilde;amos experiencias digitales centradas en la operaci&oacute;n.</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="module-cover">', unsafe_allow_html=True)
    if img_data:
        st.markdown(
            f"<img src='{img_data}' alt='Araiza Intelligence' />",
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

