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
NAV_H        = 60
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

  /* Contenedor principal centrado y sin huecos extra */
  .block-container {
    max-width: var(--maxw) !important;
    margin: 0 auto !important;
    padding: 0 !important;
  }

  /* ===== NAVBAR STICKY (sin huecos) =====
     Hacemos sticky el contenedor que contiene la 'nav-sentinel' + columns. */
  .block-container > div:has(> .nav-sentinel) {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: #fff;
    border-bottom: 1px solid #e5e7eb;
    height: var(--navh);
    display: flex;
    align-items: center;
    margin: 0 !important;
    padding: 0 !important;
  }
  /* Quitamos padding/margins propios del bloque de columnas */
  .block-container > div:has(> .nav-sentinel) [data-testid="stHorizontalBlock"] > div {
    padding: 0 !important;
    margin: 0 !important;
  }

  /* Enlaces del menú: tipografía roja, una línea, separados */
  .nav-scope [data-testid="stPageLink"] {
    display: inline-block !important;
    color: var(--brand-red) !important;
    font-weight: 700;
    font-size: 18px;
    padding: 10px 14px !important;
    white-space: nowrap !important;
    line-height: 24px !important;
    text-decoration: none !important;
  }
  .nav-scope [data-testid="stPageLink"]:hover {
    color: var(--brand-red-dark) !important;
    text-decoration: underline !important;
  }

  /* Botón SALIR rojo */
  .nav-scope .logout button {
    background: var(--brand-red) !important;
    color: #fff !important;
    border: 1px solid var(--brand-red) !important;
    padding: 10px 16px !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
  }
  .nav-scope .logout button:hover {
    background: var(--brand-red-dark) !important;
    border-color: var(--brand-red-dark) !important;
  }

  /* ===== HERO (pegado a la barra, sin huecos, columnas igual altura) ===== */
  .block-container > div:has(> .hero-sentinel) {
    margin: 0 !important;
    padding: 8px 0 0 !important;
  }

  .block-container > div:has(> .hero-sentinel) [data-testid="column"] > div:first-child {
    height: 100%;
  }

  .hero-img-wrap,
  .hero-text-wrap {
    height: 100%;
    min-height: ${hero_h}px;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    align-items: stretch;
  }

  .hero-img-wrap {
    overflow: hidden;
    border-radius: 16px;
  }

  .hero-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 16px;
    box-shadow: 0 6px 20px rgba(0,0,0,.08);
  }

  .text-box {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .text-box .copy {
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
  }

  .title { font-size: 32px; font-weight: 800; margin: 0; letter-spacing: .2px; }
  .lead  { font-size: 16px; color: #334155; margin: 0; text-align: justify; }
  .bullets { margin: 8px 0 0 1.2rem; color: #0f172a; }
  .bullets li { margin: 6px 0; }

  .cta-area { margin-top: auto; padding-top: 16px; }
  .cta-area button[kind="primary"] {
    font-size: 18px !important;
    padding: 10px 20px !important;
    border-radius: 999px !important;
    background: var(--brand-red) !important;
    border-color: var(--brand-red) !important;
  }
  .cta-area button[kind="primary"]:hover {
    background: var(--brand-red-dark) !important;
    border-color: var(--brand-red-dark) !important;
  }

  @media (max-width: 980px) {
    .hero-img-wrap,
    .hero-text-wrap {
      min-height: auto;
    }

    .hero-img-wrap {
      margin-bottom: 24px;
    }

    .cta-area {
      margin-top: 16px;
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
    st.markdown('<div class="nav-sentinel"></div>', unsafe_allow_html=True)

    #   [esp] [Tarifas] [Usuarios] [Parámetros] [Salir]
    c0, c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1, 0.9], gap="small")

    with c1:
        st.markdown('<div class="nav-scope">', unsafe_allow_html=True)
        st.page_link("pages/2_Administrar_tarifas.py", label="Tarifas")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="nav-scope">', unsafe_allow_html=True)
        st.page_link("pages/4_Usuarios.py", label="Usuarios")
        st.markdown('</div>', unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="nav-scope">', unsafe_allow_html=True)
        st.page_link("pages/5_Parametros.py", label="Parámetros")
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="nav-scope logout" style="text-align:right;">', unsafe_allow_html=True)
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
    st.markdown('<div class="hero-sentinel"></div>', unsafe_allow_html=True)
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
