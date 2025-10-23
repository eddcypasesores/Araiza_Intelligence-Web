# pages/0_Inicio.py — Navbar horizontal sticky + hero sin huecos (misma altura)
from pathlib import Path
from string import Template
import base64
import streamlit as st
from core.db import get_conn, ensure_schema

st.set_page_config(page_title="Inicio | Costos de Rutas", layout="wide")

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

# -------- Parámetros visuales --------
MAX_W        = 1100
NAV_H        = 64
HERO_H       = 420  # MISMA altura para imagen y texto

# -------- CSS --------
css_template = Template(
    """
<style>
  :root {
    --maxw: ${max_w}px;
    --navh: ${nav_h}px;
    --brand-red: #dc2626;
    --brand-red-dark: #b91c1c;
  }

  /* Ocultar elementos nativos de Streamlit que compiten con la barra */
  [data-testid="stSidebar"],
  [data-testid="collapsedControl"] {
    display: none !important;
  }
  header[data-testid="stHeader"],
  div[data-testid="stToolbar"],
  #MainMenu {
    display: none !important;
  }

  [data-testid="stAppViewContainer"] > .main {
    padding-top: 0 !important;
  }

  .block-container {
    max-width: var(--maxw) !important;
    margin: 0 auto !important;
    padding: calc(var(--navh) + 24px) clamp(16px, 4vw, 32px) clamp(48px, 8vw, 72px) !important;
  }

  /* ===== NAVBAR FIJA ===== */
  .nav-sentinel {
    display: none;
  }

  .nav-anchor {
    display: block;
  }

  .nav-anchor + div[data-testid="stHorizontalBlock"] {
    position: fixed;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: min(100%, var(--maxw));
    z-index: 1000;
    background: #fff;
    border-bottom: 1px solid #e5e7eb;
    display: flex !important;
    align-items: center;
    gap: clamp(12px, 2.5vw, 32px);
    padding: 0 clamp(16px, 4vw, 24px) !important;
    height: var(--navh);
  }

  .nav-anchor + div[data-testid="stHorizontalBlock"] > div {
    padding: 0 !important;
    margin: 0 !important;
    flex: 0 0 auto !important;
    width: auto !important;
  }

  .nav-anchor + div[data-testid="stHorizontalBlock"] > div:last-child {
    margin-left: auto !important;
  }

  .nav-scope {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
  }

  .nav-scope [data-testid="stPageLink"] {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    color: var(--brand-red) !important;
    font-weight: 700;
    font-size: clamp(15px, 1.7vw, 18px);
    padding: 10px 14px !important;
    white-space: nowrap !important;
    line-height: 24px !important;
    text-decoration: none !important;
  }

  .nav-scope [data-testid="stPageLink"]:hover {
    color: var(--brand-red-dark) !important;
    text-decoration: underline !important;
  }

  .nav-scope.logout {
    justify-content: flex-end;
  }

  .nav-scope.logout button {
    background: var(--brand-red) !important;
    color: #fff !important;
    border: 1px solid var(--brand-red) !important;
    padding: 10px 18px !important;
    border-radius: 999px !important;
    font-weight: 800 !important;
    font-size: clamp(14px, 1.6vw, 17px) !important;
  }

  .nav-scope.logout button:hover {
    background: var(--brand-red-dark) !important;
    border-color: var(--brand-red-dark) !important;
  }

  /* ===== HERO ===== */
  .hero-sentinel {
    display: none;
  }

  .hero-anchor + div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-wrap: wrap;
    gap: clamp(28px, 5vw, 48px);
    margin: 0 !important;
    padding: 0 !important;
  }

  .hero-anchor + div[data-testid="stHorizontalBlock"] > div {
    flex: 1 1 360px !important;
    padding: 0 !important;
    margin: 0 !important;
    min-width: 0;
  }

  .hero-anchor + div[data-testid="stHorizontalBlock"] > div > div:first-child {
    height: 100%;
  }

  .hero-img-wrap,
  .hero-text-wrap {
    height: 100%;
    min-height: ${hero_h}px;
    display: flex;
    flex-direction: column;
  }

  .hero-img-wrap {
    overflow: hidden;
    border-radius: 18px;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  }

  .hero-image {
    width: 100%;
    height: 100%;
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
    gap: clamp(14px, 2.5vw, 22px);
  }

  .text-box .copy {
    display: flex;
    flex-direction: column;
    gap: clamp(10px, 2vw, 16px);
    flex: 1;
  }

  .title {
    font-size: clamp(28px, 3.2vw, 42px);
    font-weight: 800;
    margin: 0;
    letter-spacing: 0.3px;
  }

  .lead {
    font-size: clamp(15px, 1.55vw, 18px);
    color: #334155;
    margin: 0;
    line-height: 1.7;
    text-align: justify;
  }

  .bullets {
    margin: 4px 0 0 clamp(18px, 2vw, 24px);
    color: #0f172a;
    font-size: clamp(14px, 1.4vw, 17px);
  }

  .bullets li {
    margin-bottom: clamp(6px, 1.6vw, 12px);
  }

  .cta-area {
    margin-top: auto;
    padding-top: clamp(12px, 2vw, 20px);
    display: flex;
    justify-content: flex-start;
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

  @media (max-width: 1024px) {
    .hero-img-wrap,
    .hero-text-wrap {
      min-height: auto;
    }
  }

  @media (max-width: 780px) {
    .nav-anchor + div[data-testid="stHorizontalBlock"] {
      gap: clamp(8px, 3vw, 16px);
    }

    .hero-anchor + div[data-testid="stHorizontalBlock"] {
      flex-direction: column;
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

  @media (max-width: 520px) {
    .block-container {
      padding: calc(var(--navh) + 20px) clamp(14px, 5vw, 18px) clamp(40px, 12vw, 60px) !important;
    }

    .nav-anchor + div[data-testid="stHorizontalBlock"] {
      flex-wrap: wrap;
      justify-content: center;
      row-gap: 8px;
      height: auto;
      padding: clamp(10px, 4vw, 16px) clamp(16px, 6vw, 24px) !important;
    }

    .nav-anchor + div[data-testid="stHorizontalBlock"] > div:last-child {
      margin-left: 0 !important;
      width: 100% !important;
      display: flex;
      justify-content: center;
    }

    .nav-scope.logout {
      justify-content: center;
    }

    .nav-scope.logout button {
      width: min(220px, 100%);
    }

    .cta-area {
      padding-top: clamp(18px, 4vw, 28px);
    }
  }
</style>
"""
)

st.markdown(
    css_template.substitute(max_w=MAX_W, nav_h=NAV_H, hero_h=HERO_H),
    unsafe_allow_html=True,
)

# -------- NAVBAR (1 sola fila con columns) --------
with st.container():
    st.markdown('<div class="nav-anchor"></div>', unsafe_allow_html=True)

    col_tarifas, col_usuarios, col_parametros, col_logout = st.columns(4, gap="small")

    with col_tarifas:
        st.markdown('<div class="nav-scope">', unsafe_allow_html=True)
        st.page_link("pages/2_Administrar_tarifas.py", label="Tarifas")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_usuarios:
        st.markdown('<div class="nav-scope">', unsafe_allow_html=True)
        st.page_link("pages/4_Usuarios.py", label="Usuarios")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_parametros:
        st.markdown('<div class="nav-scope">', unsafe_allow_html=True)
        st.page_link("pages/5_Parametros.py", label="Parámetros")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_logout:
        st.markdown('<div class="nav-scope logout">', unsafe_allow_html=True)
        if st.button("Salir", key="logout_btn"):
            for k in ("usuario", "rol", "excluded_set", "route", "show_detail"):
                if k in st.session_state:
                    del st.session_state[k]
            try:
                st.switch_page("app.py")
            except Exception:
                st.experimental_rerun()
        st.markdown('</div>', unsafe_allow_html=True)

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
            st.markdown(
                f"<img src='{img_data}' class='hero-image' alt='Transporte y rutas' />",
                unsafe_allow_html=True,
            )
        else:
            st.info("Falta la imagen en assets/inicio_card.png")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_txt:
        st.markdown('<div class="hero-text-wrap"><div class="text-box">', unsafe_allow_html=True)
        st.markdown('<div class="title">Tu ruta, nuestro compromiso.</div>', unsafe_allow_html=True)
        st.markdown('<div class="copy">', unsafe_allow_html=True)
        st.markdown(
            """
          <p class="lead">
          Somos una empresa mexicana dedicada al transporte de carga y logística de fletes, ofreciendo soluciones precisas, seguras
    y transparentes para mover mercancías en todo el país.
          </p>
          <p class="lead">
          Nuestra plataforma integra tecnología de Google Maps (Places, Directions y Geocoding APIs), bases de datos inteligentes y
    cálculos automatizados para ofrecerte resultados precisos y en tiempo real.
          </p>
          <p class="lead">
          Calculamos tus costos de traslado, optimizamos rutas y te ayudamos a tomar mejores decisiones con datos reales y actualizados.
          </p>
        """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
          <p class="lead" style="font-weight:700; margin-top: 8px;">Características principales:</p>
          <ul class="bullets">
            <li>Cálculo automático de rutas, distancias y casetas.</li>
            <li>Estimaciones de combustible y costos operativos detallados.</li>
            <li>Reportes profesionales para clientes y transportistas.</li>
            <li>Transparencia total y datos actualizados en cada viaje.</li>
          </ul>
        """,
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="cta-area">', unsafe_allow_html=True)
        if st.button("Calcular ruta", key="cta_calc", type="primary"):
            st.switch_page("pages/1_Calculadora.py")
        st.markdown('</div></div></div>', unsafe_allow_html=True)
