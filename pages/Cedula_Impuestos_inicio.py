"""Pantalla principal del modulo Cedula de impuestos."""

from __future__ import annotations

import streamlit as st

from core.theme import apply_theme
import base64
import json
from contextlib import closing
from pathlib import Path
from urllib.parse import quote, urlencode

from core.auth import forget_session
from core.custom_nav import render_brand_logout_nav
from core.db import (
    CEDULA_SHARED_SUBMODULES,
    cedula_get_payload,
    cedula_list_rfcs,
    cedula_save_payload,
    ensure_schema,
    get_conn,
)
from core.session import process_logout_flag
from core.streamlit_compat import set_query_params


CEDULA_INICIO_PAGE_PARAM = "Cedula de impuestos - Inicio"


def _normalize_rfc(value: str) -> str:
    return (value or "").strip().upper()


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
.nav-spacer{
  height:90px;
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
    ("Depreciacion contable vs fiscal", "pages/Depreciacion_contable_vs_fiscal.py"),
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


def _payload_to_text(payload) -> str:
    if payload is None:
        return ""
    if isinstance(payload, (dict, list)):
        try:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception:
            return str(payload)
    return str(payload)


def _text_to_payload(raw: str):
    stripped = (raw or "").strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


def _selected_cedula_rfc(conn) -> str | None:
    permisos = set(st.session_state.get("permisos") or [])
    is_admin = "admin" in permisos
    base_rfc = _normalize_rfc(st.session_state.get("usuario"))
    rfcs = cedula_list_rfcs(conn)
    selected = base_rfc
    if is_admin:
        options = sorted({r for r in rfcs if r} | ({base_rfc} if base_rfc else set()))
        if options:
            selected_opt = st.selectbox(
                "RFC registrados",
                options,
                index=options.index(base_rfc) if base_rfc in options else 0,
            )
        else:
            selected_opt = ""
        manual = st.text_input(
            "RFC a gestionar",
            value=selected_opt or base_rfc,
            placeholder="Ej. ABCD800101XXX",
        )
        selected = _normalize_rfc(manual) or selected_opt
    else:
        if base_rfc:
            st.caption(f"Gestionando datos para **{base_rfc}**")
        else:
            st.warning("Tu cuenta no tiene un RFC asociado.")
    selected = _normalize_rfc(selected)
    st.session_state["cedula_active_rfc"] = selected
    return selected


def _render_shared_data(conn, selected_rfc: str | None) -> None:
    if not selected_rfc:
        st.warning("Captura un RFC válido para poder compartir datos entre submódulos.")
        return

    st.subheader("Datos compartidos entre submódulos")
    st.caption(
        "La información guardada aquí estará disponible para todas las cédulas de este RFC."
    )
    user_id = st.session_state.get("portal_user_id")

    for code, label in CEDULA_SHARED_SUBMODULES:
        record = cedula_get_payload(conn, selected_rfc, code, include_metadata=True)
        existing = record["data"] if record else None
        meta_parts: list[str] = []
        if record and record.get("updated_at"):
            meta_parts.append(f"Última actualización: {record['updated_at']}")
        if record and record.get("created_by"):
            meta_parts.append(f"Capturado por ID {record['created_by']}")

        exp = st.expander(label, expanded=False)
        with exp:
            if meta_parts:
                st.caption(" · ".join(meta_parts))
            text_key = f"cedula_shared_{code}"
            default_text = _payload_to_text(existing)
            content = st.text_area(
                "Contenido (puedes pegar texto o JSON)",
                value=default_text,
                height=140,
                key=text_key,
            )
            col_save, col_reset = st.columns([1, 1])
            with col_save:
                if st.button("Guardar", key=f"save_{code}"):
                    payload = _text_to_payload(content)
                    try:
                        cedula_save_payload(
                            conn,
                            selected_rfc,
                            code,
                            payload,
                            user_id=user_id,
                        )
                        st.success("Información guardada correctamente.")
                        st.experimental_rerun()
                    except Exception as exc:
                        st.error(f"No fue posible guardar: {exc}")
            with col_reset:
                if record and st.button("Vaciar", key=f"clear_{code}"):
                    cedula_save_payload(
                        conn,
                        selected_rfc,
                        code,
                        {},
                        user_id=user_id,
                    )
                    st.success("Información eliminada.")
                    st.experimental_rerun()


def _handle_logout_request() -> None:
    if process_logout_flag():
        forget_session()
        st.switch_page("pages/0_Inicio.py")
        st.stop()


def render_fixed_nav() -> None:
    render_brand_logout_nav(CEDULA_INICIO_PAGE_PARAM, brand="Cédulas fiscales")
    st.markdown('<div class="nav-spacer"></div>', unsafe_allow_html=True)


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
    apply_theme()
    _handle_logout_request()
    _handle_pending_navigation()
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    render_fixed_nav()

    with closing(get_conn()) as conn:
        ensure_schema(conn)
        selected_rfc = _selected_cedula_rfc(conn)

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

        st.divider()
        _render_shared_data(conn, selected_rfc)


if __name__ == "__main__":
    main()
