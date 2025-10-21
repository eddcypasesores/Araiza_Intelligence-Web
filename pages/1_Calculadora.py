# pages/1_Calculadora.py — Costos de traslado (15 secciones con diseño unificado + CSS externo)
import math
import pandas as pd
import streamlit as st
from pathlib import Path

# --- Utilidades / Proyecto
from core.utils import inject_css, is_excluded, set_excluded, normalize_name
from core.db import get_conn, ensure_schema, get_active_version_id
from core.rutas import load_routes, plazas_catalog, find_subsequence_between
from core.tarifas import tarifa_por_plaza
from core.pdf import build_pdf_cotizacion
from core.driver_costs import read_trabajadores, costo_diario_trabajador_auto
from core.params import read_params

# ===============================
# Configuración de página + CSS
# ===============================
st.set_page_config(page_title="Costos de traslado", layout="wide", initial_sidebar_state="expanded")
# Inyectar CSS SIEMPRE (evita que se pierda tras reruns)
inject_css("styles.css")

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

# ===============================
# Helpers de assets / UI
# ===============================
APP_DIR = Path(__file__).resolve().parent
ASSET_DIRS = [APP_DIR, APP_DIR / "assets", APP_DIR.parent / "assets", APP_DIR.parent / "static"]

def resolve_asset(fname: str) -> str | None:
    for d in ASSET_DIRS:
        p = (d / fname).resolve()
        if p.exists():
            return str(p)
    return None

def _icon_html(icon: str | None = None, icon_img: str | None = None) -> str:
    """Devuelve HTML del icono: imagen (si hay) o emoji/texto."""
    if icon_img:
        p = resolve_asset(icon_img)
        if p:
            return f"<img src='file://{p}' class='icon-img' alt='icon'/>"
    return f"<span class='icon'>{icon or ''}</span>"

def section(title: str, icon: str | None, total_value: float, body_fn=None, icon_img: str | None = None):
    """Sección con encabezado, expander opcional y 'pill' de total a la derecha."""
    st.markdown("<div class='section'>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='section-head'>{_icon_html(icon=icon, icon_img=icon_img)}"
        f"<span class='title'>{title}</span></div>",
        unsafe_allow_html=True,
    )
    if body_fn:
        with st.expander("Desglose / cálculo", expanded=False):
            body_fn()
    st.markdown(
        f"<div class='total-right'><div class='total-pill'>${float(total_value or 0):,.2f}</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

# ===============================
# Encabezado + Barra superior
# ===============================
st.markdown("<div class='hero-title'>COSTOS DE TRASLADO</div>", unsafe_allow_html=True)
st.caption(f"Conectado como **{st.session_state['usuario']}** · Rol: **{st.session_state['rol']}**")

clases = ["MOTO","AUTOMOVIL","B2","B3","B4","T2","T3","T4","T5","T6","T7","T8","T9"]
default_idx = clases.index("T5")

bc1, bc2, bc3, bc4 = st.columns([1.2, 1.2, 1.2, 0.8])
with bc1:
    origen = st.selectbox("ORIGEN", PLAZAS, key="top_origen")
with bc2:
    usar_parada = st.checkbox("AGREGAR PARADA", value=False)
    parada = st.selectbox("PARADA (OPCIONAL)", PLAZAS, key="top_parada", disabled=not usar_parada)
with bc3:
    destino = st.selectbox("DESTINO", PLAZAS, key="top_destino")
with bc4:
    clase = st.selectbox("CLASE", clases, index=default_idx, key="top_clase")

def compute_route_df_multi():
    """Calcula ruta (origen→parada→destino si aplica) y devuelve df de casetas/tarifas."""
    if usar_parada and parada:
        f1 = find_subsequence_between(ROUTES, origen, parada)
        f2 = find_subsequence_between(ROUTES, parada, destino)
        if not f1 or not f2:
            return None, None
        name1, sec1 = f1
        name2, sec2 = f2
        ruta_nombre = f"{name1}  →  {name2}"
        if sec1 and sec2 and sec1[-1] == sec2[0]:
            secuencia = sec1 + sec2[1:]
        else:
            secuencia = sec1 + sec2
    else:
        f = find_subsequence_between(ROUTES, origen, destino)
        if not f: return None, None
        ruta_nombre, secuencia = f

    rows = [{"idx": i, "plaza": c, "tarifa": tarifa_por_plaza(conn, c, clase)} for i, c in enumerate(secuencia)]
    return ruta_nombre, pd.DataFrame(rows)

# Limpiar exclusiones si cambian selecciones
sel = (origen, destino, clase, usar_parada, parada if usar_parada else None)
if st.session_state.get("last_sel_top") != sel:
    for k in list(st.session_state.keys()):
        if str(k).startswith("cb_"):
            del st.session_state[k]
    st.session_state["last_sel_top"] = sel

ruta_nombre, df = compute_route_df_multi()
if not ruta_nombre:
    st.error("❌ No se encontró una ruta que contenga las casetas en ese orden.")
    st.stop()

# Reset exclusiones si cambia la ruta
if st.session_state.get("route_name") != ruta_nombre:
    st.session_state["route_name"] = ruta_nombre
    st.session_state.setdefault("excluded_set", set())
    st.session_state["excluded_set"].clear()

st.caption(f"Ruta detectada: **{ruta_nombre}**")

# ===============================
# 1) PEAJE
# ===============================
def _peaje_body():
    st.markdown("<span class='small-note'>Marca la caseta para excluirla del total.</span>", unsafe_allow_html=True)
    COLS = [0.6, 7.0, 2.4]
    h1, h2, h3 = st.columns(COLS)
    h2.markdown("**PLAZA**"); h3.markdown("**TARIFA (MXN)**")
    for _, row in df.iterrows():
        idx = int(row["idx"])
        c1x, c2x, c3x = st.columns(COLS)
        default_checked = bool(st.session_state.get(f"cb_{idx}", is_excluded(idx)))
        checked = c1x.checkbox("", key=f"cb_{idx}", value=default_checked, label_visibility="hidden")
        set_excluded(idx, bool(checked))
        c2x.markdown(row["plaza"])
        c3x.markdown(f"${float(row['tarifa']):,.2f}")

def _total_peajes(df_):
    return sum(0 if is_excluded(int(r["idx"])) else float(r["tarifa"]) for _, r in df_.iterrows())

subtotal_peajes = _total_peajes(df)
section("PEAJE", None, subtotal_peajes, _peaje_body, icon_img="peaje_card.png")

# ===============================
# 2) DIESEL
# ===============================
c1, c2, c3, c4 = st.columns([1.0, 1.0, 1.0, 1.0])
with c1: distancia_km = st.number_input("DISTANCIA (KM)", min_value=0.0, value=0.0, step=1.0)
with c2: rendimiento  = st.number_input("RENDIMIENTO (KM/L)", min_value=0.1, value=30.0, step=0.1)
with c3: precio_litro = st.number_input("PRECIO POR LITRO ($/L)", min_value=0.0, value=26.5, step=0.1)
with c4: viaje_redondo = st.checkbox("VIAJE REDONDO", value=False)

km_totales = float(distancia_km or 0.0) * (2 if viaje_redondo else 1)
litros_estimados = (km_totales / float(rendimiento or 1.0)) if float(rendimiento or 0) > 0 else 0.0
subtotal_combustible = float(litros_estimados) * float(precio_litro or 0.0)

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

# ===============================
# 4) Parámetros versionados y cargos
# ===============================
vid = get_active_version_id(conn)
PARAMS = read_params(conn, vid)

# Apoyos comunes
peajes_ajustados = float(subtotal_peajes or 0.0)
km_totales = float(km_totales or 0.0)
rendimiento = float(rendimiento or 1.0)
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
section("LLANTAS", "🛞", sub_llantas, _llantas_body)

# ===============================
# 6) MANTENIMIENTO
# ===============================
sub_mantto = km_totales * float(PARAMS["costos_km"]["costo_mantto_km"] or 0.0)
def _mantto_body():
    st.write(f"Costo por km: ${PARAMS['costos_km']['costo_mantto_km']}/km")
    st.write(f"KM: {km_totales:,.2f}")
    st.write(f"Total: ${sub_mantto:,.2f}")
section("MANTENIMIENTO", "🧰", sub_mantto, _mantto_body)

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
section("DEPRECIACIÓN", "📉", sub_dep, _dep_body)

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
section("SEGUROS", "🛡️", sub_seg, _seg_body)

# ===============================
# 9) VIÁTICOS (entrada + sección)
# ===============================
viaticos_mxn = st.number_input("VIÁTICOS (MXN)", min_value=0.0, value=0.0, step=50.0, format="%.2f", key="viat_input_main")
def _viat_body():
    st.write(f"Monto fijo ingresado: ${viaticos_mxn:,.2f}")
section("VIÁTICOS", "💵", viaticos_mxn, _viat_body)

# ===============================
# 10) CUSTODIA
# ===============================
sub_custodia = km_totales * float(PARAMS["otros"]["custodia_km"] or 0.0)
def _cust_body():
    st.write(f"Costo por km: ${PARAMS['otros']['custodia_km']}/km")
    st.write(f"KM: {km_totales:,.2f}")
    st.write(f"Total: ${sub_custodia:,.2f}")
section("CUSTODIA", "🚓", sub_custodia, _cust_body)

# ===============================
# 11) PERMISOS
# ===============================
sub_permiso = float(PARAMS["otros"]["permiso_viaje"] or 0.0)
def _perm_body():
    st.write(f"Permiso por viaje: ${sub_permiso:,.2f}")
section("PERMISOS", "📄", sub_permiso, _perm_body)

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
section("DEF", "💧", sub_def, _def_body)

# ===============================
# 13) COMISIÓN TAG
# ===============================
pct_tag = float(PARAMS["tag"]["pct_comision_tag"] or 0.0)
sub_tag = peajes_ajustados * pct_tag
def _tag_body():
    st.write(f"Comisión TAG %: {pct_tag*100:.2f}%")
    st.write(f"Base peajes: ${peajes_ajustados:,.2f}")
    st.write(f"Total: ${sub_tag:,.2f}")
section("COMISIÓN TAG", "🏷️", sub_tag, _tag_body)

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
section("FINANCIAMIENTO", "💳", sub_fin, _fin_body)

# ===============================
# 15) OVERHEAD
# ===============================
pct_ov = float(PARAMS["overhead"]["pct_overhead"] or 0.0)
sub_ov = base_val * pct_ov
def _ov_body():
    st.write(f"Overhead %: {pct_ov*100:.2f}%")
    st.write(f"Base: ${base_val:,.2f}")
    st.write(f"Total: ${sub_ov:,.2f}")
section("OVERHEAD", "🏢", sub_ov, _ov_body)

# ===============================
# 16) UTILIDAD
# ===============================
pct_ut = float(PARAMS["utilidad"]["pct_utilidad"] or 0.0)
sub_ut = (base_val + sub_ov) * pct_ut
def _ut_body():
    st.write(f"Utilidad %: {pct_ut*100:.2f}%")
    st.write(f"Base + Overhead: ${(base_val+sub_ov):,.2f}")
    st.write(f"Total: ${sub_ut:,.2f}")
section("UTILIDAD", "📈", sub_ut, _ut_body)

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

# Sección “TOTAL GENERAL”
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
    total_pdf = subtotal_peajes_pdf + subtotal_combustible_pdf + subtotal_conductor_pdf + viaticos_mxn_pdf

    pdf_bytes = build_pdf_cotizacion(
        ruta_nombre=ruta_nombre, origen=origen, destino=destino, clase=clase,
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
        viaticos_mxn=viaticos_mxn_pdf
    )

    st.download_button(
        "📄 DESCARGAR COTIZACIÓN (PDF)",
        data=pdf_bytes,
        file_name=f"cotizacion_{normalize_name(origen)}_{normalize_name(destino)}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
except Exception as e:
    st.warning(f"No se pudo generar PDF: {e}")
