import streamlit as st

st.set_page_config(page_title="Inicio | Costos de Rutas", layout="wide")

# Bloqueo si no hay sesión
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

usuario = st.session_state["usuario"]
rol = st.session_state["rol"]

st.title("👋 Bienvenido")
st.subheader(f"Hola, **{usuario}**")
st.caption(f"Tu rol: **{rol}**")

st.write("Usa el menú de la izquierda para navegar por las páginas.")

# Atajos útiles según rol
if rol == "admin":
    st.success("Tienes permisos de administrador. Puedes modificar tarifas y el catálogo de trabajadores.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Ir a Calculadora", use_container_width=True):
            st.switch_page("pages/1_Calculadora.py")
    with c2:
        if st.button("Administrar Tarifas", use_container_width=True):
            st.switch_page("pages/2_Administrar_tarifas.py")
    with c3:
        if st.button("Trabajadores", use_container_width=True):
            st.switch_page("pages/3_Trabajadores.py")
    with c4:
        if st.button("Parámetros", use_container_width=True):
            st.switch_page("pages/5_Parametros.py")

else:
    st.info("Eres operador. Puedes usar la calculadora.")
    if st.button("Ir a Calculadora", use_container_width=True):
        st.switch_page("pages/1_Calculadora.py")

# Botón de salir
st.divider()
if st.button("Cerrar sesión", type="secondary"):
    for k in ("usuario", "rol", "excluded_set", "route", "show_detail"):
        if k in st.session_state:
            del st.session_state[k]
    try:
        st.switch_page("app.py")
    except Exception:
        st.experimental_rerun()
