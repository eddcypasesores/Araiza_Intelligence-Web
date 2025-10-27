# pages/1_Calculadora.py — Costos de traslado (secciones con encabezado compacto y desglose controlado)
from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import html
from uuid import uuid4
from types import SimpleNamespace
import pandas as pd
import streamlit as st

# --- Utilidades / Proyecto
from core.auth import ensure_session_from_token, persist_login
from core.utils import inject_css, is_excluded, set_excluded, normalize_name
from core.db import get_conn, ensure_schema, get_active_version_id, validar_usuario
from core.config import GOOGLE_MAPS_API_KEY
from core.rutas import (
    load_routes,
    plazas_catalog,
    match_plaza_in_text,
    match_plazas_for_route,
)
from core.tarifas import tarifa_por_plaza
from core.driver_costs import read_trabajadores, costo_diario_trabajador_auto
from core.params import read_params
from core.maps import GoogleMapsClient, GoogleMapsError
from core.navigation import render_nav

HARDCODED_MAPS_API_KEY = "AIzaSyBqSuQGWucHtypH60GpAAIxJVap76CgRL8"

ALLOWED_ROLES: set[str] = {"admin", "operador"}

# ===============================
# Configuración de página + CSS
# ===============================
st.set_page_config(page_title="Costos de traslado", layout="wide", initial_sidebar_state="expanded")
inject_css("styles.css")

# Estilos de refuerzo (sin cajas grises; solo línea azul + layout)
st.markdown(
    """
    <style>
      .section { padding: 0 !important; margin: 0 0 .2rem 0 !important; border: none !important; }
      .section-header { margin-bottom:.2rem; }
      .section-header > div[data-testid="stHorizontalBlock"] { margin:0 !important; }
      .section-header > div[data-testid="stHorizontalBlock"] > div[data-testid="column"] { padding-top:0 !important; padding-bottom:0 !important; }
      .section-header > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) { padding-left:0 !important; margin-left:-0.45rem; }
      .section-title-row { display:flex; align-items:center; gap:0; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:#1e293b; font-size:1.18rem; }
      .section-title-row .section-title { font-size:inherit; }
      .section-toggle { display:flex; justify-content:flex-start; align-items:center; }
      .section-toggle .stButton { margin:0 !important; }
      .section-toggle .stButton>button { width:34px; height:34px; border-radius:999px; background:#eff6ff !important; border:1px solid rgba(59,130,246,.45) !important; color:#1d4ed8 !important; font-size:1.2rem !important; padding:0 !important; line-height:1 !important; }
      .section-toggle .stButton>button:hover { background:#dbeafe !important; }
      .section-total-pill { display:inline-flex; align-items:center; justify-content:center; min-width:120px; padding:.35rem .85rem; border-radius:999px; background:#dbeafe; color:#1e3a8a; border:1px solid rgba(59,130,246,.25); font-weight:700; }
      .small-note { font-size:.8rem; color:#475569; display:block; margin-bottom:.35rem; }
      .total-banner { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.9rem 1.2rem; border-radius:16px; background:linear-gradient(135deg,#bfdbfe,#dbeafe); color:#1e3a8a; border:1px solid rgba(59,130,246,.25); margin-bottom:1.2rem; }
      .total-banner-label { font-size:1.05rem; font-weight:700; text-transform:uppercase; letter-spacing:.12em; }
      .total-banner-value { font-size:1.45rem; font-weight:800; }
      .section-body { margin-top:.4rem; padding:.75rem 1rem; border-radius:14px; border:1px solid rgba(148,163,184,.25); background:rgba(248,250,252,.65); }
      .section-body p { margin-bottom:.4rem; }
      .section-body table { width:100%; border-collapse:collapse; }
      .section-body td { padding:.15rem 0; }
      .breakdown-card { margin-top:.6rem; padding:.65rem .85rem; border-radius:12px; border:1px solid rgba(148,163,184,.3); background:#fff; box-shadow:0 8px 20px -12px rgba(15,23,42,.35); display:flex; flex-direction:column; gap:.35rem; }
      .breakdown-card .breakdown-item { display:flex; justify-content:space-between; gap:.75rem; font-size:.95rem; }
      .breakdown-card .breakdown-item .breakdown-label { font-weight:600; color:#1e293b; }
      .breakdown-card .breakdown-item .breakdown-value { font-weight:600; color:#1d4ed8; text-align:right; }
      .top-form { display:flex; flex-wrap:wrap; gap:1.35rem; align-items:stretch; margin-bottom:.85rem; }
      .top-form > div[data-testid="column"] { display:flex; }
      .top-form > div[data-testid="column"] > div { flex:1; display:flex; }
      .top-form .add-stop-card { flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center; min-height:120px; }
      .top-form .add-stop-card .add-stop-button { width:100%; }
      .top-form .add-stop-card .add-stop-button button { height:120px; font-size:3.1rem; line-height:1; border-radius:18px; }
      .top-form .address-stack { width:100%; display:flex; flex-direction:column; gap:.5rem; }
      .top-form .address-stack > div[data-testid="stVerticalBlock"] { margin-bottom:0 !important; }
      .top-form .address-stack > div[data-testid="stHorizontalBlock"] { margin-top:.4rem; }
      .top-form .address-stack > div[data-testid="stVerticalBlock"]:last-child { margin-top:.35rem; }
      .top-form .meta-row { display:flex; gap:1rem; }
      .top-form .meta-row > div[data-testid="column"] { display:flex; }
      .top-form .meta-row > div[data-testid="column"] > div { flex:1; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===============================
# Sesión y permisos
# ===============================
ensure_session_from_token()

is_logged_in = bool(st.session_state.get("usuario"))
render_nav(active_top="calculadora", active_child=None, show_cta=is_logged_in)

conn = get_conn()
ensure_schema(conn)


def _render_login() -> None:
    """Muestra el formulario de acceso para la calculadora."""

    st.title("Calculadora de Traslados")
    st.subheader("Inicia sesión para continuar")

    raw_next = st.query_params.get("next")
    redirect_target: str | None
    if isinstance(raw_next, list):
        redirect_target = raw_next[-1] if raw_next else None
    elif isinstance(raw_next, str):
        redirect_target = raw_next or None
    else:
        redirect_target = None

    current_role = st.session_state.get("rol")
    if current_role and current_role not in ALLOWED_ROLES:
        st.error(
            "Tu usuario existe, pero no cuenta con permisos para utilizar la calculadora. "
            "Cierra sesión e intenta con otra cuenta o contacta al administrador."
        )

    with st.form("calculadora_login", clear_on_submit=False):
        username = st.text_input("Usuario", placeholder="ej. admin")
        password = st.text_input("Contraseña", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Iniciar sesión", use_container_width=True)

    if not submitted:
        return

    username = username.strip()

    try:
        rol = validar_usuario(conn, username, password)
    except Exception as exc:  # pragma: no cover - feedback en UI
        st.error(
            "No fue posible validar las credenciales. Verifica la conexión a la base de datos."
        )
        st.caption(f"Detalle técnico: {exc}")
        return

    if not rol:
        st.error("Usuario o contraseña incorrectos.")
        return

    if rol not in ALLOWED_ROLES:
        st.error(
            "Tu perfil se autentica correctamente, pero no tiene permiso para acceder a la calculadora."
        )
        return

    persist_login(username, rol)
    welcome = f"Bienvenido, {username} ({'Administrador' if rol == 'admin' else 'Calculador'})."
    st.session_state["login_flash"] = welcome

    if redirect_target:
        remaining = {k: v for k, v in st.query_params.items() if k != "next"}
        try:
            st.experimental_set_query_params(**remaining)
        except Exception:
            pass
        try:
            st.switch_page(redirect_target)
        except Exception:
            st.rerun()
        return

    st.rerun()


if st.session_state.get("rol") not in ALLOWED_ROLES:
    _render_login()
    st.stop()

flash_message = st.session_state.pop("login_flash", None)
if flash_message:
    st.success(flash_message)
ROUTES = load_routes()
PLAZAS = plazas_catalog(ROUTES)

vid = get_active_version_id(conn)
if vid is None:
    st.error("No hay parámetros de costeo publicados. Configura una versión vigente en la pantalla de parámetros.")
    st.stop()
PARAMS = read_params(conn, vid)

maps_api_key = (GOOGLE_MAPS_API_KEY or HARDCODED_MAPS_API_KEY).strip()

MAPS_ERROR = None
maps_client: GoogleMapsClient | None = None

if maps_api_key:
    cached_key = st.session_state.get("gmaps_client_key")
    maps_client = st.session_state.get("gmaps_client")
    if maps_client is not None and cached_key != maps_api_key:
        maps_client = None
        st.session_state.pop("gmaps_client", None)
        st.session_state.pop("gmaps_client_key", None)

    if maps_client is None:
        try:
            maps_client = GoogleMapsClient(api_key=maps_api_key)
            st.session_state["gmaps_client"] = maps_client
            st.session_state["gmaps_client_key"] = maps_api_key
        except GoogleMapsError as exc:
            MAPS_ERROR = str(exc)
            st.session_state.pop("gmaps_client", None)
            st.session_state.pop("gmaps_client_key", None)
else:
    MAPS_ERROR = (
        "Configura la variable de entorno GOOGLE_MAPS_API_KEY para habilitar el autocompletado y el cálculo de rutas."
    )

maps_client = st.session_state.get("gmaps_client")
MAPS_AVAILABLE = maps_client is not None
MANUAL_MODE = not MAPS_AVAILABLE
if MAPS_ERROR:
    msg = MAPS_ERROR
    if not MAPS_AVAILABLE:
        msg += " Se habilitó el modo manual sin integración con Google Maps."
    st.warning(msg)
maps_cache = st.session_state.setdefault("gmaps_cache", {})
for bucket in ("autocomplete", "place_details", "directions", "plaza_lookup", "plaza_geometry"):
    maps_cache.setdefault(bucket, {})

session_token = st.session_state.setdefault("gmaps_session_token", str(uuid4()))


_PDF_BUILDER = None


def get_pdf_builder():
    global _PDF_BUILDER
    if _PDF_BUILDER is not None:
        return _PDF_BUILDER

    if importlib.util.find_spec("reportlab") is None:
        st.error(
            "La librería opcional 'reportlab' es necesaria para generar el PDF. "
            "Ejecuta `pip install -r requirements.txt` o `pip install reportlab` e intenta de nuevo."
        )
        st.stop()

    from core.pdf import build_pdf_costeo  # noqa: WPS433 (import dentro de la función)

    _PDF_BUILDER = build_pdf_costeo
    return _PDF_BUILDER


@dataclass
class SectionBodyResult:
    total: float | None = None
    breakdown: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class SectionOutput:
    title: str
    total: float
    breakdown: list[tuple[str, str]]


def section(title: str, total_value: float | None, body_fn=None) -> SectionOutput:
    """Renderiza una sección con encabezado compacto y devuelve su información."""

    toggle_key = f"section_toggle_{normalize_name(title)}"
    show_details = bool(st.session_state.get(toggle_key, False))
    icon_char = "▾" if show_details else "▸"

    st.markdown("<div class='section'>", unsafe_allow_html=True)
    header_container = st.container()
    with header_container:
        st.markdown("<div class='section-header'>", unsafe_allow_html=True)
        header_cols = st.columns([0.72, 0.08, 0.2], gap="small")
        with header_cols[0]:
            st.markdown(
                f"<div class='section-title-row'><span class='section-title'>{title}</span></div>",
                unsafe_allow_html=True,
            )
        with header_cols[1]:
            st.markdown("<div class='section-toggle'>", unsafe_allow_html=True)
            if st.button(
                icon_char,
                key=f"{toggle_key}_btn",
                help="Mostrar u ocultar desglose",
            ):
                st.session_state[toggle_key] = not show_details
                show_details = not show_details
                icon_char = "▾" if show_details else "▸"
            st.markdown("</div>", unsafe_allow_html=True)
        total_placeholder = header_cols[2].empty()
        st.markdown("</div>", unsafe_allow_html=True)

    computed_total = float(total_value) if total_value is not None else 0.0
    result = SectionBodyResult()

    if body_fn:
        body_container = st.container()
        with body_container:
            if show_details:
                st.markdown("<div class='section-body'>", unsafe_allow_html=True)
            raw_result = body_fn(show_details)
            if show_details:
                st.markdown("</div>", unsafe_allow_html=True)
        if isinstance(raw_result, SectionBodyResult):
            result = raw_result
        elif isinstance(raw_result, tuple) and len(raw_result) == 2:
            maybe_total, breakdown = raw_result
            result = SectionBodyResult(
                total=float(maybe_total) if maybe_total is not None else None,
                breakdown=list(breakdown) if breakdown else [],
            )
        elif isinstance(raw_result, (int, float)):
            result = SectionBodyResult(total=float(raw_result))
        elif isinstance(raw_result, list):
            result = SectionBodyResult(breakdown=list(raw_result))

        if result.total is not None:
            computed_total = float(result.total)

    total_placeholder.markdown(
        f"<div class='section-total-pill'>${computed_total:,.2f}</div>",
        unsafe_allow_html=True,
    )

    if show_details and result.breakdown:
        breakdown_container = st.container()
        with breakdown_container:
            st.markdown("<div class='breakdown-card'>", unsafe_allow_html=True)
            for raw_label, raw_value in result.breakdown:
                label = html.escape(str(raw_label))
                value = html.escape(str(raw_value))
                st.markdown(
                    f"<div class='breakdown-item'><span class='breakdown-label'>{label}</span><span class='breakdown-value'>{value}</span></div>",
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    return SectionOutput(title=title, total=computed_total, breakdown=result.breakdown)


def autocomplete_input(label: str, key_prefix: str) -> dict[str, str] | None:
    query_key = f"{key_prefix}_query"
    options_key = f"{key_prefix}_options"
    selection_key = f"{key_prefix}_selection"
    data_key = f"{key_prefix}_data"

    query_value = st.text_input(
        label,
        value=st.session_state.get(query_key, ""),
        key=query_key,
        placeholder="Ingresa dirección, ciudad o caseta",
    )

    trimmed = (query_value or "").strip()
    if not MAPS_AVAILABLE:
        if trimmed:
            data = {
                "description": trimmed,
                "place_id": f"manual:{key_prefix}:{normalize_name(trimmed)}",
                "matched_plaza": match_plaza_in_text(trimmed, PLAZAS),
                "lat": None,
                "lng": None,
                "address": trimmed,
            }
            st.session_state[data_key] = data
        else:
            st.session_state.pop(data_key, None)
        st.session_state.pop(options_key, None)
        st.session_state.pop(selection_key, None)
        if trimmed:
            st.caption(f"Entrada manual: **{trimmed}**")
        return st.session_state.get(data_key)

    predictions: list[dict[str, str]] = []
    if trimmed and len(trimmed) >= 3:
        try:
            predictions = maps_client.autocomplete(
                trimmed,
                session_token=session_token,
                cache=maps_cache["autocomplete"],
            )
        except GoogleMapsError as exc:
            st.warning(f"Google Maps (autocomplete) respondió con un error: {exc}")
            predictions = []
        st.session_state[options_key] = predictions
    else:
        st.session_state[options_key] = []

    predictions = st.session_state.get(options_key, []) or []
    if predictions:
        options = [pred.get("description", "") for pred in predictions]
        prev = st.session_state.get(selection_key)
        default_idx = options.index(prev) if prev in options else 0
        selected_desc = st.selectbox(
            "Coincidencias",
            options,
            index=default_idx,
            key=selection_key,
            label_visibility="collapsed",
        )
        chosen = next((pred for pred in predictions if pred.get("description", "") == selected_desc), None)
        if chosen and chosen.get("place_id"):
            place_id = chosen.get("place_id")
            details_lat: float | None = None
            details_lng: float | None = None
            formatted_address: str | None = None
            existing = st.session_state.get(data_key) or {}

            if existing.get("place_id") == place_id and existing.get("lat") is not None and existing.get("lng") is not None:
                details_lat = existing.get("lat")
                details_lng = existing.get("lng")
                formatted_address = existing.get("address")
            else:
                try:
                    details = maps_client.place_details(
                        place_id,
                        session_token=session_token,
                        cache=maps_cache["place_details"],
                    )
                except GoogleMapsError as exc:
                    st.warning(f"Google Maps (detalles) respondió con un error: {exc}")
                    details = {}

                result = details.get("result", {}) if isinstance(details, dict) else {}
                geometry = result.get("geometry", {}) if isinstance(result, dict) else {}
                location = geometry.get("location", {}) if isinstance(geometry, dict) else {}
                if isinstance(location, dict):
                    lat_val = location.get("lat")
                    lng_val = location.get("lng")
                    try:
                        details_lat = float(lat_val) if lat_val is not None else None
                    except (TypeError, ValueError):
                        details_lat = None
                    try:
                        details_lng = float(lng_val) if lng_val is not None else None
                    except (TypeError, ValueError):
                        details_lng = None
                formatted_address = result.get("formatted_address") if isinstance(result, dict) else None

            matched_plaza = match_plaza_in_text(selected_desc, PLAZAS)
            data = {
                "description": selected_desc,
                "place_id": place_id,
                "matched_plaza": matched_plaza,
                "lat": details_lat,
                "lng": details_lng,
                "address": formatted_address,
            }
            st.session_state[data_key] = data
            return data
    else:
        st.session_state.pop(selection_key, None)
        st.session_state.pop(data_key, None)
        if trimmed:
            if len(trimmed) < 3:
                st.caption("Escribe al menos 3 caracteres para buscar.")
            else:
                st.info("Sin coincidencias para la búsqueda.")

    return st.session_state.get(data_key)


def _calculate_route(
    origin: dict[str, str] | None,
    destination: dict[str, str] | None,
    waypoint: dict[str, str] | None,
    *,
    avoid_tolls: bool,
):
    if not origin or not destination:
        return None, "Selecciona un origen y un destino válidos."
    if maps_client is None:
        return None, "Google Maps no está disponible en este momento."

    waypoint_ids = [waypoint["place_id"]] if waypoint else None
    try:
        summary = maps_client.route_summary(
            origin["place_id"],
            destination["place_id"],
            waypoints=waypoint_ids,
            avoid="tolls" if avoid_tolls else None,
            cache=maps_cache["directions"],
        )
    except GoogleMapsError as exc:
        return None, str(exc)

    return summary, None


# ===============================
# Encabezado + Selecciones TOP (orden solicitado)
# ===============================
st.markdown("<div class='hero-title'>COSTOS DE TRASLADO</div>", unsafe_allow_html=True)

clases = ["MOTO", "AUTOMOVIL", "B2", "B3", "B4", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]
default_idx = clases.index("T5")

trab_df = read_trabajadores(conn)
trab_opc = ["(Sin conductor)"] + [f"{r['nombre_completo']} — {r['numero_economico']}" for _, r in trab_df.iterrows()]

dias_manual_flag_key = "dias_input_manual"
if dias_manual_flag_key not in st.session_state:
    st.session_state[dias_manual_flag_key] = False


def _mark_dias_manual():
    st.session_state[dias_manual_flag_key] = True

stop_state_key = "show_intermediate_stop"
if stop_state_key not in st.session_state:
    st.session_state[stop_state_key] = False
if MANUAL_MODE and st.session_state.get(stop_state_key):
    st.session_state[stop_state_key] = False

with st.container():
    st.markdown("<div class='top-form'>", unsafe_allow_html=True)
    col_plus, col_addresses = st.columns([0.2, 1.0], gap="large")

    with col_plus:
        st.markdown("<div class='add-stop-card'>", unsafe_allow_html=True)
        btn_disabled = MANUAL_MODE
        help_text = "Maps no disponible" if btn_disabled else (
            "Agregar parada" if not st.session_state.get(stop_state_key) else "Quitar parada"
        )
        st.markdown("<div class='add-stop-button'>", unsafe_allow_html=True)
        if st.button(
            "➕",
            key="toggle_stop_btn",
            type="primary",
            use_container_width=True,
            disabled=btn_disabled,
            help=help_text,
        ):
            st.session_state[stop_state_key] = not st.session_state.get(stop_state_key, False)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_addresses:
        st.markdown("<div class='address-stack'>", unsafe_allow_html=True)
        origen = autocomplete_input("ORIGEN", "top_origen")
        destino = autocomplete_input("DESTINO", "top_destino")
        show_stop = bool(st.session_state.get(stop_state_key)) and not MANUAL_MODE
        if show_stop:
            parada = autocomplete_input("PARADA (OPCIONAL)", "top_parada")
        else:
            st.session_state.pop("top_parada_query", None)
            st.session_state.pop("top_parada_options", None)
            st.session_state.pop("top_parada_selection", None)
            st.session_state.pop("top_parada_data", None)
            parada = None

        meta_cols = st.columns(3, gap="medium")
        with meta_cols[0]:
            clase = st.selectbox("CLASE (TIPO DE AUTO)", clases, index=default_idx, key="top_clase")
        with meta_cols[1]:
            viaticos_mxn = st.number_input(
                "VIÁTICOS (MXN)",
                min_value=0.0,
                value=float(st.session_state.get("viat_input_main", 0.0)),
                step=50.0,
                format="%.2f",
                key="viat_input_main",
            )
        with meta_cols[2]:
            distancia_base = float(st.session_state.get("maps_distance_km") or 0.0)
            dias_sugeridos = max(1.0, round(distancia_base / 600.0, 1))
            dias_init = float(st.session_state.get("dias_estimados_input", dias_sugeridos))
            dias_est = st.number_input(
                "DÍAS ESTIMADOS",
                min_value=1.0,
                step=0.5,
                value=dias_init,
                format="%.2f",
                key="dias_estimados_input",
                on_change=_mark_dias_manual,
            )

        current_conductor = st.session_state.get("conductor_select", trab_opc[0])
        default_conductor_idx = trab_opc.index(current_conductor) if current_conductor in trab_opc else 0
        trab_show = st.selectbox(
            "SELECCIONAR CONDUCTOR",
            trab_opc,
            index=default_conductor_idx,
            key="conductor_select",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

total_banner = st.container()

usar_parada = bool(st.session_state.get(stop_state_key)) and not MANUAL_MODE
evitar_cuotas = False

origin_label = origen.get("description", "") if origen else ""
destination_label = destino.get("description", "") if destino else ""
stop_label = parada.get("description", "") if (usar_parada and parada) else ""
st.session_state["origin_label"] = origin_label
st.session_state["destination_label"] = destination_label
st.session_state["stop_label"] = stop_label

def compute_route_data():
    """Consulta Google Maps, calcula la ruta y determina las casetas aplicables."""

    waypoint = parada if (usar_parada and parada) else None
    summary, route_error = _calculate_route(origen, destino, waypoint, avoid_tolls=evitar_cuotas)
    if route_error:
        return None, None, None, route_error
    if summary is None:
        return None, None, None, None

    st.session_state["gmaps_route"] = summary
    st.session_state["maps_distance_km"] = float(summary.distance_m or 0.0) / 1000.0
    st.session_state["maps_polyline_points"] = summary.polyline_points
    st.session_state["maps_route_summary"] = summary.summary
    selections = [s for s in (origen, waypoint, destino) if s]

    match = match_plazas_for_route(
        ROUTES,
        selections,
        summary.polyline_points,
        maps_client=maps_client,
        cache=maps_cache,
        session_token=session_token,
    )

    if match:
        ruta_nombre, secuencia = match
    else:
        ruta_nombre = summary.summary or "Ruta Google Maps (sin coincidencia en catálogo)"
        secuencia = []

    rows = [
        {"idx": i, "plaza": plaza, "tarifa": tarifa_por_plaza(conn, plaza, clase)}
        for i, plaza in enumerate(secuencia)
    ]
    st.session_state["detected_plazas"] = [row["plaza"] for row in rows]
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["idx", "plaza", "tarifa"])
    return summary, ruta_nombre, df, None


def manual_route_flow(
    origin: dict[str, str] | None,
    destination: dict[str, str] | None,
    clase: str,
):
    empty_df = pd.DataFrame(columns=["idx", "plaza", "tarifa"])
    origin_label = (origin or {}).get("description", "").strip()
    destination_label = (destination or {}).get("description", "").strip()
    if not origin_label or not destination_label:
        st.info("Ingresa un origen y un destino para comenzar el cálculo manual.")
        return None, None, empty_df, None

    st.info(
        "Modo manual activo: ingresa la distancia estimada y selecciona manualmente las casetas aplicables."
    )

    cols = st.columns([1.0, 1.0])
    with cols[0]:
        if "manual_distance_km" not in st.session_state:
            st.session_state["manual_distance_km"] = float(st.session_state.get("maps_distance_km") or 0.0)
        manual_distance = st.number_input(
            "DISTANCIA ESTIMADA (KM)",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            key="manual_distance_km",
            help="Ingresa la distancia total aproximada del recorrido.",
        )
    with cols[1]:
        route_options = sorted(ROUTES.keys()) if ROUTES else []
        select_options = ["(Sin catálogo)"] + route_options
        if "manual_route_choice" not in st.session_state:
            st.session_state["manual_route_choice"] = select_options[0]
        route_choice = st.selectbox(
            "Ruta de referencia (opcional)",
            select_options,
            key="manual_route_choice",
            help="Selecciona una ruta precargada para poblar automáticamente las casetas.",
        )

    if "_manual_last_route" not in st.session_state:
        st.session_state["_manual_last_route"] = route_choice

    if route_choice != st.session_state.get("_manual_last_route"):
        st.session_state["_manual_last_route"] = route_choice
        if route_choice != "(Sin catálogo)":
            st.session_state["manual_plazas"] = list(ROUTES.get(route_choice, []))
        else:
            st.session_state["manual_plazas"] = st.session_state.get("manual_plazas", [])

    default_plazas = st.session_state.get("manual_plazas", list(ROUTES.get(route_choice, [])))
    manual_plazas = st.multiselect(
        "Casetas incluidas",
        PLAZAS,
        default=default_plazas,
        key="manual_plazas",
        help="Selecciona las casetas que se incluirán en el cálculo.",
    )

    if route_choice != "(Sin catálogo)":
        order_map = {p: idx for idx, p in enumerate(ROUTES.get(route_choice, []))}
        manual_plazas_sorted = sorted(
            manual_plazas,
            key=lambda p: order_map.get(p, len(order_map) + manual_plazas.index(p)),
        )
    else:
        manual_plazas_sorted = list(manual_plazas)

    rows = [
        {"idx": i, "plaza": plaza, "tarifa": tarifa_por_plaza(conn, plaza, clase)}
        for i, plaza in enumerate(manual_plazas_sorted)
    ]

    df = pd.DataFrame(rows) if rows else empty_df

    route_title = route_choice if route_choice != "(Sin catálogo)" else f"{origin_label} → {destination_label}"
    st.session_state["maps_distance_km"] = float(manual_distance or 0.0)
    st.session_state["gmaps_route"] = None
    st.session_state["maps_polyline_points"] = []
    st.session_state["maps_route_summary"] = route_title
    st.session_state["detected_plazas"] = [row["plaza"] for row in rows]
    summary = SimpleNamespace(
        distance_m=float(manual_distance or 0.0) * 1000.0,
        duration_s=0.0,
        polyline=None,
        polyline_points=[],
        legs=[],
        summary=route_title,
        warnings=[],
        fare=None,
        raw={},
    )

    return summary, route_title, df, None


if MANUAL_MODE:
    route_summary, ruta_nombre, df, route_error = manual_route_flow(origen, destino, clase)
else:
    route_summary, ruta_nombre, df, route_error = compute_route_data()
if route_error:
    st.error(f"❌ {route_error}")
    st.stop()

if route_summary is None:
    if not MANUAL_MODE:
        st.info("Selecciona un origen y un destino para calcular la ruta.")
    st.stop()

# Limpiar exclusiones si cambian selecciones
sel = (
    origen["place_id"] if origen else None,
    destino["place_id"] if destino else None,
    clase,
    usar_parada,
    (parada["place_id"] if usar_parada and parada else None),
    evitar_cuotas,
)
if st.session_state.get("last_sel_top") != sel:
    for k in list(st.session_state.keys()):
        if str(k).startswith("cb_"):
            del st.session_state[k]
    st.session_state["last_sel_top"] = sel

# Reset exclusiones si cambia la ruta
if st.session_state.get("route_name") != ruta_nombre:
    st.session_state["route_name"] = ruta_nombre
    st.session_state.setdefault("excluded_set", set())
    st.session_state["excluded_set"].clear()

distance_km_detected = float(st.session_state.get("maps_distance_km") or 0.0)

if getattr(route_summary, "warnings", None):
    prefix = "Google Maps advierte" if MAPS_AVAILABLE else "Aviso"
    for warn in route_summary.warnings:
        st.warning(f"{prefix}: {warn}")

# ===============================
# 1) PEAJE
# ===============================
section_outputs: list[SectionOutput] = []

def _peaje_body(show: bool) -> SectionBodyResult:
    breakdown: list[tuple[str, str]] = []

    if df.empty:
        if show:
            st.caption("No se detectaron casetas para la ruta seleccionada.")
        st.session_state["subtotal_peajes"] = 0.0
        return SectionBodyResult(
            total=0.0,
            breakdown=[("Casetas detectadas", "Sin resultados")],
        )

    if show:
        st.markdown(
            "<span class='small-note'>Marca la caseta para excluirla del total.</span>",
            unsafe_allow_html=True,
        )
        COLS = [0.6, 7.0, 2.4]
        h1, h2, h3 = st.columns(COLS)
        h2.markdown("**PLAZA**")
        h3.markdown("**TARIFA (MXN)**")

        for _, row in df.iterrows():
            idx = int(row["idx"])
            c1x, c2x, c3x = st.columns(COLS)
            default_checked = bool(st.session_state.get(f"cb_{idx}", is_excluded(idx)))
            checked = c1x.checkbox(
                "",
                key=f"cb_{idx}",
                value=default_checked,
                label_visibility="hidden",
            )
            set_excluded(idx, bool(checked))
            c2x.markdown(row["plaza"])
            c3x.markdown(f"${float(row['tarifa']):,.2f}")

    subtotal = 0.0
    for _, r in df.iterrows():
        included = not is_excluded(int(r["idx"]))
        if included:
            subtotal += float(r["tarifa"])
        status = "Incluida" if included else "Excluida"
        breakdown.append((str(r["plaza"]), f"{status} — ${float(r['tarifa']):,.2f}"))

    st.session_state["subtotal_peajes"] = subtotal
    breakdown.append(("Subtotal peajes considerados", f"${subtotal:,.2f}"))
    return SectionBodyResult(total=subtotal, breakdown=breakdown)

peaje_section = section("PEAJE", None, _peaje_body)
section_outputs.append(peaje_section)
subtotal_peajes = peaje_section.total

# ===============================
# 2) DIESEL
# ===============================
diesel_params = PARAMS.get("diesel", {}) if isinstance(PARAMS, dict) else {}
rendimiento = float(diesel_params.get("rendimiento_km_l") or 0.0)
precio_litro = float(diesel_params.get("precio_litro") or 0.0)

distancia_km_val = float(st.session_state.get("maps_distance_km") or 0.0)
km_totales = float(distancia_km_val or 0.0)
litros_estimados = (km_totales / rendimiento) if rendimiento > 0 else 0.0
subtotal_combustible = float(litros_estimados) * precio_litro

def _diesel_body(show: bool) -> SectionBodyResult:
    rows = [
        ("KM totales", f"{km_totales:,.2f} km"),
        ("Rendimiento", f"{rendimiento:,.2f} km/L"),
        ("Litros estimados", f"{litros_estimados:,.2f} L"),
        ("Precio por litro", f"${precio_litro:,.2f}"),
    ]
    if show:
        for label, value in rows:
            st.write(f"**{label}:** {value}")
    rows.append(("Subtotal diésel", f"${subtotal_combustible:,.2f}"))
    return SectionBodyResult(total=subtotal_combustible, breakdown=rows)

diesel_section = section("DIESEL", subtotal_combustible, _diesel_body)
section_outputs.append(diesel_section)

# ===============================
# 3) MANO DE OBRA (método Edwin)
# ===============================
trab_show = st.session_state.get("conductor_select", trab_opc[0])

dias_sugeridos = max(1.0, round((km_totales or 0.0) / 600.0, 1))
if not st.session_state.get(dias_manual_flag_key) and (
    float(st.session_state.get("dias_estimados_input", dias_sugeridos)) != float(dias_sugeridos)
):
    st.session_state["dias_estimados_input"] = dias_sugeridos
elif st.session_state.get(dias_manual_flag_key) and (
    float(st.session_state.get("dias_estimados_input", dias_sugeridos)) == float(dias_sugeridos)
):
    st.session_state[dias_manual_flag_key] = False

dias_est = float(st.session_state.get("dias_estimados_input", dias_sugeridos))

trabajador_sel = None
if trab_show != "(Sin conductor)":
    for _, r in trab_df.iterrows():
        if f"{r['nombre_completo']} — {r['numero_economico']}" == trab_show:
            trabajador_sel = r.to_dict()
            break

subtotal_conductor = 0.0
costo_diario_total = 0.0
anios = 1
mano_obra_dia = impuestos_dia = 0.0
if trabajador_sel:
    mano_obra_dia, impuestos_dia, costo_diario_total, anios = costo_diario_trabajador_auto(trabajador_sel)
    subtotal_conductor = float(dias_est) * float(costo_diario_total)

def _mo_body(show: bool) -> SectionBodyResult:
    if not trabajador_sel:
        if show:
            st.caption("Selecciona un conductor para ver el desglose.")
        return SectionBodyResult(
            total=subtotal_conductor,
            breakdown=[("Conductor", "Sin asignar")],
        )

    rows = [
        ("Antigüedad estimada", f"{anios} año(s)"),
        ("Salario diario base", f"${float(trabajador_sel.get('salario_diario',0)):,.2f}"),
        ("Aguinaldo (prorrateado)", "Incluido"),
        ("Prima vacacional (prorrateada)", "Incluida"),
        ("IMSS / Carga social (día)", f"${impuestos_dia:,.2f}"),
        ("Costo diario total", f"${costo_diario_total:,.2f}"),
        ("Días estimados", f"{dias_est}"),
    ]
    if show:
        st.write(f"**Antigüedad estimada:** {anios} año(s)")
        st.write(f"**Salario diario base:** ${float(trabajador_sel.get('salario_diario',0)):,.2f}")
        st.write("**Aguinaldo (prorrateado):** incluido")
        st.write("**Prima vacacional (prorrateada):** incluida")
        st.write(f"**IMSS / Carga social (día):** ${impuestos_dia:,.2f}")
        st.write(f"**Costo diario total:** ${costo_diario_total:,.2f}")
        st.write(f"**Días estimados:** {dias_est}")
    rows.append(("Total mano de obra", f"${subtotal_conductor:,.2f}"))
    return SectionBodyResult(total=subtotal_conductor, breakdown=rows)

mano_obra_section = section("MANO DE OBRA", subtotal_conductor, _mo_body)
section_outputs.append(mano_obra_section)

# Apoyos comunes
peajes_ajustados = float(subtotal_peajes or 0.0)
km_totales = float(km_totales or 0.0)
rendimiento = float(rendimiento or 0.0)
precio_litro = float(precio_litro or 0.0)
litros_estimados = (km_totales / rendimiento) if rendimiento > 0 else 0.0

# ===============================
# 5) LLANTAS
# ===============================
sub_llantas = km_totales * float(PARAMS["costos_km"]["costo_llantas_km"] or 0.0)
def _llantas_body(show: bool) -> SectionBodyResult:
    costo_km = float(PARAMS['costos_km']['costo_llantas_km'] or 0.0)
    rows = [
        ("Costo por km", f"${costo_km:,.2f}/km"),
        ("KM considerados", f"{km_totales:,.2f}"),
    ]
    if show:
        st.write(f"**Costo por km:** ${costo_km:,.2f}/km")
        st.write(f"**KM considerados:** {km_totales:,.2f}")
    rows.append(("Total llantas", f"${sub_llantas:,.2f}"))
    return SectionBodyResult(total=sub_llantas, breakdown=rows)

llantas_section = section("LLANTAS", sub_llantas, _llantas_body)
section_outputs.append(llantas_section)


# ===============================
# 6) MANTENIMIENTO
# ===============================
sub_mantto = km_totales * float(PARAMS["costos_km"]["costo_mantto_km"] or 0.0)
def _mantto_body(show: bool) -> SectionBodyResult:
    costo_km = float(PARAMS['costos_km']['costo_mantto_km'] or 0.0)
    rows = [
        ("Costo por km", f"${costo_km:,.2f}/km"),
        ("KM considerados", f"{km_totales:,.2f}"),
    ]
    if show:
        st.write(f"**Costo por km:** ${costo_km:,.2f}/km")
        st.write(f"**KM considerados:** {km_totales:,.2f}")
    rows.append(("Total mantenimiento", f"${sub_mantto:,.2f}"))
    return SectionBodyResult(total=sub_mantto, breakdown=rows)

mantenimiento_section = section("MANTENIMIENTO", sub_mantto, _mantto_body)
section_outputs.append(mantenimiento_section)

# ===============================
# 7) DEPRECIACIÓN
# ===============================
dep = PARAMS["depreciacion"]
dep_anual = (float(dep["costo_adq"]) - float(dep["valor_residual"])) / max(int(dep["vida_anios"]),1)
dep_km = dep_anual / max(int(dep["km_anuales"]),1)
sub_dep = dep_km * km_totales
def _dep_body(show: bool) -> SectionBodyResult:
    rows = [
        ("Costo adquisición", f"${float(dep['costo_adq']):,.2f}"),
        ("Valor residual", f"${float(dep['valor_residual']):,.2f}"),
        ("Vida útil", f"{int(dep['vida_anios'])} años"),
        ("KM anuales", f"{int(dep['km_anuales'])}"),
        ("Depreciación por km", f"${dep_km:,.4f}"),
    ]
    if show:
        st.write(f"**Costo adquisición:** ${float(dep['costo_adq']):,.2f}")
        st.write(f"**Valor residual:** ${float(dep['valor_residual']):,.2f}")
        st.write(f"**Vida:** {int(dep['vida_anios'])} años · **KM/año:** {int(dep['km_anuales'])}")
        st.write(f"**Depreciación por km:** ${dep_km:,.4f}")
    rows.append(("Total depreciación", f"${sub_dep:,.2f}"))
    return SectionBodyResult(total=sub_dep, breakdown=rows)

depreciacion_section = section("DEPRECIACIÓN", sub_dep, _dep_body)
section_outputs.append(depreciacion_section)

# ===============================
# 8) SEGUROS
# ===============================
seg = PARAMS["seguros"]
seg_km = float(seg["prima_anual"]) / max(int(seg["km_anuales"]),1)
sub_seg = seg_km * km_totales
def _seg_body(show: bool) -> SectionBodyResult:
    rows = [
        ("Prima anual", f"${float(seg['prima_anual']):,.2f}"),
        ("KM anuales", f"{int(seg['km_anuales'])}"),
        ("Seguro por km", f"${seg_km:,.4f}"),
    ]
    if show:
        st.write(f"**Prima anual:** ${float(seg['prima_anual']):,.2f} · **KM/año:** {int(seg['km_anuales'])}")
        st.write(f"**Seguro por km:** ${seg_km:,.4f}")
    rows.append(("Total seguros", f"${sub_seg:,.2f}"))
    return SectionBodyResult(total=sub_seg, breakdown=rows)

seguros_section = section("SEGUROS", sub_seg, _seg_body)
section_outputs.append(seguros_section)


# ===============================
# 9) VIÁTICOS
# ===============================
def _viat_body(show: bool) -> SectionBodyResult:
    if show:
        st.write(f"**Monto fijo ingresado:** ${viaticos_mxn:,.2f}")
    rows = [("Monto fijo ingresado", f"${viaticos_mxn:,.2f}")]
    return SectionBodyResult(total=viaticos_mxn, breakdown=rows)

viaticos_section = section("VIÁTICOS", viaticos_mxn, _viat_body)
section_outputs.append(viaticos_section)

# ===============================
# 10) CUSTODIA
# ===============================
sub_custodia = km_totales * float(PARAMS["otros"]["custodia_km"] or 0.0)
def _cust_body(show: bool) -> SectionBodyResult:
    costo_km = float(PARAMS['otros']['custodia_km'] or 0.0)
    rows = [
        ("Costo por km", f"${costo_km:,.2f}/km"),
        ("KM considerados", f"{km_totales:,.2f}"),
    ]
    if show:
        st.write(f"**Costo por km:** ${costo_km:,.2f}/km")
        st.write(f"**KM considerados:** {km_totales:,.2f}")
    rows.append(("Total custodia", f"${sub_custodia:,.2f}"))
    return SectionBodyResult(total=sub_custodia, breakdown=rows)

custodia_section = section("CUSTODIA", sub_custodia, _cust_body)
section_outputs.append(custodia_section)

# ===============================
# 11) PERMISOS
# ===============================
sub_permiso = float(PARAMS["otros"]["permiso_viaje"] or 0.0)
def _perm_body(show: bool) -> SectionBodyResult:
    if show:
        st.write(f"**Permiso por viaje:** ${sub_permiso:,.2f}")
    rows = [("Permiso por viaje", f"${sub_permiso:,.2f}")]
    return SectionBodyResult(total=sub_permiso, breakdown=rows)

permisos_section = section("PERMISOS", sub_permiso, _perm_body)
section_outputs.append(permisos_section)

# ===============================
# 12) DEF
# ===============================
pct_def = float(PARAMS["def"]["pct_def"] or 0.0)
precio_def = float(PARAMS["def"]["precio_def_litro"] or 0.0)
litros_def = litros_estimados * pct_def
sub_def = litros_def * precio_def
def _def_body(show: bool) -> SectionBodyResult:
    rows = [
        ("% DEF vs diésel", f"{pct_def*100:.2f}%"),
        ("Litros DEF", f"{litros_def:,.2f} L"),
        ("Precio DEF/L", f"${precio_def:,.2f}"),
    ]
    if show:
        st.write(f"**% DEF vs diésel:** {pct_def*100:.2f}%")
        st.write(f"**Litros DEF:** {litros_def:,.2f} · **Precio DEF/L:** ${precio_def:,.2f}")
    rows.append(("Total DEF", f"${sub_def:,.2f}"))
    return SectionBodyResult(total=sub_def, breakdown=rows)

def_section = section("DEF", sub_def, _def_body)
section_outputs.append(def_section)

# ===============================
# 13) COMISIÓN TAG
# ===============================
pct_tag = float(PARAMS["tag"]["pct_comision_tag"] or 0.0)
sub_tag = peajes_ajustados * pct_tag
def _tag_body(show: bool) -> SectionBodyResult:
    rows = [
        ("Comisión TAG %", f"{pct_tag*100:.2f}%"),
        ("Base peajes", f"${peajes_ajustados:,.2f}"),
    ]
    if show:
        st.write(f"**Comisión TAG %:** {pct_tag*100:.2f}%")
        st.write(f"**Base peajes:** ${peajes_ajustados:,.2f}")
    rows.append(("Total comisión TAG", f"${sub_tag:,.2f}"))
    return SectionBodyResult(total=sub_tag, breakdown=rows)

tag_section = section("COMISIÓN TAG", sub_tag, _tag_body)
section_outputs.append(tag_section)

# ===============================
# Base para (14) Financiamiento, (15) Overhead, (16) Utilidad
# ===============================
base_conceptos = set(PARAMS["politicas"]["incluye_en_base"])
base_val = 0.0
if "peajes" in base_conceptos:       base_val += peajes_ajustados
if "diesel" in base_conceptos:       base_val += float(subtotal_combustible or 0.0)
if "llantas" in base_conceptos:      base_val += sub_llantas
if "mantto" in base_conceptos:       base_val += sub_mantto
if "depreciacion" in base_conceptos: base_val += sub_dep
if "seguros" in base_conceptos:      base_val += sub_seg
if "viaticos" in base_conceptos:     base_val += float(viaticos_mxn or 0.0)
if "permisos" in base_conceptos:     base_val += sub_permiso
if "def" in base_conceptos:          base_val += sub_def
if "custodia" in base_conceptos:     base_val += sub_custodia
if "tag" in base_conceptos:          base_val += sub_tag
if trabajador_sel and "conductor" in base_conceptos:
    base_val += float(subtotal_conductor or 0.0)

# ===============================
# 14) FINANCIAMIENTO
# ===============================
tasa = float(PARAMS["financiamiento"]["tasa_anual"] or 0.0)
dias_cobro = int(PARAMS["financiamiento"]["dias_cobro"] or 30)
sub_fin = base_val * tasa * (dias_cobro / 360.0)
def _fin_body(show: bool) -> SectionBodyResult:
    rows = [
        ("Tasa anual", f"{tasa*100:.2f}%"),
        ("Días de cobro", f"{dias_cobro}"),
        ("Base considerada", f"${base_val:,.2f}"),
    ]
    if show:
        st.write(f"**Tasa anual:** {tasa*100:.2f}% · **Días de cobro:** {dias_cobro}")
        st.write(f"**Base considerada:** ${base_val:,.2f}")
    rows.append(("Total financiamiento", f"${sub_fin:,.2f}"))
    return SectionBodyResult(total=sub_fin, breakdown=rows)

financiamiento_section = section("FINANCIAMIENTO", sub_fin, _fin_body)
section_outputs.append(financiamiento_section)

# ===============================
# 15) OVERHEAD
# ===============================
pct_ov = float(PARAMS["overhead"]["pct_overhead"] or 0.0)
sub_ov = base_val * pct_ov
def _ov_body(show: bool) -> SectionBodyResult:
    rows = [
        ("Overhead %", f"{pct_ov*100:.2f}%"),
        ("Base considerada", f"${base_val:,.2f}"),
    ]
    if show:
        st.write(f"**Overhead %:** {pct_ov*100:.2f}%")
        st.write(f"**Base considerada:** ${base_val:,.2f}")
    rows.append(("Total overhead", f"${sub_ov:,.2f}"))
    return SectionBodyResult(total=sub_ov, breakdown=rows)

overhead_section = section("OVERHEAD", sub_ov, _ov_body)
section_outputs.append(overhead_section)

# ===============================
# 16) UTILIDAD
# ===============================
pct_ut = float(PARAMS["utilidad"]["pct_utilidad"] or 0.0)
sub_ut = (base_val + sub_ov) * pct_ut
def _ut_body(show: bool) -> SectionBodyResult:
    rows = [
        ("Utilidad %", f"{pct_ut*100:.2f}%"),
        ("Base + Overhead", f"${(base_val+sub_ov):,.2f}"),
    ]
    if show:
        st.write(f"**Utilidad %:** {pct_ut*100:.2f}%")
        st.write(f"**Base + Overhead:** ${(base_val+sub_ov):,.2f}")
    rows.append(("Total utilidad", f"${sub_ut:,.2f}"))
    return SectionBodyResult(total=sub_ut, breakdown=rows)

utilidad_section = section("UTILIDAD", sub_ut, _ut_body)
section_outputs.append(utilidad_section)

# ===============================
# TOTAL GENERAL + PDF
# ===============================
total_general = (
    float(subtotal_peajes or 0.0)
    + float(subtotal_combustible or 0.0)
    + float(subtotal_conductor or 0.0)
    + float(viaticos_mxn or 0.0)
    + sub_tag + sub_def + sub_llantas + sub_mantto + sub_dep + sub_seg + sub_permiso + sub_custodia
    + sub_fin + sub_ov + sub_ut
)

with total_banner:
    st.markdown(
        f"""
        <div class='total-banner'>
            <span class='total-banner-label'>Total general</span>
            <span class='total-banner-value'>${total_general:,.2f}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

pdf_sections = [(sec.title, sec.total, sec.breakdown) for sec in section_outputs]

# PDF
pdf_builder = get_pdf_builder()

try:
    df_pdf = df.copy()
    df_pdf["excluir"] = df_pdf["idx"].apply(lambda i: is_excluded(int(i)))

    trabajador_sel_row = trabajador_sel  # dict o None
    costo_diario_pdf = 0.0
    anios_pdf = 1
    if trabajador_sel_row:
        _, _, costo_diario_pdf, anios_pdf = costo_diario_trabajador_auto(trabajador_sel_row)

    dias_est_pdf = float(dias_est or 1.0)
    km_totales_pdf = float(km_totales or 0.0)
    rendimiento_pdf = float(rendimiento or 1.0)
    precio_litro_pdf = float(precio_litro or 0.0)
    litros_estimados_pdf = float(litros_estimados if rendimiento_pdf > 0 else 0.0)

    subtotal_peajes_pdf = float(subtotal_peajes or 0.0)
    subtotal_combustible_pdf = float(subtotal_combustible or 0.0)
    subtotal_conductor_pdf = float(dias_est_pdf * costo_diario_pdf) if trabajador_sel_row else 0.0
    viaticos_mxn_pdf = float(viaticos_mxn or 0.0)

    horas_totales = dias_est_pdf * 9.0

    # Usa el MISMO total que muestras en la pantalla
    total_pdf = float(total_general or 0.0)

    pdf_bytes = pdf_builder(
        ruta_nombre=ruta_nombre,
        origen=origin_label,
        destino=destination_label,
        clase=clase,
        df_peajes=df_pdf[["plaza", "tarifa", "excluir"]],
        total_original=float(df["tarifa"].sum()),
        total_ajustado=subtotal_peajes_pdf,
        km_totales=km_totales_pdf, rendimiento=rendimiento_pdf, precio_litro=precio_litro_pdf,
        litros=litros_estimados_pdf, costo_combustible=subtotal_combustible_pdf,
        total_general=total_pdf,
        trabajador_sel=trabajador_sel_row,
        esquema_conductor="Por día (método Edwin)" if trabajador_sel_row else "Sin conductor",
        horas_estimadas=horas_totales,
        costo_conductor=subtotal_conductor_pdf,
        tarifa_dia=float(costo_diario_pdf) if trabajador_sel_row else None,
        horas_por_dia=None,
        tarifa_hora=None, tarifa_km=None,
        viaticos_mxn=viaticos_mxn_pdf,
        section_breakdowns=pdf_sections,
    )

    st.download_button(
        "📄 DESCARGAR COSTEO (PDF)",
        data=pdf_bytes,
        file_name=f"costeo_{normalize_name(origin_label)}_{normalize_name(destination_label)}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
except Exception as e:
    st.warning(f"No se pudo generar PDF: {e}")
