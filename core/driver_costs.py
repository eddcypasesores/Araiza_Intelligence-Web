# core/driver_costs.py
import pandas as pd
from datetime import datetime, date

# =========================
# Catálogo de trabajadores (solo campos nuevos)
# =========================
def read_trabajadores(conn) -> pd.DataFrame:
    """
    Devuelve el catálogo de trabajadores con los campos nuevos.
    Si las columnas no existen (instalaciones viejas), vendrán como NULL.
    """
    sql = """
    SELECT
      id,
      COALESCE(nombres,'')               AS nombres,
      COALESCE(apellido_paterno,'')      AS apellido_paterno,
      COALESCE(apellido_materno,'')      AS apellido_materno,
      COALESCE(edad, 0)                  AS edad,
      COALESCE(rol_trabajador,'')        AS rol_trabajador,
      COALESCE(numero_economico,'')      AS numero_economico,
      COALESCE(fecha_registro, DATE('now')) AS fecha_registro,
      COALESCE(salario_diario, 0.0)      AS salario_diario
    FROM trabajadores
    ORDER BY nombres, apellido_paterno, apellido_materno
    """
    df = pd.read_sql_query(sql, conn)
    # Nombre completo de conveniencia
    df["nombre_completo"] = (
        df["nombres"].astype(str).str.strip() + " " +
        df["apellido_paterno"].astype(str).str.strip() + " " +
        df["apellido_materno"].astype(str).str.strip()
    ).str.replace(r"\s+", " ", regex=True).str.strip()
    return df


# =========================
# Días de vacaciones por antigüedad (tabla LFT simplificada)
# =========================
def dias_vacaciones_por_anios(anios: int) -> int:
    """Tabla de vacaciones según antigüedad (mismo criterio que ya usabas)."""
    if anios <= 1: return 12
    if anios == 2: return 14
    if anios == 3: return 16
    if anios == 4: return 18
    if anios == 5: return 20
    if 6 <= anios <= 10: return 22
    if 11 <= anios <= 15: return 24
    if 16 <= anios <= 20: return 26
    if 21 <= anios <= 25: return 28
    return 30  # 26-30 o más


# =========================
# Antigüedad automática (desde fecha_registro)
# =========================
def calcular_antiguedad(fecha_registro: str) -> int:
    """Devuelve años completos desde la fecha de registro hasta hoy (>=1)."""
    try:
        d = datetime.strptime(str(fecha_registro), "%Y-%m-%d").date()
    except Exception:
        return 1
    hoy = date.today()
    anios = hoy.year - d.year - ((hoy.month, hoy.day) < (d.month, d.day))
    return max(int(anios), 1)


# =========================
# MÉTODO EDWIN — ÚNICO OFICIAL
# =========================
def costo_diario_metodo_edwin(
    salario_diario: float,
    anios_trabajados: int,
    pct_imss: float = 0.41,
    pct_sar: float = 0.02,
    pct_infonavit: float = 0.05
):
    """
    Retorna (mano_obra_dia, impuestos_dia, costo_total_dia):

      salario_anual      = salario_diario * 365
      aguinaldo          = salario_diario * 15
      prima_vacacional   = 0.25 * (salario_diario * dias_vacaciones(anios))
      total_recibido     = salario_anual + aguinaldo + prima_vacacional
      mano_obra_dia      = total_recibido / 365

      imss               = pct_imss * mano_obra_dia
      sar                = pct_sar  * mano_obra_dia
      infonavit          = pct_infonavit * mano_obra_dia
      impuestos_dia      = (imss + sar + infonavit) / 365   # según tu implementación

      costo_total_dia    = mano_obra_dia + impuestos_dia
    """
    salario_diario = float(salario_diario or 0.0)
    anios = int(anios_trabajados or 1)

    dias_vac = dias_vacaciones_por_anios(anios)
    salario_anual = salario_diario * 365.0
    aguinaldo = salario_diario * 15.0
    prima_vac = 0.25 * (salario_diario * dias_vac)
    total_recibido = salario_anual + aguinaldo + prima_vac

    mano_obra_dia = total_recibido / 365.0

    imss = pct_imss * mano_obra_dia
    sar = pct_sar * mano_obra_dia
    infonavit = pct_infonavit * mano_obra_dia
    impuestos_dia = (imss + sar + infonavit) / 365.0

    costo_total_dia = mano_obra_dia + impuestos_dia
    return float(mano_obra_dia), float(impuestos_dia), float(costo_total_dia)


def costo_diario_trabajador_auto(row: dict):
    """
    Calcula el costo diario empresa usando SOLO el método Edwin,
    con salario_diario (campo nuevo) y antigüedad desde fecha_registro.
    Devuelve (mano_obra_dia, impuestos_dia, costo_total_dia, anios_antiguedad)
    """
    salario_diario = float(row.get("salario_diario", 0) or 0)
    fecha_registro = row.get("fecha_registro", str(date.today()))
    anios = calcular_antiguedad(fecha_registro)

    mano_obra_dia, impuestos_dia, costo_total_dia = costo_diario_metodo_edwin(
        salario_diario=salario_diario,
        anios_trabajados=anios
    )

    return mano_obra_dia, impuestos_dia, costo_total_dia, anios
