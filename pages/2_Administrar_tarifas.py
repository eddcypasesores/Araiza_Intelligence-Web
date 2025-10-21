import pandas as pd
import streamlit as st

from utils import _cols_trabajadores
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

if st.session_state["rol"] != "admin":
    st.error("🚫 No tienes permiso para acceder a esta página.")
    st.stop()


from core.db import get_conn, ensure_schema, get_usuario, set_usuario_trabajador

st.set_page_config(page_title="Admin tarifas", layout="wide")
conn = get_conn(); ensure_schema(conn)

st.header("🛠️ Modificación de precios de casetas")
vias = pd.read_sql_query("SELECT id,nombre FROM vias ORDER BY nombre", conn)
if vias.empty:
    st.info("Crea primero vías y plazas en tu ETL.")
else:
    via_nombre = st.selectbox("Vía", vias["nombre"].tolist())
    via_id = int(vias.loc[vias["nombre"]==via_nombre,"id"].iloc[0])

    plazas = pd.read_sql_query("SELECT id AS plaza_id, nombre AS plaza FROM plazas WHERE via_id=? ORDER BY orden", conn, params=(via_id,))
    if plazas.empty:
        st.info("Esta vía no tiene plazas.")
    else:
        plaza_nombre = st.selectbox("Plaza", plazas["plaza"].tolist())
        plaza_id = int(plazas.loc[plazas["plaza"]==plaza_nombre,"plaza_id"].iloc[0])

        tarifas = pd.read_sql_query("SELECT clase,tarifa_mxn FROM plaza_tarifas WHERE plaza_id=? ORDER BY clase", conn, params=(plaza_id,))
        clases = ["MOTO","AUTOMOVIL","B2","B3","B4","T2","T3","T4","T5","T6","T7","T8","T9"]
        falt = [c for c in clases if c not in tarifas["clase"].tolist()]
        if falt:
            tarifas = pd.concat([tarifas, pd.DataFrame({"clase": falt, "tarifa_mxn": [0.0]*len(falt)})], ignore_index=True)
        tarifas = tarifas.sort_values("clase").reset_index(drop=True)

        edited = st.data_editor(
            tarifas, use_container_width=True, hide_index=True,
            column_config={
                "clase": st.column_config.TextColumn("Clase", disabled=True),
                "tarifa_mxn": st.column_config.NumberColumn("Tarifa (MXN)", format="%.2f"),
            },
            key="editor_admin_tarifas",
        )

        if st.button("💾 Guardar cambios", type="primary"):
            cur = conn.cursor()
            for _, r in edited.iterrows():
                        u = (r.get("usuario") or "").strip()
                        p = (r.get("contrasena") or "")
                        rol_ui = r.get("Tipo de usuario") or "Calculadora de costos"
                        rol_bd = "admin" if rol_ui == "Administrador" else "operador"

                        # Validación mínima usuario
                        if not u or not p:
                            st.error("Usuario y Contraseña son obligatorios en todas las filas.")
                            continue

                        # Upsert usuario
                        cur.execute("""
                            INSERT INTO usuarios(username, password, rol)
                            VALUES (?,?,?)
                            ON CONFLICT(username) DO UPDATE SET
                            password=excluded.password,
                            rol=excluded.rol
                        """, (u, p, rol_bd))

                        # Datos trabajador
                        nombres = (r.get("nombres") or "").strip()
                        ap_pat = (r.get("apellido_paterno") or "").strip()
                        ap_mat = (r.get("apellido_materno") or "").strip()
                        rol_trab = (r.get("rol_trabajador") or "").strip()
                        numeco = (r.get("numero_economico") or "").strip()
                        fec = (r.get("fecha_registro") or "").strip()
                        saldia = float(r.get("salario_diario") or 0.0)
                        edad_val = int(r.get("edad") or 0)

                        if all([nombres, ap_pat, ap_mat, rol_trab, numeco, fec]) and saldia > 0:
                            cols = _cols_trabajadores(conn)

                            nombre_legacy = f"{nombres} {ap_pat} {ap_mat}".strip()
                            salario_mensual_legacy = saldia * 30.4
                            imss_pct = 0.41
                            carga_social_pct = 0.05
                            aguinaldo_dias = 15.0
                            prima_vacacional_pct = 0.25
                            horas_por_dia = 9.0
                            dias_laborales_mes = 26.0

                            col_names = [
                                "nombres","apellido_paterno","apellido_materno","edad","rol_trabajador",
                                "numero_economico","fecha_registro","salario_diario"
                            ]
                            values = [
                                nombres, ap_pat, ap_mat, edad_val, rol_trab,
                                numeco, fec, saldia
                            ]

                            if "nombre" in cols:
                                col_names.append("nombre"); values.append(nombre_legacy)
                            if "salario_mensual" in cols:
                                col_names.append("salario_mensual"); values.append(salario_mensual_legacy)
                            if "imss_pct" in cols:
                                col_names.append("imss_pct"); values.append(imss_pct)
                            if "carga_social_pct" in cols:
                                col_names.append("carga_social_pct"); values.append(carga_social_pct)
                            if "aguinaldo_dias" in cols:
                                col_names.append("aguinaldo_dias"); values.append(aguinaldo_dias)
                            if "prima_vacacional_pct" in cols:
                                col_names.append("prima_vacacional_pct"); values.append(prima_vacacional_pct)
                            if "horas_por_dia" in cols:
                                col_names.append("horas_por_dia"); values.append(horas_por_dia)
                            if "dias_laborales_mes" in cols:
                                col_names.append("dias_laborales_mes"); values.append(dias_laborales_mes)

                            placeholders = ",".join(["?"]*len(col_names))
                            cols_sql = ",".join(col_names)
                            set_sql = ", ".join([f"{c}=excluded.{c}" for c in col_names if c != "numero_economico"])

                            cur.execute(f"""
                                INSERT INTO trabajadores({cols_sql})
                                VALUES ({placeholders})
                                ON CONFLICT(numero_economico) DO UPDATE SET
                                {set_sql}
                            """, values)

                            # Vincular 1:1
                            uid = get_usuario(conn, u)[0]
                            tid = cur.execute("SELECT id FROM trabajadores WHERE numero_economico=?", (numeco,)).fetchone()[0]
                            set_usuario_trabajador(conn, u, tid)

            conn.commit()
            st.success("Tarifas actualizadas ✅")
