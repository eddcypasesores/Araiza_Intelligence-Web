# app.py  (Login | Calculadora de Ruta)
import base64
from pathlib import Path
import streamlit as st
from core.db import get_conn, ensure_schema, validar_usuario
from core.navigation import PAGE_PARAM_NAMES

# -------------------------------
# Configuración de página (login)
# -------------------------------
st.set_page_config(page_title="Login | Calculadora de Ruta", layout="centered")

# Oculta sidebar y ajusta estilo general
st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { display: none !important; }
      [data-testid="collapsedControl"] { display: none !important; }

      /* Contenedor principal centrado */
      .main > div {
          max-width: 480px;
          margin: 10vh auto;
      }

      /* Bloque combinado de texto + logo */
      .login-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          width: 100%;
          margin-bottom: 30px;
      }

      .login-text { flex: 1; }
      .login-text h1 { font-size: 1.8em; margin-bottom: 0.2em; }
      .login-text p  { font-size: 1.05em; color: #555; margin-top: 0; }

      .login-logo { flex-shrink: 0; text-align: right; }
      .login-logo img {
          border-radius: 10px;
          width: 130px; /* tamaño del logo */
          box-shadow: 0 2px 10px rgba(0,0,0,.06);
      }

      .block-container { padding-left: 2rem !important; padding-right: 2rem !important; }

      @media (max-width: 600px) {
          .login-header { flex-direction: column; align-items: center; text-align: center; }
          .login-logo img { width: 150px; }
      }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------
# Inicializa BD / esquema
# -------------------------------
conn = get_conn()
ensure_schema(conn)

# -------------------------------
# Si ya hay sesión iniciada -> manda a Inicio
# -------------------------------
PAGE_PARAM_TO_SCRIPT = {label: script for script, label in PAGE_PARAM_NAMES.items()}


def _requested_page() -> str | None:
    """Return the script path requested through the ``page`` query parameter."""

    params = st.query_params
    raw_page = params.get("page")
    if isinstance(raw_page, list):
        candidate = raw_page[-1] if raw_page else None
    else:
        candidate = raw_page
    if not candidate:
        return None
    return PAGE_PARAM_TO_SCRIPT.get(candidate)


if "usuario" in st.session_state and "rol" in st.session_state:
    target_script = _requested_page() or "pages/0_Inicio.py"
    try:
        st.switch_page(target_script)
    except Exception:
        st.success(
            f"Ya has iniciado sesión como: {st.session_state['usuario']} ({st.session_state['rol']})."
        )
        st.info("Utiliza el menú de navegación para continuar.")
    st.stop()

# -------------------------------
# Helper para resolver el logo
# -------------------------------
APP_DIR = Path(__file__).resolve().parent
# Prioridades de búsqueda: /pages/assets, /assets en raíz, mismo directorio
ASSET_CANDIDATES = [
    APP_DIR / "assets" / "logo.jpg",
    APP_DIR.parent / "assets" / "logo.jpg",
    APP_DIR / "logo.jpg",
]

def load_logo_b64() -> str | None:
    for p in ASSET_CANDIDATES:
        if p.exists():
            data = p.read_bytes()
            return base64.b64encode(data).decode("utf-8")
    return None

logo_b64 = load_logo_b64()
logo_html = (
    f'<img src="data:image/jpeg;base64,{logo_b64}" alt="Logo de la empresa">'
    if logo_b64 else
    "<div style='color:#c00;font-size:13px'>[Logo no encontrado]</div>"
)

# -------------------------------
# Cabecera: texto + logo
# -------------------------------
st.markdown(
    f"""
    <div class="login-header">
        <div class="login-text">
            <h1>Iniciar sesión</h1>
            <p>Ingresa tus credenciales para continuar.</p>
        </div>
        <div class="login-logo">
            {logo_html}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------
# Formulario de Login
# -------------------------------
with st.form("login_form", clear_on_submit=False):
    username = st.text_input("Usuario", placeholder="ej. admin")
    password = st.text_input("Contraseña", type="password", placeholder="••••••••")
    submitted = st.form_submit_button("Entrar", use_container_width=True)

if submitted:
    try:
        rol = validar_usuario(conn, username.strip(), password)
    except Exception as e:
        st.error("Error al validar credenciales. Revisa la conexión a la base de datos o el esquema.")
        st.caption(f"Detalle técnico: {e}")
        st.stop()

    if rol:
        st.session_state["usuario"] = username.strip()
        st.session_state["rol"] = rol
        st.success(f"Bienvenido, {st.session_state['usuario']} ({rol}).")
        try:
            st.switch_page("pages/0_Inicio.py")
        except Exception:
            st.info("Ve a **Inicio** desde el menú lateral.")
            st.experimental_rerun()
    else:
        st.error("Usuario o contraseña incorrectos.")
