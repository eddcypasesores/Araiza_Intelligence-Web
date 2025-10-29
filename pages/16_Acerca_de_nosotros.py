"""Sección informativa sobre Araiza Intelligence."""

from contextlib import closing
from pathlib import Path
import base64
import streamlit as st

from core.auth import ensure_session_from_token, persist_login
from core.db import authenticate_portal_user, ensure_schema, get_conn
from core.navigation import render_nav
from core.streamlit_compat import set_query_params

st.set_page_config(page_title="Acerca de Nosotros | Araiza Intelligence", layout="wide")

ensure_session_from_token()
render_nav(active_top="acerca", active_child=None)

st.markdown(
    """
    <style>
      .about-wrapper {
        display: grid;
        gap: clamp(20px, 4vw, 36px);
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        margin-top: clamp(24px, 5vw, 40px);
      }
      .about-card {
        border-radius: 18px;
        padding: clamp(18px, 3vw, 28px);
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        box-shadow: 0 18px 32px rgba(15, 23, 42, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.25);
      }
      .about-card h3 {
        margin-top: 0;
        font-size: clamp(20px, 2.2vw, 26px);
      }
      .about-card p {
        color: #334155;
        font-size: clamp(15px, 1.55vw, 17px);
        line-height: 1.55;
      }
      .about-hero {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        align-items: center;
        gap: clamp(24px, 5vw, 40px);
        margin-top: clamp(16px, 4vw, 32px);
      }
      .about-hero h1 {
        font-size: clamp(30px, 3.6vw, 44px);
        margin-bottom: 16px;
      }
      .about-hero p {
        font-size: clamp(16px, 1.6vw, 19px);
        line-height: 1.6;
        color: #1f2937;
      }
      .about-hero img {
        width: 100%;
        border-radius: 18px;
        object-fit: cover;
        box-shadow: 0 22px 38px rgba(15, 23, 42, 0.18);
        max-height: 420px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="about-hero">', unsafe_allow_html=True)

st.markdown('<div>', unsafe_allow_html=True)
st.markdown('<h1>Somos Araiza Intelligence</h1>', unsafe_allow_html=True)
st.markdown(
    """
    <p>
      Nacimos dentro del Grupo Araiza para transformar la operación logística en
      información procesable. Construimos modelos que unen datos de transporte,
      finanzas y cumplimiento regulatorio para anticipar decisiones clave.
    </p>
    <p>
      Nuestros equipos multidisciplinarios diseñan herramientas que integran
      algoritmos, experiencia de campo y visualizaciones ejecutivas para impulsar
      a las áreas de logística, finanzas y dirección.
    </p>
    """,
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

image_candidates = [
    Path("assets/about_cover.jpg"),
    Path("assets/about_cover.png"),
    Path(__file__).resolve().parent / "assets" / "about_cover.jpg",
    Path(__file__).resolve().parent / "assets" / "about_cover.png",
]
cover_data = None
for candidate in image_candidates:
    if candidate.exists():
        mime = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
        cover_data = f"data:{mime};base64," + base64.b64encode(candidate.read_bytes()).decode()
        break

if cover_data:
    st.markdown(f"<img src='{cover_data}' alt='Equipo Araiza Intelligence' />", unsafe_allow_html=True)
else:
    st.info("Agrega una imagen en assets/about_cover.jpg para complementar esta sección.")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="about-wrapper">', unsafe_allow_html=True)

st.markdown(
    """
    <div class="about-card">
      <h3>Visión</h3>
      <p>
        Convertir a Araiza Intelligence en el centro de inteligencia operativa
        del grupo, habilitando decisiones rápidas basadas en datos confiables y
        procesos automatizados.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="about-card">
      <h3>Capacidades</h3>
      <p>
        Especialistas en analítica de costos, automatización de reportes,
        integraciones con proveedores de datos (como Google Maps) y diseño de
        experiencias digitales para equipos internos.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="about-card">
      <h3>Alianzas</h3>
      <p>
        Colaboramos con áreas clave del grupo y aliados externos para mantener
        los modelos actualizados, garantizar el cumplimiento fiscal y asegurar
        la continuidad operativa de nuestras soluciones.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <p style="margin-top:32px; font-size:15px; color:#475569;">
      ¿Quieres saber más? Escríbenos a <strong>intelligence@grupoaraiza.mx</strong>.
    </p>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")
with st.expander("Administrar", expanded=False):
    st.caption(
        "Acceso reservado. Ingresa solo si administras los módulos y permisos del portal."
    )
    with st.form("super_admin_login", clear_on_submit=False):
        admin_rfc = st.text_input("RFC", placeholder="ej. ADMINISTRADOR")
        admin_password = st.text_input("Contraseña", type="password", placeholder="********")
        admin_submitted = st.form_submit_button("Iniciar sesión", use_container_width=True)

    st.caption(
        "¿Olvidaste tu contraseña? Solicita un enlace temporal y utiliza "
        "[esta página](?page=pages/18_Restablecer_contrasena.py) para restablecerla."
    )

    if admin_submitted:
        username = (admin_rfc or "").strip().upper()
        password = admin_password or ""

        if not username or not password:
            st.error("Captura RFC y contraseña para continuar.")
        else:
            try:
                with closing(get_conn()) as conn:
                    ensure_schema(conn)
                    record = authenticate_portal_user(conn, username, password)
            except Exception as exc:
                st.error("No fue posible validar las credenciales.")
                st.caption(f"Detalle técnico: {exc}")
                record = None

            permisos = set(record.get("permisos") or []) if record else set()
            if not record or "admin" not in permisos:
                st.error("Credenciales inválidas o sin privilegios de super administrador.")
            else:
                token = persist_login(
                    record["rfc"],
                    record["permisos"],
                    must_change_password=record.get("must_change_password", False),
                    user_id=record.get("id"),
                )
                try:
                    params = {k: v for k, v in st.query_params.items() if k != "auth"}
                    params["auth"] = token
                    set_query_params(params)
                except Exception:
                    pass
                st.success("Acceso concedido. Redirigiendo al panel de administración...")
                st.switch_page("pages/19_Admin_portal.py")
