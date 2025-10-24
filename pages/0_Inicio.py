# pages/0_Inicio.py — Inicio con héroe centrado y navegación compartida
from pathlib import Path
import base64
import streamlit as st

from core.auth import ensure_session_from_token
from core.db import get_conn, ensure_schema
from core.navigation import render_nav

st.set_page_config(page_title="Inicio | Costos de Rutas", layout="wide")

ensure_session_from_token()

# -------- Seguridad --------
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

# -------- DB --------
conn = get_conn(); ensure_schema(conn)

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

  .cta-area {
    margin-top: auto;
    padding-top: 0px;
    display: flex;
    justify-content: flex-end;
    padding-bottom: 0;
  }

  .cta-area button[kind="primary"] {
    font-size: clamp(16px, 1.8vw, 20px) !important;
    padding: clamp(10px, 1.6vw, 16px) clamp(22px, 4vw, 36px) !important;
    border-radius: 999px !important;
    background: var(--brand-red) !important;
    border-color: var(--brand-red) !important;
  }

  .cta-area button[kind="primary"]:hover {
    background: var(--brand-red-dark) !important;
    border-color: var(--brand-red-dark) !important;
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

    .cta-area {
      justify-content: center;
    }
  }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

render_nav(active_top="inicio", active_child=None, show_inicio=False)

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

img_path = resolve_asset("assets/inicio_card.png") or resolve_asset("inicio_card.png")
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
            st.info("Falta la imagen en assets/inicio_card.png")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_txt:
        # El texto define la altura. La imagen se estira para igualarla.
        st.markdown(
            '<div class="hero-text-wrap"><div class="text-box"><div class="headline-stack">',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="title">Precisión en movimiento</div>', unsafe_allow_html=True)
        st.markdown('<div class="copy">', unsafe_allow_html=True)
        st.markdown(
            """
          <p class="lead">
          Nuestra plataforma calcula con exactitud los costos reales de cada flete, integrando tecnología avanzada, APIs de Google Maps y bases de datos inteligentes para ofrecer resultados precisos y actualizados en tiempo real.
          </p>
          <p class="lead">
          Obtén en segundos el costo total de una ruta — peajes, combustible, mantenimiento y demás gastos operativos — con una interfaz ágil, intuitiva y confiable.
          </p>
          <p class="lead">
          Además, administra fácilmente usuarios y trabajadores, garantizando control, trazabilidad y eficiencia en cada viaje.
          </p>
        """,
            unsafe_allow_html=True,
        )
        st.markdown('</div></div>', unsafe_allow_html=True)
        st.markdown(
            """
          <div class="features">
            <p class="lead features-title">Características principales:</p>
            <ul class="bullets">
              <li>Cálculo automático de rutas, distancias y casetas.</li>
              <li>Estimación real de combustible y costos operativos.</li>
              <li>Gestión integrada de usuarios y trabajadores.</li>
              <li>Reportes claros y listos para la toma de decisiones.</li>
              <li>Transparencia y precisión en cada operación.</li>
            </ul>
          </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="cta-area">', unsafe_allow_html=True)
        if st.button("Calcular ruta", key="cta_calc", type="primary"):
            st.switch_page("pages/1_Calculadora.py")
        st.markdown('</div></div></div>', unsafe_allow_html=True)