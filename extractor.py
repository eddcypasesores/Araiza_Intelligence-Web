# -*- coding: utf-8 -*-
"""Herramientas de extraccion para CFDI y estados Banamex."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, Tuple, List
import re

import pandas as pd
import pdfplumber


# ============================================================
# CFDI 3.3 / 4.0
# ============================================================
def _to_decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _detect_cfdi_ns(root: ET.Element) -> str:
    if root.tag.startswith("{") and "}Comprobante" in root.tag:
        return root.tag.split("}")[0][1:]
    return "http://www.sat.gob.mx/cfd/4"


def parse_cfdi_bytes(data: bytes) -> Dict[str, Any]:
    tree = ET.fromstring(data)
    ns_cfdi = _detect_cfdi_ns(tree)
    ns = {
        "cfdi": ns_cfdi,
        "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    }

    comprobante = tree
    fecha = comprobante.attrib.get("Fecha", "")

    emisor = comprobante.find("cfdi:Emisor", ns)
    rfc_emisor = emisor.attrib.get("Rfc", "") if emisor is not None else ""
    nombre_emisor = emisor.attrib.get("Nombre", "") if emisor is not None else ""

    receptor = comprobante.find("cfdi:Receptor", ns)
    regimen_receptor = receptor.attrib.get("RegimenFiscalReceptor", "") if receptor is not None else ""

    timbre = comprobante.find(".//cfdi:Complemento/tfd:TimbreFiscalDigital", ns)
    uuid = timbre.attrib.get("UUID", "") if timbre is not None else ""

    conceptos = comprobante.findall("cfdi:Conceptos/cfdi:Concepto", ns)
    total_concepto = sum(_to_decimal(c.attrib.get("Importe")) for c in conceptos)

    traslados_globales = comprobante.findall("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", ns)
    if traslados_globales:
        total_traslados = sum(_to_decimal(t.attrib.get("Importe")) for t in traslados_globales)
    else:
        traslados_concepto = comprobante.findall(
            "cfdi:Conceptos/cfdi:Concepto/cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado",
            ns,
        )
        total_traslados = sum(_to_decimal(t.attrib.get("Importe")) for t in traslados_concepto)

    return {
        "Fecha": fecha,
        "RFC Emisor": rfc_emisor,
        "Nombre Emisor": nombre_emisor,
        "UUID": uuid,
        "cfdi:Concepto Importe": float(total_concepto),
        "cfdi:Traslado Importe": float(total_traslados),
        "RegimenFiscalReceptor": regimen_receptor,
    }


def parse_cfdi_many(files: Iterable[Tuple[str, bytes]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _, blob in files:
        try:
            rows.append(parse_cfdi_bytes(blob))
        except Exception:
            continue
    return rows


# ============================================================
# Extractor Banamex
# ============================================================
MESES_BANAMEX = {
    "ENE": "01",
    "FEB": "02",
    "MAR": "03",
    "ABR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AGO": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DIC": "12",
}

RE_FECHA_LINEA = re.compile(r"^(\d{2})\s([A-Z]{3})\b")
RE_ANIO_1 = re.compile(r"ESTADO DE CUENTA AL .*? (\d{4})", re.IGNORECASE)
RE_ANIO_2 = re.compile(r"RESUMEN DEL: .*? (\d{4})", re.IGNORECASE)
RE_RFC_FLEX = re.compile(r"\b([A-Z\u00D1&]{3,4}\d{6}[A-Z0-9]{2,3})\b")
RE_RASTREO_1 = re.compile(r"CLAVE\s+RASTREO\s+([A-Z0-9\-\/]+)", re.IGNORECASE)
RE_RASTREO_2 = re.compile(r"RASTREO[:\s]+([A-Z0-9\-\/]+)", re.IGNORECASE)
RE_REF_TOKEN = re.compile(r"\bREF\.?\s*([A-Z0-9\-\/]+)", re.IGNORECASE)
RE_MONTOS_ITER = re.compile(r"(-?\d{1,3}(?:,\d{3})*(?:\.\d{2}))")
DET_SPLIT_RE = re.compile(
    r"\b(REFERENCIA|CTA\.?|CUENTA|FOLIO|CLABE|AUT\.?|AUTORIZACION|CLAVE\s+RASTREO|RASTREO)\b",
    re.IGNORECASE,
)
BENEF_CLASS = "[A-Z\u00D1\u00C1\u00C9\u00CD\u00D3\u00DA0-9&.,/\\-\\s]{5,}"


def _norm_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _limpia_detalle(detalle: str) -> str:
    detalle = _norm_spaces(detalle)
    detalle = DET_SPLIT_RE.split(detalle, maxsplit=1)[0]
    detalle = re.sub(r"\b\d{7,}\b", "", detalle)
    detalle = detalle.strip(" -.,/")
    return _norm_spaces(detalle)


def _limpia_ruido_concepto(texto: str) -> str:
    texto = texto.upper()
    texto = re.sub(r"\bFECHA\b|\bCONCEPTO\b|\bRETIROS\b|\bDEPOSITOS\b|\bSALDO\b", " ", texto)
    texto = re.sub(r"000180\.B10CHDA008\.OD\.\d{4}\.\d{2}", " ", texto)
    texto = re.sub(r"ESTADO DE CUENTA AL.*?\d{4}", " ", texto)
    texto = re.sub(r"PAGINA:\s*\d+\s*DE\s*\d+", " ", texto)
    return _norm_spaces(texto)


def _extraer_beneficiario(texto: str) -> str:
    texto_up = texto.upper()
    patrones = [
        rf"(?:POR\s+ORDEN\s+DE)[:\s\-]*({BENEF_CLASS})",
        rf"(?:ORDEN\s+DE)[:\s\-]*({BENEF_CLASS})",
        rf"(?:AL\s+BENEF\.?)[:\s\-]*({BENEF_CLASS})",
        rf"(?:BENEF(?:\.|\-|ICIARIO)?)[:\s\-]*({BENEF_CLASS})",
        rf"(?:RECIBIDO\s+DE)[:\s\-]*({BENEF_CLASS})",
        rf"(?:PAGO\s+INTERBANCARIO\s+A|PAGO\s+A|TRANSFERENCIA\s+A|SPEI\s+A)[:\s\-]*({BENEF_CLASS})",
    ]
    for pattern in patrones:
        match = re.search(pattern, texto_up, re.IGNORECASE)
        if match:
            cand = _limpia_detalle(match.group(1))
            if cand:
                return cand

    if "NOMINA" in texto_up:
        return "PAGO DE NOMINA"
    if "CARGO GLOBAL" in texto_up:
        return "CARGO GLOBAL"
    if "IVA COMISION" in texto_up:
        return "IVA COMISION"
    if "COMISION" in texto_up:
        return "COMISION"
    if "PAGO DE SERVICIO" in texto_up:
        return _limpia_detalle(texto_up.split("PAGO DE SERVICIO", 1)[-1])
    if "TRASPASO" in texto_up:
        return "TRASPASO"
    return ""


def _clasifica_cargo_abono(texto_original: str) -> str:
    texto = _limpia_ruido_concepto(texto_original)
    abono_tokens = [
        "PAGO RECIBIDO",
        "SPEI RECIBIDO",
        "DEPOSITO EFECTIVO",
        "DEPOSITO EN EFECTIVO",
        "DEP EN EFECTIVO",
        "DEP EFECTIVO",
        "DEPOSITO MIXTO",
        "DEP MIXTO",
        "DEP CHEQUE",
        "DEPOSITO CHEQUE",
        "DEPOSITO DE SUC",
        "DEPOSITO SUC",
        "DEPOSITO EN SUC",
        "DEPOSITO VENTANILLA",
        "DEP VENTANILLA",
    ]
    if any(token in texto for token in abono_tokens) or re.search(r"\bDEPOSITO\b", texto):
        return "ABONO"

    cargo_tokens = [
        "PAGO INTERBANCARIO A",
        "TRANSFERENCIA A",
        "PAGO A TERCEROS",
        "PAGO DE SERVICIO",
        "CARGO GLOBAL",
        "DOMI ",
        "DOMICILIAC",
        "COMPRA",
        "RETIRO",
        " AL BENEF",
        " A BENEF",
    ]
    if any(token in texto for token in cargo_tokens):
        return "CARGO"

    if "TRASPASO" in texto and " DE " in texto and " A " not in texto:
        return "ABONO"
    if "TRASPASO" in texto and " A " in texto and " DE " not in texto:
        return "CARGO"
    return "CARGO"


def _rightmost_amounts(linea: str) -> List[str]:
    matches = list(RE_MONTOS_ITER.finditer(linea))
    if not matches:
        return []
    matches_sorted = sorted(matches, key=lambda match: match.start())
    if len(matches_sorted) >= 2:
        return [matches_sorted[-2].group(1), matches_sorted[-1].group(1)]
    return [matches_sorted[-1].group(1)]


def _procesar_bloque_banamex(bloque: List[str], anio: str | None) -> Dict[str, Any] | None:
    if not bloque:
        return None

    match = RE_FECHA_LINEA.match(bloque[0])
    if not match:
        return None
    dia, mes_abrev = match.groups()
    mes_num = MESES_BANAMEX.get(mes_abrev.upper(), "01")
    fecha = f"{dia}/{mes_num}/{anio}" if anio else f"{dia}/{mes_num}/XXXX"

    concepto_completo = _norm_spaces(" ".join(bloque))
    texto_upper = concepto_completo.upper()

    rfc = ""
    match_rfc = RE_RFC_FLEX.search(concepto_completo)
    if match_rfc:
        rfc = match_rfc.group(1)

    operacion = ""
    match_rastreo = RE_RASTREO_1.search(concepto_completo) or RE_RASTREO_2.search(concepto_completo)
    if match_rastreo:
        operacion = match_rastreo.group(1).strip()
    else:
        match_ref = RE_REF_TOKEN.search(concepto_completo)
        if match_ref:
            operacion = match_ref.group(1).strip()

    referencia = ""
    match_ref2 = RE_REF_TOKEN.search(concepto_completo)
    if match_ref2:
        referencia = match_ref2.group(1)
    else:
        match_largo = re.search(r"\b(\d{10,})\b", concepto_completo)
        if match_largo:
            referencia = match_largo.group(1)

    beneficiario = _extraer_beneficiario(concepto_completo)
    detalle = beneficiario or _limpia_detalle(concepto_completo)

    retiro = deposito = saldo = 0.0
    for linea in reversed(bloque):
        montos = _rightmost_amounts(linea)
        if not montos:
            continue

        if len(montos) >= 2:
            monto = float(montos[0].replace(",", ""))
            saldo = float(montos[1].replace(",", ""))
        else:
            monto = float(montos[0].replace(",", ""))

        etiqueta = _clasifica_cargo_abono(texto_upper)
        if etiqueta == "ABONO":
            deposito = monto
        else:
            retiro = monto
        break

    return {
        "Fecha": fecha,
        "Detalle": detalle,
        "Referencia": referencia,
        "Beneficiario": beneficiario,
        "RFC": rfc,
        "Operacion": operacion,
        "Cargo": retiro,
        "Abono": deposito,
        "Saldo": saldo,
        "Comprobacion": "",
        "Concepto": concepto_completo,
    }


def extraer_datos_banamex_formato_final(pdf_path: str) -> pd.DataFrame:
    movimientos: List[Dict[str, Any]] = []
    bloque: List[str] = []
    anio_detectado: str | None = None
    saldo_anterior: float | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            raw_text = page.extract_text() or ""
            lines = [ln.strip() for ln in raw_text.split("\n") if ln is not None]

            if anio_detectado is None:
                for ln in lines:
                    match_anio = RE_ANIO_1.search(ln) or RE_ANIO_2.search(ln)
                    if match_anio:
                        anio_detectado = match_anio.group(1)
                        break

            if saldo_anterior is None:
                for ln in lines:
                    if "SALDO ANTERIOR" in ln.upper():
                        match_saldo = RE_MONTOS_ITER.search(ln)
                        if match_saldo:
                            saldo_anterior = float(match_saldo.group(1).replace(",", ""))
                            break

            for ln in lines:
                if RE_FECHA_LINEA.match(ln):
                    if bloque:
                        mov = _procesar_bloque_banamex(bloque, anio_detectado)
                        if mov:
                            movimientos.append(mov)
                        bloque = []
                bloque.append(ln)

    if bloque:
        mov = _procesar_bloque_banamex(bloque, anio_detectado)
        if mov:
            movimientos.append(mov)

    df = pd.DataFrame(movimientos)

    if saldo_anterior is not None:
        fila = {
            "Fecha": "",
            "Detalle": "SALDO ANTERIOR",
            "Referencia": "",
            "Beneficiario": "",
            "RFC": "",
            "Operacion": "",
            "Cargo": 0.0,
            "Abono": 0.0,
            "Saldo": saldo_anterior,
            "Comprobacion": saldo_anterior,
            "Concepto": "SALDO ANTERIOR",
        }
        df = pd.concat([pd.DataFrame([fila]), df], ignore_index=True)

    columnas_finales = [
        "Fecha",
        "Detalle",
        "Referencia",
        "Beneficiario",
        "RFC",
        "Operacion",
        "Cargo",
        "Abono",
        "Saldo",
        "Comprobacion",
        "Concepto",
    ]
    for columna in columnas_finales:
        if columna not in df.columns:
            df[columna] = "" if columna not in {"Cargo", "Abono", "Saldo", "Comprobacion"} else 0.0
    return df[columnas_finales]
