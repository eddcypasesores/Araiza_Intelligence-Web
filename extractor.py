# -*- coding: utf-8 -*-
"""
Extractor CFDI 4.0/3.3 -> Fila agregada por XML:
Fecha, RFC Emisor, Nombre Emisor, UUID, cfdi:Concepto Importe (suma),
cfdi:Traslado Importe (preferencia total a nivel Comprobante; si no existe, suma por concepto),
RegimenFiscalReceptor
"""
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
from typing import Dict, Any, Iterable, Tuple

def _to_decimal(x: str) -> Decimal:
    try:
        return Decimal(x)
    except (InvalidOperation, TypeError):
        return Decimal("0")

def _detect_cfdi_ns(root: ET.Element) -> str:
    """Regresa el namespace CFDI detectado en el documento (3.3 o 4.0)."""
    if root.tag.startswith("{") and "}Comprobante" in root.tag:
        return root.tag.split("}")[0][1:]
    # fallback comunes
    return "http://www.sat.gob.mx/cfd/4"

def parse_cfdi_bytes(data: bytes) -> Dict[str, Any]:
    """
    Parsea un CFDI (XML bytes) y devuelve un dict con los campos solicitados (agregados por comprobante).
    Compatible con CFDI 4.0 y 3.3.
    """
    tree = ET.fromstring(data)
    ns_cfdi = _detect_cfdi_ns(tree)
    ns = {
        "cfdi": ns_cfdi,
        "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    }

    comprobante = tree  # <cfdi:Comprobante>
    # --- Campos base ---
    fecha = comprobante.attrib.get("Fecha", "")

    emisor = comprobante.find("cfdi:Emisor", ns)
    rfc_emisor = emisor.attrib.get("Rfc", "") if emisor is not None else ""
    nombre_emisor = emisor.attrib.get("Nombre", "") if emisor is not None else ""

    receptor = comprobante.find("cfdi:Receptor", ns)
    regimen_receptor = receptor.attrib.get("RegimenFiscalReceptor", "") if receptor is not None else ""

    tfd = comprobante.find(".//cfdi:Complemento/tfd:TimbreFiscalDigital", ns)
    uuid = tfd.attrib.get("UUID", "") if tfd is not None else ""

    # --- Suma de importes de conceptos ---
    conceptos = comprobante.findall("cfdi:Conceptos/cfdi:Concepto", ns)
    total_concepto_importe = sum(_to_decimal(c.attrib.get("Importe")) for c in conceptos)

    # --- Impuestos trasladados ---
    # Preferimos los traslados globales (evita duplicar si el PAC ya totalizó)
    traslados_globales = comprobante.findall("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", ns)
    if traslados_globales:
        total_traslados = sum(_to_decimal(t.attrib.get("Importe")) for t in traslados_globales)
    else:
        # Si no hay global, sumamos por concepto
        traslados_concepto = comprobante.findall(
            "cfdi:Conceptos/cfdi:Concepto/cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", ns
        )
        total_traslados = sum(_to_decimal(t.attrib.get("Importe")) for t in traslados_concepto)

    return {
        "Fecha": fecha,
        "RFC Emisor": rfc_emisor,
        "Nombre Emisor": nombre_emisor,
        "UUID": uuid,
        "cfdi:Concepto Importe": float(total_concepto_importe),   # para que Excel lo vea como número
        "cfdi:Traslado Importe": float(total_traslados),
        "RegimenFiscalReceptor": regimen_receptor,
    }

def parse_cfdi_many(files: Iterable[Tuple[str, bytes]]):
    """
    Recibe iterable de (filename, bytes) y regresa lista de dicts.
    Ignora archivos que no son XML válido.
    """
    rows = []
    for fname, blob in files:
        try:
            row = parse_cfdi_bytes(blob)
            rows.append(row)
        except Exception:
            # Si un XML viene malformado, simplemente lo omitimos
            continue
    return rows
