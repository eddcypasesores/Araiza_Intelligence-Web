# pages/0_Inicio.py — Sticky navbar (1 fila), sin hueco, hero pegado y texto justificado
from pathlib import Path
import base64
import streamlit as st
from core.db import get_conn, ensure_schema

st.set_page_config(page_title="Inicio | Costos de Rutas", layout="wide")

# --- Seguridad ---
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

# --- DB ---
conn = get_conn(); ensure_schema(conn)

# --- Visual ---
HERO_MAX_WIDTH = 1100
HERO_HEIGHT    = 360
NAV_HEIGHT     = 56  # alto barra

# --- CSS ---
st.markdown(f"""
<style>
  :root {{
    --nav-h:{NAV_HEIGHT}px;
    --brand-red:#b91c1c; /* rojo para links */
  }}

  /* Quitar sidebar */
  [data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display:none !important; }}

  /* Contenedor principal: agregamos el offset de la barra sticky y eliminamos huecos */
  .block-container {{
    max-width:{HERO_MAX_WIDTH}px !important;
    margin:0 auto !important;
    padding-top:12px !important;        /* pequeño respiro superior */
    padding-bottom:0 !important;
  }}

  /* ===== NAVBAR STICKY =====
     El truco: creamos un 'sentinel' y hacemos sticky el contenedor que LO TIENE como hijo. */
  .block-container > div:has(> .nav-sentinel) {{
    position: sticky;
    top: 0;
    z-index: 999;
    background: #ffffffee;             /* leve transparencia con blur */
    backdrop-filter: saturate(180%) blur(8px);
    border-bottom:1px solid #e5e7eb;
    height: var(--nav-h);
    display:flex;
    align-items:center;
    padding:0 !important;
    margin:0 0 8px 0 !important;       /* nada de margen arriba, un respiro abajo */
  }}

  /* El bloque horizontal (columns) no debe añadir padding extra */
  .block-container > div:has(> .nav-sentinel) [data-testid="stHorizontalBlock"] > div {{
    padding:0 !important; margin:0 !important;
  }}

  /* Links del menú: rojo y sin recortes */
  .nav a, .nav [data-testid="stPageLink"] {{
    display:inline-block !important;
    font-size:15px; font-weight:700; color:var(--brand-red) !important;
    padding:10px 10px !important;
    line-height:22px !important;
    white-space:nowrap !important;
    text-decoration:none !important;
  }}
  .nav [data-testid="stPageLink"]:hover {{ text-decoration:underline !important; }}

  /* Botón de salir en rojo */
  .logout button {{
    background:transparent !important;
    border:1px solid var(--brand-red) !important;
    color:var(--brand-red) !important;
    padding:6px 12px !important;
    border-radius:8px !important;
    font-weight:700 !important;
  }}

  /* ===== HERO pegado a la barra (sin huecos arriba) ===== */
  .hero-wrap {{ margin-top:0 !important; }}
  .hero-grid {{
    display:grid; grid-template-columns:1fr 1fr; gap:20px; align-items:stretch;
  }}
  @media (max-width:980px) {{ .hero-grid {{ grid-template-columns:1fr; }} }}

  .img-cell, .text-cell {{ display:flex; align-items:center; justify-content:center; min-height:{HERO_HEIGHT}px; }}
  .hero-image {{ width:100%; height:{HERO_HEIGHT}px; object-fit:cover; border-radius:16px; box-shadow:0 6px 20px rgba(0,0,0,.08); }}

  .text-box {{ width:100%; display:flex; flex-direction:column; justify-content:center; gap:10px; }}
  .title {{ font-size:30px; font-weight:800; margin:0; letter-spacing:.2px; }}
  .lead {{ font-size:16px; color:#334155; margin:0; text-align:justify; }}
  .bullets {{ margin:8px 0 0 1.2rem; color:#0f172a; }}
  .bullets li {{ margin:6px 0; }}

  .cta-area {{ margin-top:12px; }}
  .cta-area button[kind="primary"] {{ font-size:18px !important; padding:10px 18px !important; border-radius:999px !important; }}
</style>
""", unsafe_allow_html=True)

# --- Resolver imagen ---
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

# === NAVBAR (solo Streamlit; el contenedor se vuelve sticky vía :has) ===
with st.container():
    # Este div marca el contenedor para que el CSS lo haga sticky
    st.markdown('<div class="nav-sentinel"></div>', unsafe_allow_html=True)

    # Estructura: spacer | 4 links | spacer | salir
    c0, c1, c2, c3, c4, c5, c6 = st.columns([1.2, 1, 1, 1, 1, 1.2, 0.9], gap="small")
    with c1: st.markdown('<div class="nav">', unsafe_allow_html=True); st.page_link("pages/2_Administrar_tarifas.py", label="Tarifas de Casetas ▾"); st.markdown('</div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="nav">', unsafe_allow_html=True); st.page_link("pages/4_Usuarios.py", label="Usuarios ▾"); st.markdown('</div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="nav">', unsafe_allow_html=True); st.page_link("pages/5_Parametros.py", label="Parámetros ▾"); st.markdown('</div>', unsafe_allow_html=True)
    with c4: st.markdown('<div class="nav">', unsafe_allow_html=True); st.page_link("pages/1_Calculadora.py", label="Calculadora"); st.markdown('</div>', unsafe_allow_html=True)
    with c6:
        st.markdown('<div class="logout" style="text-align:right;">', unsafe_allow_html=True)
        if st.button("Salir", key="logout_btn"):
            for k in ("usuario","rol","excluded_set","route","show_detail"):
                if k in st.session_state: del st.session_state[k]
            try: st.switch_page("app.py")
            except Exception: st.experimental_rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# === HERO (imagen izquierda | texto derecha) ===
st.markdown('<div class="hero-wrap"><div class="hero-grid">', unsafe_allow_html=True)
col_img, col_txt = st.columns(2, gap="large")

with col_img:
    st.markdown('<div class="img-cell">', unsafe_allow_html=True)
    if img_data:
        st.markdown(f"<img src='{img_data}' class='hero-image' alt='Transporte y rutas'/>", unsafe_allow_html=True)
    else:
        st.info("Falta la imagen en assets/inicio_card.png")
    st.markdown('</div>', unsafe_allow_html=True)

with col_txt:
    st.markdown('<div class="text-cell"><div class="text-box">', unsafe_allow_html=True)
    st.markdown('<div class="title">Tu ruta, nuestro compromiso.</div>', unsafe_allow_html=True)
    st.markdown("""
      <p class="lead">
      Somos una empresa mexicana dedicada al transporte de carga y logística de fletes, ofreciendo soluciones precisas, seguras y transparentes para mover mercancías en todo el país.
      </p>
      <p class="lead">
      Calculamos tus costos de traslado, optimizamos rutas y te ayudamos a tomar mejores decisiones con datos reales y actualizados.
      </p>
    """, unsafe_allow_html=True)
    st.markdown("""
      <ul class="bullets">
        <li>Cálculo de tarifas y peajes por tipo de camión.</li>
        <li>Estimaciones de combustible y costos operativos.</li>
        <li>Reportes detallados para clientes y transportistas.</li>
        <li>Transparencia total en cada viaje.</li>
      </ul>
    """, unsafe_allow_html=True)
    st.markdown('<div class="cta-area">', unsafe_allow_html=True)
    if st.button("Calcula tu Traslado", key="cta_calc", type="primary"):
        st.switch_page("pages/1_Calculadora.py")
    st.markdown('</div></div></div>', unsafe_allow_html=True)

st.markdown('</div></div>', unsafe_allow_html=True)
