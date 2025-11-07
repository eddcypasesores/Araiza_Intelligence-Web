"""Modulo Generador de pólizas contables con UI completa y control de acceso."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from core.auth import ensure_session_from_token, persist_login
from core.db import authenticate_portal_user, ensure_schema, get_conn
from core.flash import consume_flash
from core.login_ui import render_login_header, render_token_reset_section
from core.streamlit_compat import rerun, set_query_params
from core.custom_nav import handle_logout_request, render_brand_logout_nav

MODULE_TITLE = "Generador de pólizas contables"
MODULE_PERMISSION = "generador_polizas"
RESET_SLUG = "generador_polizas"

ASSETS = Path("assets")
LOGO_PATH = ASSETS / "logo_al.jpeg"


st.set_page_config(
    page_title="Generador de Pólizas - Araiza Intelligence",
    page_icon=str(LOGO_PATH),
    layout="wide",
)
ensure_session_from_token()
handle_logout_request()


def _has_permission() -> bool:
    permisos = set(st.session_state.get("permisos") or [])
    return MODULE_PERMISSION in permisos or "admin" in permisos


def _b64(img_path: Path) -> str:
    return base64.b64encode(img_path.read_bytes()).decode()


def _render_login() -> None:
    consume_flash()
    render_login_header("Iniciar sesion", subtitle=f"Acceso {MODULE_TITLE}")
    st.caption("Valida tus credenciales para usar el generador masivo de pólizas contables.")

    with st.form("generador_polizas_login", clear_on_submit=False):
        username = st.text_input("RFC", placeholder="ej. ABCD800101XXX")
        password = st.text_input("Contrasena", type="password", placeholder="********")
        col_login, col_cancel = st.columns(2)
        submitted = col_login.form_submit_button("Iniciar sesion", use_container_width=True)
        cancelled = col_cancel.form_submit_button("Cancelar", use_container_width=True)

    if cancelled:
        st.switch_page("pages/0_Inicio.py")
        st.stop()

    handled_reset = render_token_reset_section(RESET_SLUG)
    if handled_reset:
        st.stop()

    if not submitted:
        st.stop()

    username = (username or "").strip()
    password = password or ""

    conn = get_conn()
    ensure_schema(conn)
    try:
        record = authenticate_portal_user(conn, username, password)
    except Exception as exc:
        st.error("No fue posible validar las credenciales. Intentalo de nuevo.")
        st.caption(f"Detalle tecnico: {exc}")
        st.stop()
    finally:
        conn.close()

    if not record:
        st.error("RFC o contrasena incorrectos.")
        st.stop()

    permisos = set(record.get("permisos") or [])
    if MODULE_PERMISSION not in permisos and "admin" not in permisos:
        st.error("Tu cuenta no tiene permiso para acceder a este modulo.")
        st.stop()

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

    rerun()


if not (st.session_state.get("usuario") and _has_permission()):
    _render_login()
    st.stop()


# ---------------- Navegacion ----------------
render_brand_logout_nav("Generador de polizas contables")

# ---------------- UI principal ----------------
logo_b64 = _b64(LOGO_PATH) if LOGO_PATH.exists() else ""

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@700;800;900&family=Montserrat:wght@500;600&display=swap');
:root {
  --heroH: 198px;
  --pearl: #F2F2F4;
  --cardRadius: 18px;
  --policyH: 110px;
  --dividerH: 4px;
}
html, body, [data-testid="stAppViewContainer"] { background: var(--pearl) !important; }
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
header[data-testid="stHeader"],
div[data-testid="stToolbar"],
#MainMenu,
#root > div:nth-child(1) > div[data-testid="stSidebarNav"],
#stDecoration {
  display:none !important;
}
.block-container { padding-top:0 !important; }
.hero-row {
  display: grid; grid-template-columns: 4fr 1fr; gap: 24px; align-items: stretch;
  margin: 10px 0 6px 0;
}
.hero {
  background:#000; color:#fff; border-radius: var(--cardRadius);
  min-height: var(--heroH); padding: 24px 40px;
  display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; gap:10px;
}
.hero h1 {
  margin:0; font-family:'Poppins',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  font-weight:800; font-size:clamp(36px,6.2vw,76px); letter-spacing:.6px;
}
.hero p {
  margin:0; font-family:'Montserrat',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  font-weight:600; font-size:clamp(16px,2.4vw,34px); opacity:.95;
}
.logo-card {
  border-radius:var(--cardRadius); min-height:var(--heroH); background:#000;
  box-shadow:0 4px 14px rgba(0,0,0,.08);
  display:flex; align-items:center; justify-content:center; overflow:hidden;
}
.logo-card img { max-height:100%; max-width:100%; object-fit:contain; }
.card {
  display:block; border:1px solid #e6e6e6; border-radius:16px; padding:22px;
  background:#fff; text-align:center;
  box-shadow:0 4px 14px rgba(0,0,0,.04); transition:transform .08s ease-in;
  text-decoration:none; color: inherit;
}
.card:hover { transform:translateY(-2px); box-shadow:0 8px 18px rgba(0,0,0,.06); }
.card.policy {
  height: var(--policyH);
  padding: 0 18px;
  display:flex; align-items:center; justify-content:center; text-align:center;
  font-family:'Montserrat',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  font-weight:600; font-size:clamp(14px,1.3vw,18px);
  text-decoration:none !important; color:#111 !important;
}
.placeholder { height: var(--policyH); }
.divider {
  height:var(--dividerH); background:#000; border-radius:999px;
  margin:16px 0 18px 0; box-shadow:0 1px 2px rgba(0,0,0,.08) inset;
}
.footer { color:#8b8b8b; font-size:13px; text-align:center; margin-top:32px; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="hero-row">
  <div class="hero">
    <h1>GENERADOR DE PÓLIZAS</h1>
    <p>Selecciona el tipo de póliza</p>
  </div>
  <div class="logo-card">
    <img src="data:image/jpeg;base64,{logo_b64}" alt="Araiza Intelligence" />
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.write("")

policies = [
    ("Pólizas Dr Ventas sin IVA", "https://polizas-dr-sin-iva-202p.onrender.com/"),
    ("Pólizas Dr Ventas con IVA", "https://polizas-dr-ingresos-iva-xi5m.onrender.com"),
    ("Pólizas Dr Ventas con IVA Coordinados", "https://polizas-dr-ingresos-con-retencion-iva.onrender.com"),
    ("Pólizas Dr Ventas Combinadas", "https://polizas-dr-ventas-combinadas.onrender.com/"),
    ("Pólizas Dr Egresos", "https://polizas-dr-egresos-psdm.onrender.com/"),
    ("Pólizas Ig Cobranza sin IVA", "https://polizas-ig-cobranza-sin-iva.onrender.com/"),
    ("Pólizas Ig Cobranza con IVA", "https://polizas-ig-cobranza-con-iva-befx.onrender.com/"),
    ("Pólizas Ig Cobranza sin IVA Coordinados", "https://polizas-ig-cobranza-sin-iva-coordinados.onrender.com/"),
    ("Pólizas Ig Cobranza con IVA Coordinados", "https://polizas-ig-cobranza-con-iva-coordinados.onrender.com/"),
    ("Pólizas Ig Cobranza con IVA y Retención Coordinados", "https://poliza-ig-cobranza-con-iva-coordinados.onrender.com/"),
    ("Pólizas Ig Cobranza Combinadas", "https://polizas-ig-combinadas-kke2.onrender.com/"),
    ("Pólizas Eg", "https://polizas-eg-pago-provee.onrender.com/"),
]

SLOTS_PER_ROW = 5
policy_missing = (SLOTS_PER_ROW - (len(policies) % SLOTS_PER_ROW)) % SLOTS_PER_ROW
policy_total = len(policies) + policy_missing

for start in range(0, policy_total, SLOTS_PER_ROW):
    cols = st.columns(SLOTS_PER_ROW)
    for i in range(SLOTS_PER_ROW):
        idx = start + i
        with cols[i]:
            if idx < len(policies):
                label, url = policies[idx]
                st.markdown(
                    f'<a class="card policy" href="{url}" target="_self" rel="noopener noreferrer">{label}</a>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="card placeholder"></div>', unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="footer">© 2025 Araiza Intelligence. Todos los derechos reservados.</div>', unsafe_allow_html=True)
