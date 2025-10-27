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

  .hero-anchor + div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-wrap: wrap;
    gap: clamp(28px, 5vw, 48px);
    margin: 0 !important;
    padding: 0 !important;
    align-items: center;
  }

  .hero-anchor + div[data-testid="stHorizontalBlock"] > div {
    flex: 1 1 360px !important;
    padding: 0 !important;
    margin: 0 !important;
    min-width: 0;
    display: flex;
    align-items: center;
    height: 100%;
  }

  .hero-anchor + div[data-testid="stHorizontalBlock"] > div > div:first-child {
    height: 100%;
    width: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .hero-img-wrap,
  .hero-text-wrap {
    height: 100%;
    width: 100%;
    display: flex;
    flex-direction: column;
  }

  .hero-img-wrap > div,
  .hero-img-wrap > div > div,
  .hero-img-wrap > div > div > div {
    flex: 1 1 0%;
    height: 100%;
    min-height: 0;
  }

  .hero-img-wrap {
    overflow: hidden;
    border-radius: 18px;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  }

  .hero-img-wrap > div > div > div > img {
    height: 100%;
    width: 100%;
    object-fit: cover;
  }

  .hero-text-wrap {
    padding: clamp(4px, 1vw, 12px) clamp(4px, 1vw, 12px);
  }

  .text-box {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: clamp(18px, 2.6vw, 28px);
  }

  .headline-stack {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .headline-stack .copy {
    margin-top: 0;
    display: flex;
    flex-direction: column;
    gap: clamp(8px, 1.5vw, 12px);
  }

  .headline-stack .copy .lead {
    margin: 0;
  }

  .features {
    display: flex;
    flex-direction: column;
    gap: clamp(8px, 1.6vw, 14px);
  }

  .features .features-title {
    font-weight: 700;
    margin: 0;
  }

  .title {
    font-size: clamp(24px, 2.8vw, 36px);
    font-weight: 800;
    margin: 0;
    letter-spacing: 0.3px;
    white-space: nowrap;
  }

  .lead {
    font-size: clamp(15px, 1.55vw, 18px);
    color: #334155;
    margin: 0;
    line-height: 1.5;
    text-align: justify;
  }

  .bullets {
    margin: 2px 0 0 clamp(18px, 2vw, 24px);
    color: #0f172a;
    font-size: clamp(14px, 1.4vw, 17px);
  }

  .bullets li {
    margin-bottom: clamp(2px, 0.8vw, 4px);
    line-height: 1.3;
  }

  @media (max-width: 780px) {
    .title {
      white-space: normal;
    }

    .hero-anchor + div[data-testid="stHorizontalBlock"] {
      flex-direction: column;
      align-items: stretch;
    }

    .hero-img-wrap {
      min-height: 260px;
    }

    .hero-text-wrap {
      padding: clamp(12px, 4vw, 20px) 0;
    }

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

img_path = (
    resolve_asset("assets/Inicio_card.png")
    or resolve_asset("Inicio_card.png")
    or resolve_asset("assets/inicio_card.png")
    or resolve_asset("inicio_card.png")
)
img_data = to_data_url(img_path) if img_path else None

# -------- HERO (imagen izquierda | texto derecha, MISMA altura) --------
with st.container():
    st.markdown('<div class="hero-anchor"></div>', unsafe_allow_html=True)
    col_img, col_txt = st.columns(2, gap="large")

    with col_img:
        st.markdown('<div class="hero-img-wrap">', unsafe_allow_html=True)
        if img_data:
            # Aquí inyectamos la imagen con la clase hero-image
            st.markdown(
                f"<img src='{img_data}' class='hero-image' alt='Transporte y rutas' />",
                unsafe_allow_html=True,
            )
        else:
            st.info("Falta la imagen en assets/Inicio_card.png")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_txt:
        # El texto define la altura. La imagen se estira para igualarla.
        st.markdown(
            '<div class="hero-text-wrap"><div class="text-box"><div class="headline-stack">',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="title">Araiza Intelligence</div>', unsafe_allow_html=True)
        st.markdown('<div class="copy">', unsafe_allow_html=True)
        st.markdown(
            """
          <p class="lead">
          Somos la unidad de analítica y automatización del Grupo Araiza. Transformamos datos operativos en decisiones estratégicas mediante herramientas inteligentes que integran geolocalización, modelos de costos y tableros ejecutivos.
          </p>
          <p class="lead">
          Con la Calculadora de Traslados estima en segundos el costo real de cada ruta y alinea a tus equipos de logística con tarifas transparentes y actualizadas.
          </p>
          <p class="lead">
          Complementa la operación con módulos especializados de riesgo fiscal y paneles administrativos pensados para equipos directivos.
          </p>
        """,
            unsafe_allow_html=True,
        )
        st.markdown('</div></div>', unsafe_allow_html=True)
        st.markdown(
            """
          <div class="features">
            <p class="lead features-title">¿Qué hacemos?</p>
            <ul class="bullets">
              <li>Modelamos escenarios logísticos con datos en tiempo real.</li>
              <li>Automatizamos cálculos de costos y presupuestos de traslados.</li>
              <li>Monitoreamos alertas de riesgo fiscal y cumplimiento.</li>
              <li>Conectamos a tus equipos con indicadores accionables.</li>
              <li>Diseñamos experiencias digitales centradas en la operación.</li>
            </ul>
          </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown('</div></div></div>', unsafe_allow_html=True)

