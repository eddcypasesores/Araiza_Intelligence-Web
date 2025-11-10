"""Extractor de estados de cuenta Inbursa."""

from __future__ import annotations

import math
import re
from typing import List

import pandas as pd
import pdfplumber

AMOUNT_RX = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
DATE_START_RX = re.compile(r"^(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.\s*(\d{2})\s+(.*)$", re.IGNORECASE)

MESES = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
}


def _clean_concept(text: str) -> str:
    return AMOUNT_RX.sub("", text).replace("  ", " ").strip()


def _parse_amount(txt: str) -> float:
    return float(txt.replace(",", ""))


def extraer_inbursa(pdf_file) -> pd.DataFrame:
    rows: List[list] = []
    prev_saldo: float | None = None
    year = 2000

    with pdfplumber.open(pdf_file) as pdf:
        first_page = pdf.pages[0].extract_text() or ""
        match = re.search(r"PERIODO\s+Del\s+\d{2}\s+\w+\.\s+(\d{4})", first_page, re.IGNORECASE)
        if match:
            year = int(match.group(1))

        last_idx = None
        current: dict | None = None

        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [line.strip() for line in text.splitlines() if line.strip()]

            for line in lines:
                upper = line.upper()

                if "RESUMEN DEL CFDI" in upper:
                    current = None
                    break
                if re.search(r"FECHA\s+REFERENCIA\s+CONCEPTO\s+CARGOS\s+ABONOS\s+SALDO", line, re.IGNORECASE):
                    continue
                if upper.startswith("PÁGINA") or upper.startswith("PAGINA"):
                    continue

                match_date = DATE_START_RX.match(line)
                if match_date:
                    current = None
                    mon = match_date.group(1).upper()[:3]
                    day = int(match_date.group(2))
                    rest = match_date.group(3).strip()
                    month = MESES.get(mon, 1)
                    fecha = f"{year:04d}-{month:02d}-{day:02d}"

                    ref = ""
                    concepto = rest
                    match_ref = re.match(r"^(\d{7,})\s+(.*)$", rest)
                    if match_ref:
                        ref, concepto = match_ref.group(1), match_ref.group(2)

                    amounts = [m.group(0) for m in AMOUNT_RX.finditer(line)]

                    if "BALANCE INICIAL" in concepto.upper() and amounts:
                        saldo = _parse_amount(amounts[-1])
                        prev_saldo = saldo
                        rows.append([fecha, ref, "BALANCE INICIAL", math.nan, math.nan, saldo])
                        last_idx = len(rows) - 1
                        continue

                    if len(amounts) >= 2:
                        movimiento = _parse_amount(amounts[0])
                        saldo = _parse_amount(amounts[-1])
                        cargo = abono = math.nan
                        if prev_saldo is None:
                            if any(
                                token in concepto.upper()
                                for token in ["DEPOSITO", "ABONO", "INTERESES", "DEPOSITO SPEI"]
                            ):
                                abono = movimiento
                            else:
                                cargo = movimiento
                        else:
                            abono = movimiento if saldo > prev_saldo else math.nan
                            cargo = movimiento if saldo <= prev_saldo else math.nan

                        rows.append([fecha, ref, _clean_concept(concepto), cargo, abono, saldo])
                        last_idx = len(rows) - 1
                        prev_saldo = saldo
                        continue

                        current = None

                    current = {"FECHA": fecha, "REFERENCIA": ref, "CONCEPTO": concepto}
                    continue

                if re.fullmatch(r"\d{7,}", line.replace(" ", "")):
                    number = line.replace(" ", "")
                    if current is not None:
                        prev_ref = current.get("REFERENCIA", "")
                        current["REFERENCIA"] = f"{prev_ref} {number}".strip() if prev_ref else number
                    elif last_idx is not None:
                        prev_ref = rows[last_idx][1]
                        rows[last_idx][1] = f"{prev_ref} {number}".strip() if prev_ref else number
                    continue

                amounts = [m.group(0) for m in AMOUNT_RX.finditer(line)]
                if len(amounts) >= 2 and current is not None:
                    movimiento = _parse_amount(amounts[0])
                    saldo = _parse_amount(amounts[-1])
                    cargo = abono = math.nan
                    if prev_saldo is None:
                        cargo = movimiento
                    else:
                        abono = movimiento if saldo > prev_saldo else math.nan
                        cargo = movimiento if saldo <= prev_saldo else math.nan

                    rows.append(
                        [
                            current["FECHA"],
                            current["REFERENCIA"],
                            _clean_concept(current["CONCEPTO"]),
                            cargo,
                            abono,
                            saldo,
                        ]
                    )
                    last_idx = len(rows) - 1
                    prev_saldo = saldo
                    current = None
                    continue

                bad_starts = (
                    "SI DESEA",
                    "EL NOMBRE DEL BENEFICIARIO",
                    "CLAVE DE RASTREO. SIRVE",
                    "TIPO COMPROBANTE",
                    "EXPEDIDO EN:",
                    "RECEPTOR(",
                    "R.F.C. DEL PROVEEDOR",
                    "ESTE DOCUMENTO ES UNA REPRESENTACIÓN IMPRESA",
                )
                if current is not None:
                    current["CONCEPTO"] = (current["CONCEPTO"] + " " + line).strip()
                elif rows:
                    upper_line = line.upper()
                    if not AMOUNT_RX.search(line) and not DATE_START_RX.match(line):
                        if not upper_line.startswith(bad_starts) and not any(
                            token in upper_line
                            for token in [
                                "BANCO INBURSA, S.A.",
                                "REGIMEN FISCAL",
                                "AVENIDA PASEO",
                                "RESUMEN DE SALDOS",
                                "GLOSARIO",
                                "CONSULTAS Y RECLAMACIONES",
                            ]
                        ):
                            rows[-1][2] = (rows[-1][2] + " " + line).strip()

    df = pd.DataFrame(rows, columns=["Fecha", "Referencia", "Concepto", "Cargo", "Abono", "Saldo"])
    if df.empty:
        return df
    df["Cargo"] = pd.to_numeric(df["Cargo"], errors="coerce").fillna(0.0)
    df["Abono"] = pd.to_numeric(df["Abono"], errors="coerce").fillna(0.0)
    df["Saldo"] = pd.to_numeric(df["Saldo"], errors="coerce")
    df["Concepto"] = df["Concepto"].str.replace(r"\s+", " ", regex=True).str.strip()
    return df
