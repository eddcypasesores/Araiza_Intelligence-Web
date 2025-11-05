"""Pantalla principal del modulo Cedula de impuestos."""

from __future__ import annotations

import streamlit as st

import base64
import html
from pathlib import Path
from urllib.parse import quote, urlencode

from core.auth import forget_session
from core.session import process_logout_flag
from core.streamlit_compat import set_query_params


NAV_LOGO_CANDIDATES = (
    Path("assets/logo_nav.png"),
    Path("assets/Araiza Intelligence logo-04.png"),
    Path("assets/Araiza Intelligence logo-04.jpg"),
    Path("assets/logo.png"),
    Path("assets/logo.jpg"),
)

CEDULA_INICIO_PAGE_PARAM = "Cedula de impuestos - Inicio"


CSS = """
:root{
  --hero-bg:#0d3c74;
  --hero-bg-2:#0b2a55;
  --card:#ffffff;
  --text:#0f172a;
  --muted:#51607b;
  --pill:#ecf2f9;
  --pill-border:#d0dae7;
  --shadow:0 18px 42px rgba(15,23,42,0.15);
}

html, body, [data-testid="stAppViewContainer"]{
  background:#f5f8fc;
}
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
header[data-testid="stHeader"],
div[data-testid="stToolbar"],
#MainMenu,
#root > div:nth-child(1) > div[data-testid="stSidebarNav"],
#stDecoration{
  display:none !important;
}
.custom-nav{
  position:fixed;
  top:0;
  left:50%;
  transform:translateX(-50%);
  width:min(1100px,100%);
  z-index:1000;
  background:#ffffff;
  color:#0f172a;
  padding:10px 22px;
  border-radius:999px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  box-shadow:0 18px 32px rgba(15,23,42,0.18);
  border:1px solid rgba(148,163,184,0.25);
}
.nav-brand{
  display:inline-flex;
  align-items:center;
  gap:10px;
  font-weight:700;
  font-size:1rem;
  text-transform:uppercase;
  letter-spacing:0.05em;
}
.nav-brand img{
  height:28px;
  width:auto;
  display:block;
}
.nav-actions a{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:6px 20px;
  border-radius:999px;
  background:#0d3c74;
  color:#fff;
  font-weight:600;
  text-decoration:none;
  box-shadow:0 6px 16px rgba(13,60,116,0.25);
}
.nav-spacer{
  height:70px;
}

.cedulas-wrapper{
  max-width:1100px;
  margin:0 auto;
  padding:24px 16px 80px;
  font-family:"Inter", "Segoe UI", sans-serif;
  color:var(--text);
}

.hero{
  border-radius:24px;
  background:linear-gradient(135deg, var(--hero-bg), var(--hero-bg-2));
  color:#fff;
  padding:clamp(28px,5vw,48px);
  display:flex;
  flex-wrap:wrap;
  gap:clamp(24px,4vw,48px);
  align-items:center;
  box-shadow:var(--shadow);
}

.hero-copy{
  flex:1 1 320px;
}
.hero-copy h1{
  margin:0;
  font-size:clamp(30px,4vw,44px);
  line-height:1.1;
}
.hero-copy p{display:none;}
.hero-media{
  flex:0 0 320px;
  max-width:420px;
}
.hero-media img{
  width:100%;
  height:auto;
  display:block;
  filter:drop-shadow(0 20px 40px rgba(7,13,28,.45));
}

.feature-card{
  margin-top:32px;
  background:var(--card);
  border-radius:24px;
  padding:clamp(18px,3vw,26px);
  box-shadow:var(--shadow);
}
.feature-card img{
  width:100%;
  border-radius:18px;
  border:1px solid #dfe6f2;
}

.components{
  margin-top:32px;
  background:var(--card);
  border-radius:24px;
  padding:clamp(24px,3vw,32px);
  box-shadow:var(--shadow);
}
.components-flex{
  display:flex;
  align-items:center;
  gap:24px;
}
.component-list{
  flex:1 1 60%;
}
.component-illustration{
  flex:1 1 40%;
  display:flex;
  justify-content:center;
}
.component-illustration img{
  width:100%;
  max-width:320px;
}
.pill-grid.two-col{
  grid-template-columns:repeat(3,minmax(0,1fr));
}
@media (max-width:900px){
  .components-flex{
    flex-direction:column;
  }
  .pill-grid.two-col{
    grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
  }
}
.components h2{
  margin:0 0 18px;
}
.pill-grid{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:12px;
}
@media (max-width:1100px){
  .pill-grid{
    grid-template-columns:repeat(2,minmax(0,1fr));
  }
}
@media (max-width:700px){
  .pill-grid{
    grid-template-columns:repeat(1,minmax(0,1fr));
  }
}
.pill{
  border-radius:999px;
  border:1px solid var(--pill-border);
  background:var(--pill);
  padding:8px 22px;
  font-size:0.95rem;
  line-height:1.2;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  text-decoration:none;
  color:var(--text);
  box-shadow:none;
  cursor:pointer;
  transition:box-shadow .15s ease, transform .15s ease;
}
.pill:hover{
  box-shadow:0 10px 18px rgba(15,23,42,.12);
  transform:translateY(-1px);
}
.pill.disabled{
  color:var(--muted);
  cursor:default;
  box-shadow:none;
}
"""

COMPONENTS = [
    ("Balanzas de comprobacion", None),
    ("Catalogos de cuentas", None),
    ("Estados financieros", None),
    ("Costo de ventas", None),
    ("Depreciacion contable vs fiscal", None),
    ("Resultado contable / fiscal", None),
    ("Conciliacion contable vs fiscal", None),
    ("Ajuste anual por inflacion", None),
    ("Perdidas fiscales", None),
    ("CUFIN y CUCA", None),
    ("Calculo de PTU", None),
    ("Coeficiente de utilidad", None),
    ("Actualizacion y Amortizacion de Perdidas", "pages/Cedula_Actualizacion_perdidas.py"),
]

DEFAULT_NAV_LOGO = ("data:image/png;base64,/9j/4AAQSkZJRgABAgEBLAEsAAD/7QAsUGhvdG9zaG9wIDMuMAA4QklNA+0AAAAAABABLAAAAAEAAQEsAAAAAQAB/+E00Gh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8APD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDggNzkuMTY0MDUwLCAyMDE5LzEwLzAxLTE4OjAzOjE2ICAgICAgICAiPgogICA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPgogICAgICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgICAgICAgICB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iCiAgICAgICAgICAgIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIKICAgICAgICAgICAgeG1sbnM6eG1wR0ltZz0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL2cvaW1nLyIKICAgICAgICAgICAgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iCiAgICAgICAgICAgIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIgogICAgICAgICAgICB4bWxuczpzdEV2dD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlRXZlbnQjIgogICAgICAgICAgICB4bWxuczppbGx1c3RyYXRvcj0iaHR0cDovL25zLmFkb2JlLmNvbS9pbGx1c3RyYXRvci8xLjAvIgogICAgICAgICAgICB4bWxuczpwZGY9Imh0dHA6Ly9ucy5hZG9iZS5jb20vcGRmLzEuMy8iPgogICAgICAgICA8ZGM6Zm9ybWF0PmltYWdlL2pwZWc8L2RjOmZvcm1hdD4KICAgICAgICAgPGRjOnRpdGxlPgogICAgICAgICAgICA8cmRmOkFsdD4KICAgICAgICAgICAgICAgPHJkZjpsaSB4bWw6bGFuZz0ieC1kZWZhdWx0Ij5JbXByaW1pcjwvcmRmOmxpPgogICAgICAgICAgICA8L3JkZjpBbHQ+CiAgICAgICAgIDwvZGM6dGl0bGU+CiAgICAgICAgIDx4bXA6TWV0YWRhdGFEYXRlPjIwMjQtMTItMTdUMTU6NTg6MzctMDY6MDA8L3htcDpNZXRhZGF0YURhdGU+CiAgICAgICAgIDx4bXA6TW9kaWZ5RGF0ZT4yMDI0LTEyLTE3VDIxOjU4OjQ0WjwveG1wOk1vZGlmeURhdGU+CiAgICAgICAgIDx4bXA6Q3JlYXRlRGF0ZT4yMDI0LTEyLTE3VDE1OjU4OjM3LTA2OjAwPC94bXA6Q3JlYXRlRGF0ZT4KICAgICAgICAgPHhtcDpDcmVhdG9yVG9vbD5BZG9iZSBJbGx1c3RyYXRvciAyNC4xIChXaW5kb3dzKTwveG1wOkNyZWF0b3JUb29sPgogICAgICAgICA8eG1wOlRodW1ibmFpbHM+CiAgICAgICAgICAgIDxyZGY6QWx0PgogICAgICAgICAgICAgICA8cmRmOmxpIHJkZjpwYXJzZVR5cGU9IlJlc291cmNlIj4KICAgICAgICAgICAgICAgICAgPHhtcEdJbWc6d2lkdGg+MjU2PC94bXBHSW1nOndpZHRoPgogICAgICAgICAgICAgICAgICA8eG1wR0ltZzp"
)

def _auth_query_param() -> str | None:
    raw = st.query_params.get("auth")
    if isinstance(raw, list):
        raw = raw[-1] if raw else None
    if raw:
        return raw
    token = st.session_state.get("auth_token")
    return token if isinstance(token, str) and token else None


def _component_pills_html(auth_token: str | None) -> str:
    parts: list[str] = []
    for label, target in COMPONENTS:
        if target:
            href = f"?goto={quote(target, safe='/')}"
            if auth_token:
                href += f"&auth={quote(auth_token)}"
            href = href.replace('"', "&quot;")
            parts.append(f'<a class="pill" href="{href}" target="_self">{label}</a>')
        else:
            parts.append(f'<span class="pill disabled">{label}</span>')
    return "".join(parts)


def _navbar_logo_data() -> str:
    for candidate in NAV_LOGO_CANDIDATES:
        if candidate.exists():
            try:
                encoded = base64.b64encode(candidate.read_bytes()).decode()
                return f"data:image/png;base64,{encoded}"
            except Exception:
                continue
    return DEFAULT_NAV_LOGO


def _logout_href() -> str:
    params: dict[str, str] = {}
    for key, value in st.query_params.items():
        if key in {"goto", "logout"}:
            continue
        if isinstance(value, list):
            value = value[-1] if value else None
        if isinstance(value, str) and value:
            params[key] = value
    params.setdefault("page", CEDULA_INICIO_PAGE_PARAM)
    params["logout"] = "1"
    query = urlencode(params, doseq=False)
    return f"?{query}"


def _handle_logout_request() -> None:
    if process_logout_flag():
        forget_session()
        st.switch_page("pages/0_Inicio.py")
        st.stop()


def render_fixed_nav() -> None:
    logo_src = _navbar_logo_data()
    logout_href = html.escape(_logout_href(), quote=True)
    nav_html = (
        f'<div class="custom-nav">'
        f'<div class="nav-brand"><img src="{logo_src}" alt="Araiza logo"><span>Araiza Intelligence</span></div>'
        f'<div class="nav-actions"><a href="{logout_href}" target="_self">Cerrar sesi&oacute;n</a></div>'
        f'</div><div class="nav-spacer"></div>'
    )
    st.markdown(nav_html, unsafe_allow_html=True)


def _handle_pending_navigation() -> None:
    params = st.query_params
    raw = params.get("goto")
    goto = None
    if isinstance(raw, list):
        goto = raw[-1] if raw else None
    elif isinstance(raw, str):
        goto = raw
    if goto:
        cleaned = {k: v for k, v in params.items() if k != "goto"}
        set_query_params(cleaned)
        try:
            st.switch_page(goto)
        except Exception:
            pass
        st.stop()


def main() -> None:
    st.set_page_config(page_title="Cedula de impuestos - Inicio", layout="wide")
    _handle_logout_request()
    _handle_pending_navigation()
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    render_fixed_nav()

    hero_bytes = Path("assets/cedula_impuestos_menu.png").read_bytes()
    hero_image_src = f"data:image/png;base64,{base64.b64encode(hero_bytes).decode()}"
    components_bytes = Path("assets/robot_pensando.png").read_bytes()
    components_image_src = f"data:image/png;base64,{base64.b64encode(components_bytes).decode()}"
    component_pills_html = _component_pills_html(_auth_query_param())

    st.markdown(
        f"""
        <div class="cedulas-wrapper">
          <section class="hero">
            <div class="hero-media">
              <img src="{hero_image_src}" alt="Papeles de trabajo y declaracion anual">
            </div>
            <div class="hero-copy">
              <h1>Cedulas fiscales - Personas Morales</h1>
              <p>(Regimen General)</p>
            </div>
          </section>
          <section class="components components-flex">
            <div class="component-list">
              <h2>Componentes disponibles</h2>
              <div class="pill-grid">
                  {component_pills_html}
              </div>
            </div>
            <div class="component-illustration">
              <img src="{components_image_src}" alt="Robot pensando" />
            </div>
          </section>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
