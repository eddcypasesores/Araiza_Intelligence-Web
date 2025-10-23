# pages/1_Calculadora.py — Costos de traslado (layout 2 columnas por sección + iconos en base64)
from __future__ import annotations

import base64
from uuid import uuid4
from types import SimpleNamespace
import pandas as pd
import streamlit as st
from pathlib import Path

# --- Utilidades / Proyecto
from core.utils import inject_css, is_excluded, set_excluded, normalize_name
from core.db import get_conn, ensure_schema, get_active_version_id
from core.config import GOOGLE_MAPS_API_KEY
from core.rutas import (
    load_routes,
    plazas_catalog,
    match_plaza_in_text,
    match_plazas_for_route,
)
from core.tarifas import tarifa_por_plaza
from core.pdf import build_pdf_cotizacion
from core.driver_costs import read_trabajadores, costo_diario_trabajador_auto
from core.params import read_params
from core.maps import GoogleMapsClient, GoogleMapsError

HARDCODED_MAPS_API_KEY = "AIzaSyBqSuQGWucHtypH60GpAAIxJVap76CgRL8"

# ===============================
# Configuración de página + CSS
# ===============================
st.set_page_config(page_title="Costos de traslado", layout="wide", initial_sidebar_state="expanded")
inject_css("styles.css")

# Estilos de refuerzo (sin cajas grises; solo línea azul + layout)
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; }
      .section, .section * { background: transparent !important; box-shadow: none !important; }
      .section { padding: 0 !important; margin: 0 0 .25rem 0 !important; border: none !important; }
      .section-head { display:flex; align-items:center; gap:.5rem; font-weight:800; color:#1e293b; letter-spacing:.2px; margin:.25rem 0; }
      .section-head .title { text-transform:uppercase; font-size:1.25rem; }
      .total-right { display:flex; justify-content:flex-end; margin:.25rem 0 .4rem 0; }
      .total-pill { display:inline-block; padding:.35rem .6rem; border-radius:999px; border:1px solid rgba(37,99,235,.25); min-width:110px; text-align:center; }
      .section-divider { height:0; border:0; border-top:3px solid #2563eb; margin:8px 0 14px 0; opacity:1; }
      [data-testid="stExpander"]{ border:1px solid rgba(15,23,42,.08); background:transparent; }
      [data-testid="stExpander"]>div{ background:transparent !important; }
      .section input[aria-label=""], .section textarea[aria-label=""]{ display:none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===============================
# Seguridad / sesión
# ===============================
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

# ===============================
# Conexión y datos base
# ===============================
conn = get_conn()
ensure_schema(conn)
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

# ===============================
# Helpers de assets / UI
# ===============================
APP_DIR = Path(__file__).resolve().parent

# Lista robusta de ubicaciones posibles de assets
ASSET_DIRS = [
    APP_DIR,                                 # /pages
    APP_DIR / "assets",                       # /pages/assets
    APP_DIR.parent / "assets",                # /assets (raíz)
    APP_DIR.parent / "static",                # /static (raíz)
    Path.cwd() / "assets",                    # CWD/assets (por si el runner cambia)
]

def resolve_asset(fname: str) -> Path | None:
    """
    Devuelve un Path a la imagen del icono sin importar si:
    - pasas sólo el nombre: "peaje_card.png"
    - o pasas una ruta relativa: "assets/peaje_card.png"
    - o una ruta absoluta
    """
    if not fname:
        return None

    p = Path(fname).expanduser().resolve()
    # 1) Si te pasaron una ruta absoluta o una relativa válida, úsala
    if p.exists():
        return p

    # 2) Si fue sólo el nombre o una ruta relativa no válida, busca en carpetas conocidas
    for d in ASSET_DIRS:
        candidate = (d / fname).resolve()
        if candidate.exists():
            return candidate

        # También intenta sólo el nombre del archivo dentro de cada carpeta
        candidate2 = (d / Path(fname).name).resolve()
        if candidate2.exists():
            return candidate2

    return None

def img_to_data_url(path: Path) -> str | None:
    try:
        suffix = path.suffix.lower()
        if suffix in [".png"]: mime = "image/png"
        elif suffix in [".jpg", ".jpeg"]: mime = "image/jpeg"
        elif suffix in [".gif"]: mime = "image/gif"
        elif suffix in [".svg"]: 
            # SVG embebido como texto (no base64) para mejor nitidez
            return f"data:image/svg+xml;utf8,{path.read_text(encoding='utf-8')}"
        else: mime = "application/octet-stream"
        b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None
def section(title: str, icon: str | None, total_value: float | None, body_fn=None, icon_img: str | None = None):
    """
    Layout por sección:
      - Izquierda: título grande + expander (desglose)
      - Derecha: imagen/icono arriba y, debajo, el total (pill) alineado a la derecha
    Devuelve el total utilizado (float).
    """
    st.markdown("<div class='section'>", unsafe_allow_html=True)
    left, right = st.columns([0.68, 0.32], gap="large")

    computed_total = total_value if total_value is not None else 0.0

    with left:
        st.markdown(
            f"<div class='section-head' style='margin-bottom:.25rem'><span class='title'>{title}</span></div>",
            unsafe_allow_html=True,
        )
        if body_fn:
            with st.expander("Desglose / cálculo", expanded=False):
                # Si el body_fn devuelve un número, se toma como total de la sección
                ret = body_fn()
                if isinstance(ret, (int, float)):
                    computed_total = float(ret)

    with right:
        data_url = None
        if icon_img:
            p = resolve_asset(icon_img)
            if p:
                data_url = img_to_data_url(p)

        st.markdown(
            f"<div class='total-right' style='justify-content:flex-end; margin-bottom:.75rem'>"
            f"<div class='total-pill'>${computed_total:,.2f}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if data_url:
            st.markdown(
                f"<div style='display:flex; justify-content:flex-end; margin-bottom:.5rem'>"
                f"<img src='{data_url}' alt='icon' style='max-width:120px; height:auto;'/>"
                f"</div>",
                unsafe_allow_html=True,
            )
        elif icon:
            st.markdown(
                f"<div style='display:flex; justify-content:flex-end; margin-bottom:.5rem'>"
                f"<div style='font-size:54px; line-height:1'>{icon}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    return computed_total


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

# 1) Fila 1: ORIGEN / DESTINO
r1c1, r1c2 = st.columns([1.2, 1.2])
with r1c1:
    origen = autocomplete_input("ORIGEN", "top_origen")
with r1c2:
    destino = autocomplete_input("DESTINO", "top_destino")

# 2) Fila 2: CLASE (tipo de auto)
clases = ["MOTO","AUTOMOVIL","B2","B3","B4","T2","T3","T4","T5","T6","T7","T8","T9"]
default_idx = clases.index("T5")
st.markdown("")  # espacio
cl_col = st.columns([0.9])[0]
with cl_col:
    clase = st.selectbox("CLASE (TIPO DE AUTO)", clases, index=default_idx, key="top_clase")

# 3) Fila 3: Agregar parada (checkbox) + selector visible solo si se activa
st.markdown("")  # espacio
r3c1, r3c2 = st.columns([0.35, 1.05])
with r3c1:
    if "chk_parada" not in st.session_state:
        st.session_state["chk_parada"] = False
    if MANUAL_MODE and st.session_state.get("chk_parada"):
        st.session_state["chk_parada"] = False
    usar_parada = st.checkbox(
        "AGREGAR PARADA",
        key="chk_parada",
        disabled=MANUAL_MODE,
    )
with r3c2:
    if usar_parada:
        parada = autocomplete_input("PARADA (OPCIONAL)", "top_parada")
    else:
        st.session_state.pop("top_parada_query", None)
        st.session_state.pop("top_parada_options", None)
        st.session_state.pop("top_parada_selection", None)
        st.session_state.pop("top_parada_data", None)
        parada = None  # oculto completamente

st.markdown("")  # espacio
opts_c1, _ = st.columns([0.4, 0.6])
with opts_c1:
    if "chk_avoid_tolls" not in st.session_state:
        st.session_state["chk_avoid_tolls"] = False
    if MANUAL_MODE and st.session_state.get("chk_avoid_tolls"):
        st.session_state["chk_avoid_tolls"] = False
    evitar_cuotas = st.checkbox(
        "EVITAR CASETAS (RUTA LIBRE)",
        key="chk_avoid_tolls",
        disabled=MANUAL_MODE,
    )

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
def _peaje_body():
    st.markdown("<span class='small-note'>Marca la caseta para excluirla del total.</span>", unsafe_allow_html=True)
    COLS = [0.6, 7.0, 2.4]
    h1, h2, h3 = st.columns(COLS)
    h2.markdown("**PLAZA**"); h3.markdown("**TARIFA (MXN)**")

    # Pintamos checkboxes y vamos actualizando el set de excluidas
    if df.empty:
        st.caption("No se detectaron casetas para la ruta seleccionada.")
        st.session_state["subtotal_peajes"] = 0.0
        return 0.0

    for _, row in df.iterrows():
        idx = int(row["idx"])
        c1x, c2x, c3x = st.columns(COLS)
        default_checked = bool(st.session_state.get(f"cb_{idx}", is_excluded(idx)))
        checked = c1x.checkbox("", key=f"cb_{idx}", value=default_checked, label_visibility="hidden")
        set_excluded(idx, bool(checked))
        c2x.markdown(row["plaza"])
        c3x.markdown(f"${float(row['tarifa']):,.2f}")

    # Calcular el subtotal con el estado ACTUAL
    subtotal = 0.0
    for _, r in df.iterrows():
        if not is_excluded(int(r["idx"])):
            subtotal += float(r["tarifa"])
    # Guardamos por si quieres leerlo de session_state en otro lado
    st.session_state["subtotal_peajes"] = subtotal
    return subtotal

subtotal_peajes = section("PEAJE", None, None, _peaje_body, icon_img="peaje_card.png")

# ===============================
# 2) DIESEL
# ===============================
diesel_params = PARAMS.get("diesel", {}) if isinstance(PARAMS, dict) else {}
rendimiento = float(diesel_params.get("rendimiento_km_l") or 0.0)
precio_litro = float(diesel_params.get("precio_litro") or 0.0)

c1, c2 = st.columns([1.0, 1.0])
distancia_km_val = float(st.session_state.get("maps_distance_km") or 0.0)
with c1:
    st.number_input(
        "DISTANCIA (KM)",
        min_value=0.0,
        value=distancia_km_val,
        step=0.1,
        format="%.2f",
        key="distance_display_km",
        disabled=True,
    )
with c2:
    viaje_redondo = st.checkbox("VIAJE REDONDO", value=False)

km_totales = float(distancia_km_val or 0.0) * (2 if viaje_redondo else 1)
litros_estimados = (km_totales / rendimiento) if rendimiento > 0 else 0.0
subtotal_combustible = float(litros_estimados) * precio_litro

def _diesel_body():
    st.write(f"**KM totales:** {km_totales:,.2f}")
    st.write(f"**Rendimiento:** {rendimiento:,.2f} km/L")
    st.write(f"**Litros estimados:** {litros_estimados:,.2f} L")
    st.write(f"**Precio por litro:** ${precio_litro:,.2f}")

section("DIESEL", None, subtotal_combustible, _diesel_body, icon_img="diesel_card.png")

# ===============================
# 3) MANO DE OBRA (método Edwin)
# ===============================
trab_df = read_trabajadores(conn)
trab_opc = ["(Sin conductor)"] + [f"{r['nombre_completo']} — {r['numero_economico']}" for _, r in trab_df.iterrows()]
cT1, cT2 = st.columns([1.6, .8])
with cT1: trab_show = st.selectbox("SELECCIONAR CONDUCTOR", trab_opc, index=0)
with cT2:
    dias_sugeridos = max(1.0, round((km_totales or 0.0)/600.0, 1))
    dias_est = st.number_input("DÍAS ESTIMADOS", min_value=1.0, step=0.5, value=dias_sugeridos)

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

def _mo_body():
    if not trabajador_sel:
        st.caption("Selecciona un conductor para ver el desglose.")
        return
    st.write(f"**Antigüedad estimada:** {anios} año(s)")
    st.write(f"**Salario diario base:** ${float(trabajador_sel.get('salario_diario',0)):,.2f}")
    st.write(f"**Aguinaldo (prorrateado):** incluido")
    st.write(f"**Prima vacacional (prorrateada):** incluida")
    st.write(f"**IMSS / Carga social (día):** ${impuestos_dia:,.2f}")
    st.write(f"**Costo diario total:** ${costo_diario_total:,.2f}")
    st.write(f"**Días estimados:** {dias_est}")
    st.write(f"**Total mano de obra:** ${subtotal_conductor:,.2f}")

section("MANO DE OBRA", None, subtotal_conductor, _mo_body, icon_img="conductor_card.png")

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
def _llantas_body():
    st.write(f"Costo por km: ${PARAMS['costos_km']['costo_llantas_km']}/km")
    st.write(f"KM: {km_totales:,.2f}")
    st.write(f"Total: ${sub_llantas:,.2f}")

section("LLANTAS", None, sub_llantas, _mo_body, icon_img="llanta_card.png")


# ===============================
# 6) MANTENIMIENTO
# ===============================
sub_mantto = km_totales * float(PARAMS["costos_km"]["costo_mantto_km"] or 0.0)
def _mantto_body():
    st.write(f"Costo por km: ${PARAMS['costos_km']['costo_mantto_km']}/km")
    st.write(f"KM: {km_totales:,.2f}")
    st.write(f"Total: ${sub_mantto:,.2f}")
section("MANTENIMIENTO", None, sub_mantto, _mo_body, icon_img="mantenimiento_card.png")

# ===============================
# 7) DEPRECIACIÓN
# ===============================
dep = PARAMS["depreciacion"]
dep_anual = (float(dep["costo_adq"]) - float(dep["valor_residual"])) / max(int(dep["vida_anios"]),1)
dep_km = dep_anual / max(int(dep["km_anuales"]),1)
sub_dep = dep_km * km_totales
def _dep_body():
    st.write(f"Costo adquisición: ${float(dep['costo_adq']):,.2f}")
    st.write(f"Valor residual: ${float(dep['valor_residual']):,.2f}")
    st.write(f"Vida: {int(dep['vida_anios'])} años · KM/año: {int(dep['km_anuales'])}")
    st.write(f"Depreciación por km: ${dep_km:,.4f}")
    st.write(f"Total: ${sub_dep:,.2f}")
section("DEPRECIACIÓN", None, sub_dep, _mo_body, icon_img="depreciacion_card.png")

# ===============================
# 8) SEGUROS
# ===============================
seg = PARAMS["seguros"]
seg_km = float(seg["prima_anual"]) / max(int(seg["km_anuales"]),1)
sub_seg = seg_km * km_totales
def _seg_body():
    st.write(f"Prima anual: ${float(seg['prima_anual']):,.2f} · KM/año: {int(seg['km_anuales'])}")
    st.write(f"Seguro por km: ${seg_km:,.4f}")
    st.write(f"Total: ${sub_seg:,.2f}")
section("SEGUROS", None, sub_seg, _mo_body, icon_img="seguros_card.png")


# ===============================
# 9) VIÁTICOS
# ===============================
viaticos_mxn = st.number_input("VIÁTICOS (MXN)", min_value=0.0, value=0.0, step=50.0, format="%.2f", key="viat_input_main")
def _viat_body():
    st.write(f"Monto fijo ingresado: ${viaticos_mxn:,.2f}")
section("Viaticos", None, viaticos_mxn, _mo_body, icon_img="viaticos_card.png")

# ===============================
# 10) CUSTODIA
# ===============================
sub_custodia = km_totales * float(PARAMS["otros"]["custodia_km"] or 0.0)
def _cust_body():
    st.write(f"Costo por km: ${PARAMS['otros']['custodia_km']}/km")
    st.write(f"KM: {km_totales:,.2f}")
    st.write(f"Total: ${sub_custodia:,.2f}")
section("CUSTODIA", None, sub_custodia, _mo_body, icon_img="custodia_card.png")

# ===============================
# 11) PERMISOS
# ===============================
sub_permiso = float(PARAMS["otros"]["permiso_viaje"] or 0.0)
def _perm_body():
    st.write(f"Permiso por viaje: ${sub_permiso:,.2f}")
section("PERMISOS", None, sub_permiso, _mo_body, icon_img="permiso_card.png")

# ===============================
# 12) DEF
# ===============================
pct_def = float(PARAMS["def"]["pct_def"] or 0.0)
precio_def = float(PARAMS["def"]["precio_def_litro"] or 0.0)
litros_def = litros_estimados * pct_def
sub_def = litros_def * precio_def
def _def_body():
    st.write(f"% DEF vs diésel: {pct_def*100:.2f}%")
    st.write(f"Litros DEF: {litros_def:,.2f} · Precio DEF/L: ${precio_def:,.2f}")
    st.write(f"Total: ${sub_def:,.2f}")
section("DEF", None, sub_def, _mo_body, icon_img="def_card.png")

# ===============================
# 13) COMISIÓN TAG
# ===============================
pct_tag = float(PARAMS["tag"]["pct_comision_tag"] or 0.0)
sub_tag = peajes_ajustados * pct_tag
def _tag_body():
    st.write(f"Comisión TAG %: {pct_tag*100:.2f}%")
    st.write(f"Base peajes: ${peajes_ajustados:,.2f}")
    st.write(f"Total: ${sub_tag:,.2f}")
section("COMISIÓN TAG", None, sub_tag, _mo_body, icon_img="tag_card.png")

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
def _fin_body():
    st.write(f"Tasa anual: {tasa*100:.2f}% · Días de cobro: {dias_cobro}")
    st.write(f"Base: ${base_val:,.2f}")
    st.write(f"Total: ${sub_fin:,.2f}")
section("FINANCIAMIENTO", None, sub_fin, _mo_body, icon_img="financiamiento_card.png")

# ===============================
# 15) OVERHEAD
# ===============================
pct_ov = float(PARAMS["overhead"]["pct_overhead"] or 0.0)
sub_ov = base_val * pct_ov
def _ov_body():
    st.write(f"Overhead %: {pct_ov*100:.2f}%")
    st.write(f"Base: ${base_val:,.2f}")
    st.write(f"Total: ${sub_ov:,.2f}")
section("OVERHEAD", None, sub_ov, _mo_body, icon_img="overhead_card.png")

# ===============================
# 16) UTILIDAD
# ===============================
pct_ut = float(PARAMS["utilidad"]["pct_utilidad"] or 0.0)
sub_ut = (base_val + sub_ov) * pct_ut
def _ut_body():
    st.write(f"Utilidad %: {pct_ut*100:.2f}%")
    st.write(f"Base + Overhead: ${(base_val+sub_ov):,.2f}")
    st.write(f"Total: ${sub_ut:,.2f}")
section("UTILIDAD", None, sub_ut, _mo_body, icon_img="utilidad_card.png")

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

st.markdown("<div class='section'>", unsafe_allow_html=True)
st.markdown("<div class='section-head'><span class='title'>TOTAL GENERAL</span></div>", unsafe_allow_html=True)
st.markdown(
    f"<div class='total-right'><div class='total-pill' "
    f"style='background:#c8e6c9;color:#0f3313;border-color:rgba(27,94,32,.25)'>"
    f"${total_general:,.2f}</div></div>",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# PDF
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

    # --- construir lista de "OTROS CONCEPTOS" para el PDF ---
    otros_conceptos_pdf = [
        ("LLANTAS",       float(sub_llantas or 0.0)),
        ("MANTENIMIENTO", float(sub_mantto or 0.0)),
        ("DEPRECIACIÓN",  float(sub_dep or 0.0)),
        ("SEGUROS",       float(sub_seg or 0.0)),
        ("CUSTODIA",      float(sub_custodia or 0.0)),
        ("PERMISOS",      float(sub_permiso or 0.0)),
        ("DEF",           float(sub_def or 0.0)),
        ("COMISIÓN TAG",  float(sub_tag or 0.0)),
        ("FINANCIAMIENTO",float(sub_fin or 0.0)),
        ("OVERHEAD",      float(sub_ov or 0.0)),
        ("UTILIDAD",      float(sub_ut or 0.0)),
    ]

    # Usa el MISMO total que muestras en la pantalla
    total_pdf = float(total_general or 0.0)

    pdf_bytes = build_pdf_cotizacion(
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
        otros_conceptos=otros_conceptos_pdf,  # <-- nuevo parámetro
    )

    st.download_button(
        "📄 DESCARGAR COTIZACIÓN (PDF)",
        data=pdf_bytes,
        file_name=f"cotizacion_{normalize_name(origin_label)}_{normalize_name(destination_label)}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
except Exception as e:
    st.warning(f"No se pudo generar PDF: {e}")