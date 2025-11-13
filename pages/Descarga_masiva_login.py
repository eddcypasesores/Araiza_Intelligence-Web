# pages/Descarga_masiva_login.py — Login unificado para "Descarga masiva de XML"
from __future__ import annotations

import streamlit as st

from core.theme import apply_theme
# Núcleo (tus módulos reales)
from core.auth import ensure_session_from_token, persist_login
from core.db import get_conn, authenticate_portal_user
from core.login_ui import render_login_header, render_token_reset_section

# -----------------------------------------------------------------------------
# Configuración base
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Descarga masiva de XML — Acceso",
    page_icon="📥",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()

# -----------------------------------------------------------------------------
# Estilos mínimos coherentes (opcional)
# -----------------------------------------------------------------------------
LOGIN_CSS = """
<style>
  :root{
    --brand: #0f172a;
    --muted: #64748b;
  }
  .login-wrap {
    max-width: 720px;
    margin: 1.5rem auto 3rem auto;
    padding: 0 .5rem;
  }
  .login-card {
    background: #fff;
    border: 1px solid rgba(2,6,23,0.06);
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 8px 22px rgba(2,6,23,0.06);
  }
  .field-note {
    color: var(--muted);
    font-size: .85rem;
    margin-top: -6px;
    margin-bottom: 10px;
  }
</style>
"""
st.markdown(LOGIN_CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Helpers locales de query params (compatibles nuevas/viejas versiones)
# -----------------------------------------------------------------------------
def _get_params() -> dict[str, str]:
    try:
        return dict(st.query_params)  # type: ignore[attr-defined]
    except Exception:
        q = st.experimental_get_query_params()  # type: ignore[attr-defined]
        return {k: (v[-1] if isinstance(v, list) and v else v) for k, v in q.items()}

def _set_params(**kwargs) -> None:
    try:
        st.query_params.update(kwargs)  # type: ignore[attr-defined]
    except Exception:
        merged = _get_params()
        merged.update({k: str(v) for k, v in kwargs.items()})
        st.experimental_set_query_params(**merged)  # type: ignore[attr-defined]

def _clear_params() -> None:
    try:
        st.query_params.clear()  # type: ignore[attr-defined]
    except Exception:
        st.experimental_set_query_params()  # type: ignore[attr-defined]

# -----------------------------------------------------------------------------
# Sesión + parámetros
# -----------------------------------------------------------------------------
ensure_session_from_token()
conn = get_conn()

params = _get_params()
NEXT_DEFAULT = "pages/Descarga_masiva_inicio.py"
next_target = params.get("next") or NEXT_DEFAULT

def go_to_target():
    try:
        st.switch_page(next_target)
    except Exception:
        try:
            st.switch_page(NEXT_DEFAULT)
        except Exception:
            st.stop()

# -----------------------------------------------------------------------------
# Cabecera visual estándar
# -----------------------------------------------------------------------------
render_login_header(
    "Descarga masiva de XML",
    subtitle="Acceso seguro para indexar, consultar y administrar grandes volúmenes de CFDI.",
)

# -----------------------------------------------------------------------------
# Tarjeta de formulario
# -----------------------------------------------------------------------------
st.markdown('<div class="login-wrap"><div class="login-card">', unsafe_allow_html=True)

with st.form("frm_login_xml", clear_on_submit=False):
    rfc = st.text_input("RFC", placeholder="ABCD800101XXX").strip().upper()
    st.markdown('<div class="field-note">Usa el RFC con el que te registraron.</div>', unsafe_allow_html=True)
    password = st.text_input("Contraseña", type="password", placeholder="••••••••")

    c1, c2 = st.columns(2)
    login_click = c1.form_submit_button("Iniciar sesión", type="primary", use_container_width=True)
    cancel_click = c2.form_submit_button("Cancelar", use_container_width=True)

# Bloque estándar de “Olvidé mi contraseña” (según tu firma actual)
if render_token_reset_section("xml_login"):
    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

# -----------------------------------------------------------------------------
# Acciones
# -----------------------------------------------------------------------------
if cancel_click:
    try:
        _clear_params()
    except Exception:
        pass
    try:
        st.switch_page("pages/0_Inicio.py")
    except Exception:
        st.stop()

if login_click:
    if not rfc or not password:
        st.error("Ingresa tu RFC y tu contraseña.")
    else:
        user = authenticate_portal_user(conn, rfc, password)
        if not user:
            st.error("RFC o contraseña incorrectos.")
        else:
            # Permisos asignados para este producto (ajusta si manejas roles distintos)
            granted = ["descarga_masiva"]

            # Persistencia con tu core.auth.persist_login (firma real)
            token = persist_login(
                username=user.get("rfc", rfc),
                permisos_or_rol=granted,   # o usa un rol como "admin"
                user_id=user.get("id"),
            )

            _set_params(auth=token, next=next_target)
            st.success("¡Bienvenido! Redirigiendo…")
            go_to_target()

st.markdown("</div></div>", unsafe_allow_html=True)
