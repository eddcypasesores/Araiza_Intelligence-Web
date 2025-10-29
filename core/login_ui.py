"""Shared helpers to render the new unified login layout."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st

from .db import ensure_schema, get_conn, portal_consume_reset_token, portal_get_reset_token

_DEFAULT_LOGO = Path("assets/logo.jpg")
_CSS_KEY = "_login_theme_injected"

_LOGIN_CSS = """
<style>
  [data-testid="stSidebar"],
  [data-testid="collapsedControl"],
  header[data-testid="stHeader"],
  div[data-testid="stToolbar"],
  #MainMenu {
    display: none !important;
  }

  [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #eef2ff, #f8fafc);
  }

  [data-testid="stAppViewContainer"] > .main {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
  }

  .block-container {
    max-width: 420px !important;
    width: 100% !important;
    padding: 48px 36px 40px !important;
    background: #ffffff;
    border-radius: 24px;
    box-shadow: 0 28px 48px rgba(15, 23, 42, 0.18);
  }

  .auth-logo {
    text-align: center;
    margin-bottom: 1.5rem;
  }

  .auth-title {
    text-align: center;
    font-size: 1.65rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.5rem;
  }

  .auth-subtitle {
    text-align: center;
    color: #475569;
    font-size: 1rem;
    line-height: 1.5;
    margin-bottom: 1.5rem;
  }

  .auth-actions {
    display: flex;
    gap: 12px;
    margin-top: 1.2rem;
  }

  .auth-actions > div {
    padding: 0 !important;
  }

  .auth-actions button {
    height: 44px;
    border-radius: 12px !important;
    font-weight: 600 !important;
  }

  .auth-links {
    text-align: center;
    margin-top: 1.25rem;
    font-size: 0.95rem;
  }

  .auth-links a {
    color: #2563eb;
    text-decoration: none;
    font-weight: 600;
  }

  .auth-links a:hover {
    text-decoration: underline;
  }

  .auth-links .stButton>button {
    background: none !important;
    border: none !important;
    color: #2563eb !important;
    padding: 0 !important;
    font-weight: 600 !important;
    text-decoration: underline !important;
    cursor: pointer !important;
    min-height: auto !important;
  }

  .auth-links .stButton>button:hover {
    color: #1d4ed8 !important;
    background: none !important;
  }

  .auth-section {
    margin-top: 1.25rem;
  }

  .auth-section .stTextInput > div > div > input,
  .auth-section .stPassword > div > div > input {
    border-radius: 12px;
  }
</style>
"""


def _inject_login_css() -> None:
    """Ensure the shared login CSS is loaded once per run."""

    if st.session_state.get(_CSS_KEY):
        return
    st.session_state[_CSS_KEY] = True
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)


def _logo_data_uri(path: Path) -> str | None:
    """Return a base64 data URI for the provided logo path."""

    if not path.exists():
        return None
    try:
        mime = "png" if path.suffix.lower() == ".png" else "jpeg"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/{mime};base64,{data}"
    except Exception:
        return None


def render_login_header(
    title: str,
    *,
    subtitle: str | None = None,
    logo_path: str | Path | None = _DEFAULT_LOGO,
) -> None:
    """Render the standard login header block with optional subtitle."""

    _inject_login_css()

    logo_uri: str | None = None
    logo_str: str | None = None
    if logo_path is not None:
        path = Path(logo_path)
        logo_uri = _logo_data_uri(path)
        if not logo_uri and path.exists():
            logo_str = str(path)

    if logo_uri:
        st.markdown(
            f'<div class="auth-logo"><img src="{logo_uri}" alt="Araiza Intelligence logo" width="160"/></div>',
            unsafe_allow_html=True,
        )
    elif logo_str:
        st.image(logo_str, width=160)

    safe_title = html.escape(title or "")
    st.markdown(f'<div class="auth-title">{safe_title}</div>', unsafe_allow_html=True)

    if subtitle:
        safe_subtitle = html.escape(subtitle)
        st.markdown(f'<div class="auth-subtitle">{safe_subtitle}</div>', unsafe_allow_html=True)


def _consume_token_to_default(token: str) -> tuple[bool, str | None]:
    """Consume a reset token and set the password back to the RFC value."""

    conn = get_conn()
    ensure_schema(conn)
    try:
        record = portal_get_reset_token(conn, token)
        if not record:
            return False, "El token es invalido o ya expiro."

        default_password = (record.get("rfc") or "").strip()
        if not default_password:
            return False, "El token no tiene un RFC asociado."

        if not portal_consume_reset_token(conn, token, default_password):
            return False, "El token es invalido o ya fue utilizado."

        return True, default_password
    finally:
        conn.close()


def render_token_reset_section(scope: str) -> bool:
    """Render an inline reset form that only requires the recovery token.

    Returns True when the form was submitted (successfully or not) so the caller
    can short-circuit additional processing for that run.
    """

    toggle_key = f"{scope}_forgot_toggle"

    with st.container():
        st.markdown('<div class="auth-links">', unsafe_allow_html=True)
        clicked = st.button(
            "Olvide mi contrasena",
            key=f"{scope}_forgot_btn",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    if clicked:
        st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)

    if not st.session_state.get(toggle_key, False):
        return False

    st.caption("Ingresa el token de recuperacion enviado a tu correo para restablecer tu acceso.")

    with st.form(f"{scope}_token_reset_form", clear_on_submit=False):
        token_value = st.text_input(
            "Token de recuperacion",
            key=f"{scope}_token_input",
        )
        submitted = st.form_submit_button("Restablecer contrasena", use_container_width=True)

    if not submitted:
        return False

    token_clean = (token_value or "").strip()
    if not token_clean:
        st.error("Captura el token de recuperacion.")
        return True

    try:
        ok, message = _consume_token_to_default(token_clean)
    except Exception as exc:
        st.error("No fue posible restablecer la contrasena. Intenta mas tarde.")
        st.caption(f"Detalle tecnico: {exc}")
        return True

    if not ok:
        st.error(message or "El token es invalido o ya fue utilizado.")
        return True

    st.success(
        "Contrasena restablecida al valor de tu RFC. Inicia sesion con ese valor y cambiala inmediatamente."
    )
    st.session_state.pop(toggle_key, None)
    st.session_state[f"{scope}_token_input"] = ""
    return True
