"""Extractor de estados de cuenta HSBC."""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from datetime import datetime
from typing import BinaryIO, Dict, List, Optional, Tuple, Union

import pandas as pd
import pdfplumber

try:
    import fitz  # type: ignore
except ImportError:  # pragma: no cover - dependencia opcional
    fitz = None

try:
    import pytesseract
except ImportError:  # pragma: no cover - dependencia opcional
    pytesseract = None

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError:  # pragma: no cover - dependencia opcional
    Image = None

if pytesseract is not None:
    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd  # type: ignore[attr-defined]

    DIGIT_CHAR_MAP = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "S": "5", "B": "8"})
else:
    DIGIT_CHAR_MAP = {}


class OCRUnavailableError(RuntimeError):
    """Se lanza cuando se requiere OCR pero falta una dependencia."""


PDFSource = Union[str, Path, bytes, bytearray, BinaryIO]

AMOUNT_RX = re.compile(r"\(?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?")
YEAR_RX = re.compile(r"\b(20\d{2})\b")
REF_RX = re.compile(r"\b\d{6,}\b")
PERIODO_RX = re.compile(r"PERIODO\s+DEL\s+(?P<dia>\d{1,2})/(?P<mes>\d{1,2})/(?P<anio>\d{2,4})", re.IGNORECASE)
PERIODO_RANGE_RX = re.compile(
    r"PERIODO\s+DEL\s+(?P<dia1>\d{1,2})/(?P<mes1>\d{1,2})/(?P<anio1>\d{2,4})\s+AL\s+(?P<dia2>\d{1,2})/(?P<mes2>\d{1,2})/(?P<anio2>\d{2,4})",
    re.IGNORECASE,
)
DAY_ONLY_RX = re.compile(r"^(?P<dia>\d{1,2})(?=\s)")
NUMERIC_TOKEN_RX = re.compile(r"[0-9OolISB]{2,}|[OolISB][0-9]+|[0-9]+[OolISB]+")
DATE_PATTERNS = [
    re.compile(r"^(?P<dia>\d{1,2})/(?P<mes>\d{1,2})/(?P<anio>\d{2,4})"),
    re.compile(r"^(?P<dia>\d{1,2})-(?P<mes>\d{1,2})-(?P<anio>\d{2,4})"),
    re.compile(r"^(?P<dia>\d{1,2})\s+(?P<mes_txt>[A-Z]{3})\s*(?P<anio>\d{2,4})?", re.IGNORECASE),
    re.compile(r"^(?P<mes_txt>[A-Z]{3})\s+(?P<dia>\d{1,2})\s*(?P<anio>\d{2,4})?", re.IGNORECASE),
]

MONTHS = {
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
MONTH_NAMES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}
MONTH_NAMES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

ABONO_KEYWORDS = (
    "ABONO",
    "DEPOSITO",
    "PAGO RECIBIDO",
    "TRANSFERENCIA RECIBIDA",
    "SPEI RECIBIDO",
    "INTERESES",
    "DEVOLUCION",
)
CARGO_KEYWORDS = (
    "CARGO",
    "PAGO",
    "TRANSFERENCIA",
    "COMPRA",
    "RETIRO",
    "DOMICILIACION",
    "SPEI ENVIADO",
    "COMISION",
    "IVA",
)

HEADER_TOKENS = ("FECHA", "DESCRIPCION", "DESCRIPCI?N", "DETALLE")
FOOTER_PREFIXES = (
    "PAGINA",
    "P?GINA",
    "HSBC",
    "CONSULTAS",
    "RECLAMACION",
    "RECLAMACI?N",
    "UNE",
    "ATENCION",
    "ATENCI?N",
    "TEL",
    "CENTRO DE ATENCION",
)


def _ensure_pdf_bytes(pdf_file: PDFSource) -> bytes:
    if isinstance(pdf_file, (bytes, bytearray)):
        return bytes(pdf_file)
    if isinstance(pdf_file, (str, Path)):
        return Path(pdf_file).read_bytes()
    if hasattr(pdf_file, "read"):
        data = pdf_file.read()
        try:
            pdf_file.seek(0)
        except Exception:
            pass
        return data
    raise TypeError("Origen de PDF no soportado para la extracción.")


def _init_ocr_doc(pdf_bytes: bytes) -> Tuple[Optional["fitz.Document"], Optional[str]]:
    missing: list[str] = []
    if fitz is None:
        missing.append("PyMuPDF (pymupdf)")
    if pytesseract is None:
        missing.append("pytesseract")
    if Image is None:
        missing.append("Pillow")
    if missing:
        return None, f"Instala {', '.join(missing)} para habilitar el OCR en PDFs escaneados."
    try:
        return fitz.open(stream=pdf_bytes, filetype="pdf"), None  # type: ignore[union-attr]
    except Exception as exc:  # pragma: no cover - error ajeno a la lógica
        return None, f"No se pudo inicializar el motor OCR: {exc}"


def _pixmap_to_image(pixmap: "fitz.Pixmap"):
    if Image is None:
        raise OCRUnavailableError("Pillow es requerido para convertir las páginas a imagen.")
    if hasattr(pixmap, "pil_image"):
        return pixmap.pil_image()  # PyMuPDF >= 1.22
    mode = "RGBA" if pixmap.alpha else "RGB"
    return Image.frombytes(mode, [pixmap.width, pixmap.height], pixmap.samples)


def _preprocess_image(image: "Image.Image") -> "Image.Image":
    gray = image.convert("L")
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
    threshold = int(os.getenv("OCR_THRESHOLD", "150"))
    bw = gray.point(lambda x: 0 if x < threshold else 255, "1")  # type: ignore[arg-type]
    return bw.convert("L")


def _deskew_image(image: "Image.Image") -> "Image.Image":
    if pytesseract is None:
        return image
    try:
        osd = pytesseract.image_to_osd(image, config="--psm 0")
    except Exception:
        return image
    match = re.search(r"Rotate: (\d+)", osd or "")
    if not match:
        return image
    angle = int(match.group(1)) % 360
    if not angle:
        return image
    return image.rotate(-angle, expand=True)


def _prepare_image_for_ocr(pixmap: "fitz.Pixmap") -> "Image.Image":
    image = _pixmap_to_image(pixmap)
    try:
        image = _preprocess_image(image)
        image = _deskew_image(image)
    except Exception:
        # Ante cualquier fallo en el preprocesamiento, regresamos la imagen original.
        pass
    return image


def _normalize_numeric_candidates(text: str) -> str:
    if not DIGIT_CHAR_MAP:
        return text

    def repl(match: re.Match[str]) -> str:
        return match.group(0).translate(DIGIT_CHAR_MAP)

    return NUMERIC_TOKEN_RX.sub(repl, text)


def _normalize_ocr_line(line: str) -> str:
    if not line:
        return ""
    cleaned = line.replace("—", "-").replace("–", "-").replace("‒", "-")
    cleaned = cleaned.replace("¬", " ").replace("•", " ").replace("▪", " ")
    cleaned = re.sub(r"[=_]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = _normalize_numeric_candidates(cleaned)
    cleaned = cleaned.strip(" .")
    return cleaned


def _normalize_ocr_block(text: str) -> str:
    lines = []
    for raw in (text or "").splitlines():
        cleaned = _normalize_ocr_line(raw)
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _normalize_key(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def _extract_word_lines(page) -> List[str]:
    """Extrae líneas usando las coordenadas de pdfplumber para minimizar errores en PDF digitales."""
    try:
        words = page.extract_words(use_text_flow=True, keep_blank_chars=False, y_tolerance=2, x_tolerance=2)
    except Exception:
        return []
    if not words:
        return []
    words = sorted(words, key=lambda w: (round(float(w.get("top", 0))), w.get("x0", 0)))
    lines: List[Dict[str, object]] = []
    for word in words:
        text = (word.get("text") or "").strip()
        if not text:
            continue
        top = float(word.get("top", 0))
        if not lines or abs(top - lines[-1]["top"]) > 2.0:
            lines.append({"top": top, "texts": [text]})
        else:
            lines[-1]["texts"].append(text)
    return [" ".join(line["texts"]) for line in lines if line["texts"]]


def _format_period_label(
    start: Optional[Tuple[int, int, int]], end: Optional[Tuple[int, int, int]]
) -> Optional[str]:
    if not start:
        return None
    end = end or start
    _, start_month, start_year = start
    _, end_month, end_year = end
    start_name = MONTH_NAMES.get(start_month, str(start_month))
    end_name = MONTH_NAMES.get(end_month, str(end_month))
    if start_month == end_month and start_year == end_year:
        return f"{start_name} {start_year}"
    return f"{start_name} {start_year} - {end_name} {end_year}"


SPEI_DATE_RX = re.compile(r"^\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\s+")


def _parse_spei_row(lines: List[str], mode: str) -> Optional[tuple[str, Dict[str, object]]]:
    if not lines:
        return None
    first_line = lines[0].strip()
    fecha_match = re.match(r"(?P<fecha>\d{2}/\d{2}/\d{4})", first_line)
    fecha_val: Optional[datetime.date] = None
    if fecha_match:
        try:
            fecha_val = datetime.strptime(fecha_match.group("fecha"), "%d/%m/%Y").date()
        except ValueError:
            fecha_val = None
    block = " ".join(line.strip() for line in lines if line.strip())
    account_match = re.search(r"\d{10,}", block)
    if not account_match:
        return None
    before = block[: account_match.start()].strip()
    after = block[account_match.end() :].strip()

    before = SPEI_DATE_RX.sub("", before)
    if "*" in before:
        _, participant_section = before.split("*", 1)
    else:
        participant_section = before
    tokens = participant_section.split()
    if not tokens:
        return None
    idx = 0
    while idx < len(tokens):
        normalized = re.sub(r"[^A-Z]", "", tokens[idx].upper())
        if normalized and normalized in PARTICIPANT_TOKENS:
            idx += 1
            continue
        break
    tokens = tokens[idx:]
    name_tokens: List[str] = []
    for token in tokens:
        if any(char.isdigit() for char in token):
            break
        name_tokens.append(token)
    beneficiario = " ".join(name_tokens).title()

    amount_match = re.search(r"\$\s?[\d,]+\.\d{2}", after)
    concept_segment = after[: amount_match.start()].strip() if amount_match else after
    concept_segment = re.sub(r"\s+", " ", concept_segment)
    amount_value: Optional[float] = None
    if amount_match:
        amount_value = _clean_amount(amount_match.group(0))

    if not beneficiario or not concept_segment:
        return None

    entry = {
        "benef": beneficiario,
        "date": fecha_val,
        "amount": amount_value,
    }
    return _normalize_key(concept_segment), entry


def _extract_spei_lookup(
    spei_sections: List[Tuple[str, List[str]]],
) -> Tuple[Dict[str, List[Dict[str, object]]], Dict[str, List[Dict[str, object]]]]:
    enviados: Dict[str, List[Dict[str, object]]] = {}
    recibidos: Dict[str, List[Dict[str, object]]] = {}
    for mode, lines in spei_sections:
        if mode not in {"enviados", "recibidos"} or not lines:
            continue
        current: List[str] = []
        for line in lines:
            if re.match(r"\d{2}/\d{2}/\d{4}", line):
                if current:
                    result = _parse_spei_row(current, mode)
                    if result:
                        key, entry = result
                        target = enviados if mode == "enviados" else recibidos
                        target.setdefault(key, []).append(entry)
                current = [line]
            else:
                current.append(line)
        if current:
            result = _parse_spei_row(current, mode)
            if result:
                key, entry = result
                target = enviados if mode == "enviados" else recibidos
                target.setdefault(key, []).append(entry)
    return enviados, recibidos


def _apply_transfer_labels(
    df: pd.DataFrame,
    lookup_env: Dict[str, List[Dict[str, object]]],
    lookup_rec: Dict[str, List[Dict[str, object]]],
) -> pd.DataFrame:
    if df.empty:
        return df

    def _select_entry(
        entries: List[Dict[str, object]], target_date: Optional[pd.Timestamp], amount: Optional[float]
    ) -> Optional[str]:
        if not entries:
            return None

        def match(entry, check_date: bool, check_amount: bool) -> bool:
            date_ok = True
            amount_ok = True
            if check_date:
                entry_date = entry.get("date")
                date_ok = bool(entry_date and target_date is not None and entry_date == target_date.date())
            if check_amount:
                entry_amount = entry.get("amount")
                amount_ok = bool(
                    entry_amount is not None and amount is not None and abs(float(entry_amount) - float(amount)) <= 1.0
                )
            return date_ok and amount_ok

        for entry in entries:
            if match(entry, True, True):
                return str(entry.get("benef"))
        for entry in entries:
            if match(entry, True, False):
                return str(entry.get("benef"))
        if amount is not None:
            for entry in entries:
                if match(entry, False, True):
                    return str(entry.get("benef"))
        return str(entries[0].get("benef"))

    def adjust(row):
        concepto = row.get("Concepto", "")
        norm = _normalize_key(re.sub(r"^\d+\s+", "", concepto))
        fecha_ts = row.get("_fecha_dt")
        if not isinstance(fecha_ts, pd.Timestamp):
            fecha_ts = pd.to_datetime(row.get("Fecha"), errors="coerce")
        cargo = row.get("Cargo", 0.0) or 0.0
        abono = row.get("Abono", 0.0) or 0.0

        if cargo and lookup_env:
            entries = lookup_env.get(norm)
            if entries:
                benef = _select_entry(entries, fecha_ts, cargo)
                if benef:
                    return f"Transferencia a {benef}"
            upper = concepto.upper()
            if any(token in upper for token in TRANSFER_KEYWORDS):
                for key, entries in lookup_env.items():
                    if key in norm or norm in key:
                        benef = _select_entry(entries, fecha_ts, cargo)
                        if benef:
                            return f"Transferencia a {benef}"
        if abono and lookup_rec:
            entries = lookup_rec.get(norm)
            if entries:
                benef = _select_entry(entries, fecha_ts, abono)
                if benef:
                    return f"Transferencia recibida de {benef}"
            upper = concepto.upper()
            if any(token in upper for token in ("RECIB", "DEPOSITO", "DEPÓSITO", "DEPOSITO", "RECIBIDO")):
                for key, entries in lookup_rec.items():
                    if key in norm or norm in key:
                        benef = _select_entry(entries, fecha_ts, abono)
                        if benef:
                            return f"Transferencia recibida de {benef}"
        return concepto

    df["Concepto"] = df.apply(lambda row: adjust(row), axis=1)
    return df


def _ocr_page_text(doc: "fitz.Document", page_index: int) -> str:
    if fitz is None or pytesseract is None:
        raise OCRUnavailableError("El OCR no está disponible por falta de dependencias.")
    try:
        page = doc.load_page(page_index)
        pixmap = page.get_pixmap(dpi=300)
    except Exception as exc:  # pragma: no cover - dependencias externas
        raise RuntimeError(f"No se pudo preparar la página para OCR: {exc}") from exc

    image = _prepare_image_for_ocr(pixmap)
    lang = os.getenv("TESSERACT_LANG", "spa+eng")
    config = os.getenv("TESSERACT_CONFIG", "--psm 6 --oem 1")
    try:
        text = pytesseract.image_to_string(image, lang=lang, config=config)  # type: ignore[arg-type]
    except pytesseract.TesseractNotFoundError as exc:  # type: ignore[attr-defined]
        raise OCRUnavailableError("Tesseract OCR no está instalado o no se encuentra en el PATH.") from exc
    except pytesseract.TesseractError as exc:
        # Reintenta con idioma por defecto cuando fallan los paquetes de idioma.
        if lang != "":
            try:
                text = pytesseract.image_to_string(image, config=config)  # type: ignore[arg-type]
                return _normalize_ocr_block(text)
            except Exception:
                pass
        raise RuntimeError(f"OCR falló al procesar la página: {exc}") from exc

    return _normalize_ocr_block(text or "")


def _norm_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _clean_amount(value: str) -> float:
    val = value.strip()
    neg = val.startswith("(") and val.endswith(")")
    val = val.strip("()")
    val = val.replace("$", "").replace(",", "")
    if not val:
        return 0.0
    number = float(val)
    return -number if neg else number


def _match_date(line: str):
    for pattern in DATE_PATTERNS:
        match = pattern.match(line)
        if match:
            return match
    return None


def _extract_day_only(line: str) -> Optional[tuple[str, str]]:
    stripped = line.lstrip(" ._~-")
    match = DAY_ONLY_RX.match(stripped)
    if not match:
        return None
    try:
        day_value = int(match.group("dia"))
    except ValueError:
        return None
    if not (1 <= day_value <= 31):
        return None
    rest = stripped[match.end():].strip()
    if not rest:
        return None
    return str(day_value).zfill(2), rest


def _format_date(match, year_hint: Optional[int], month_hint: Optional[int] = None) -> str:
    info = match.groupdict()
    dia = info.get("dia")
    mes = info.get("mes")
    mes_txt = info.get("mes_txt")
    anio = info.get("anio")

    if mes_txt and not mes:
        mes = str(MONTHS.get(mes_txt.upper(), 1)).zfill(2)
    elif mes:
        mes = mes.zfill(2)
    elif month_hint:
        mes = f"{month_hint:02d}"
    else:
        mes = "01"

    if dia:
        dia = dia.zfill(2)
    else:
        dia = "01"

    if anio:
        anio = anio.zfill(4) if len(anio) == 4 else f"20{anio[-2:]}"
    elif year_hint:
        anio = f"{year_hint:04d}"
    else:
        anio = "0000"

    return f"{anio}-{mes}-{dia}"


def _strip_amounts(text: str) -> str:
    return _norm_spaces(AMOUNT_RX.sub(" ", text))


def _extract_reference(text: str) -> str:
    match = REF_RX.search(text)
    return match.group(0) if match else ""


def _classify_by_keywords(text: str, amount: float) -> tuple[float, float]:
    upper = text.upper()
    if any(token in upper for token in ABONO_KEYWORDS):
        return 0.0, amount
    if any(token in upper for token in CARGO_KEYWORDS):
        return amount, 0.0
    if amount < 0:
        return abs(amount), 0.0
    return 0.0, amount


def _finalize_entry(entry: Dict[str, str], prev_saldo: Optional[float]) -> Optional[Dict[str, float]]:
    text = entry.get("text", "")
    if not text:
        return None

    amounts = AMOUNT_RX.findall(text)
    cargo = 0.0
    abono = 0.0
    saldo = prev_saldo if prev_saldo is not None else 0.0

    if amounts:
        saldo = _clean_amount(amounts[-1])
        if len(amounts) >= 3:
            cargo = abs(_clean_amount(amounts[-3]))
            abono = abs(_clean_amount(amounts[-2]))
        elif len(amounts) == 2:
            movimiento = abs(_clean_amount(amounts[0]))
            if prev_saldo is not None:
                if saldo >= prev_saldo:
                    delta = saldo - prev_saldo
                    abono = abs(delta) if delta else movimiento
                else:
                    delta = prev_saldo - saldo
                    cargo = abs(delta) if delta else movimiento
            else:
                cargo, abono = _classify_by_keywords(text, movimiento)
        elif len(amounts) == 1 and entry.get("is_balance") and prev_saldo is None:
            saldo = abs(_clean_amount(amounts[0]))

    concepto = _strip_amounts(text)
    referencia = _extract_reference(concepto)
    if referencia:
        concepto = _norm_spaces(concepto.replace(referencia, ""))

    if not concepto:
        concepto = "MOVIMIENTO"

    concepto = concepto.replace("$", "").strip()
    if not concepto:
        concepto = "MOVIMIENTO"
    raw_text = " | ".join(entry.get("raw_lines", []))
    display_day = entry.get("dia") or entry["fecha"][-2:]

    return {
        "Fecha": display_day,
        "_fecha_iso": entry["fecha"],
        "Referencia": referencia,
        "Concepto": concepto,
        "Cargo": cargo,
        "Abono": abono,
        "Saldo": saldo,
        "LineaDetectada": raw_text,
    }


def extraer_hsbc(pdf_file: PDFSource) -> pd.DataFrame:
    movimientos: List[Dict[str, object]] = []
    pending: Optional[Dict[str, str]] = None
    prev_saldo: Optional[float] = None
    year_hint: Optional[int] = None
    month_hint: Optional[int] = None

    pdf_bytes = _ensure_pdf_bytes(pdf_file)
    pdf_stream = io.BytesIO(pdf_bytes)
    ocr_doc, ocr_error = _init_ocr_doc(pdf_bytes)
    spei_sections: List[Tuple[str, List[str]]] = []
    current_section: Optional[str] = None
    spei_buffer: List[str] = []
    period_start: Optional[Tuple[int, int, int]] = None
    period_end: Optional[Tuple[int, int, int]] = None

    def flush_spei() -> None:
        nonlocal spei_buffer, current_section
        if current_section in {"spei_enviados", "spei_recibidos"} and spei_buffer:
            spei_sections.append((current_section, spei_buffer.copy()))
            spei_buffer = []

    def set_section(section: Optional[str]) -> None:
        nonlocal current_section
        if section != current_section:
            if current_section in {"spei_enviados", "spei_recibidos"}:
                flush_spei()
            current_section = section

    try:
        with pdfplumber.open(pdf_stream) as pdf:
            pages = list(pdf.pages)
            if month_hint is None or year_hint is None:
                for page in pages:
                    head_text = page.extract_text() or ""
                    match_period = PERIODO_RANGE_RX.search(head_text)
                    if match_period:
                        period_start = (
                            int(match_period.group("dia1")),
                            int(match_period.group("mes1")),
                            int(match_period.group("anio1")),
                        )
                        period_end = (
                            int(match_period.group("dia2")),
                            int(match_period.group("mes2")),
                            int(match_period.group("anio2")),
                        )
                        month_hint = month_hint or int(match_period.group("mes1"))
                        year_hint = year_hint or int(match_period.group("anio1"))
                        break
            for page_index, page in enumerate(pages):
                raw_text = page.extract_text() or ""
                used_ocr = False
                if not raw_text:
                    if ocr_doc is None:
                        raise OCRUnavailableError(
                            ocr_error or "Se requiere OCR para procesar este PDF escaneado."
                        )
                    raw_text = _ocr_page_text(ocr_doc, page_index)
                    used_ocr = True
                else:
                    raw_text = _normalize_ocr_block(raw_text)

                page_text = _normalize_ocr_block(raw_text)
                line_source = page_text.splitlines()
                if month_hint is None or year_hint is None:
                    date_hint = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", page_text)
                    if date_hint:
                        if month_hint is None:
                            month_hint = int(date_hint.group(2))
                        if year_hint is None:
                            year_hint = int(date_hint.group(3))

                for raw_line in line_source:
                    normalized_line = _normalize_ocr_line(raw_line)
                    line = _norm_spaces(normalized_line)
                    if not line:
                        continue

                    upper = line.upper()
                    if any(keyword.upper() in upper for keyword in DETAIL_END_PATTERNS):
                        set_section(None)
                        continue
                    if DETAIL_HEADER_RX.search(upper):
                        set_section("detalle")
                        continue
                    if SPEI_HEADER_ENVIADOS_RX.search(upper):
                        set_section("spei_enviados")
                        spei_buffer = []
                        continue
                    if SPEI_HEADER_RECIBIDOS_RX.search(upper):
                        set_section("spei_recibidos")
                        spei_buffer = []
                        continue

                    if year_hint is None:
                        match_year = YEAR_RX.search(line)
                        if match_year:
                            year_hint = int(match_year.group(1))

                    if month_hint is None or year_hint is None:
                        periodo = PERIODO_RX.search(line)
                        if periodo:
                            month_hint = int(periodo.group('mes'))
                            if year_hint is None:
                                year_hint = int(periodo.group('anio')[-4:])

                    if current_section in {"spei_enviados", "spei_recibidos"}:
                        spei_buffer.append(line)
                        continue

                    if current_section != "detalle":
                        continue

                    match = _match_date(line)
                    if match:
                        if pending:
                            row = _finalize_entry(pending, prev_saldo)
                            if row:
                                movimientos.append(row)
                                prev_saldo = row['Saldo']
                        group = match.groupdict()
                        if month_hint is None:
                            if group.get('mes'):
                                month_hint = int(group['mes'])
                            elif group.get('mes_txt'):
                                month_hint = MONTHS.get(group['mes_txt'].upper(), month_hint)
                        fecha = _format_date(match, year_hint, month_hint)
                        rest = _norm_spaces(line[match.end():])
                        pending = {
                            'fecha': fecha,
                            'dia': group.get('dia', '').zfill(2) if group.get('dia') else None,
                            'text': rest,
                            'is_balance': 'SALDO' in rest.upper(),
                            'raw_lines': [raw_line],
                        }
                    else:
                        day_info = _extract_day_only(line)
                        if day_info and (month_hint is not None or year_hint is not None):
                            if pending:
                                row = _finalize_entry(pending, prev_saldo)
                                if row:
                                    movimientos.append(row)
                                    prev_saldo = row['Saldo']
                            dia, rest = day_info
                            if month_hint is None:
                                month_hint = 1
                            if year_hint is None:
                                year_hint = datetime.now().year
                            fecha = f"{year_hint:04d}-{month_hint:02d}-{dia}"
                            pending = {
                                'fecha': fecha,
                                'dia': dia,
                                'text': rest,
                                'is_balance': 'SALDO' in rest.upper(),
                                'raw_lines': [raw_line],
                            }
                        elif pending:
                            if any(upper.startswith(prefix) for prefix in FOOTER_PREFIXES):
                                continue
                            pending['text'] = _norm_spaces(f"{pending['text']} {line}")
                            if 'SALDO' in upper:
                                pending['is_balance'] = True
                            pending.setdefault('raw_lines', []).append(raw_line)
                        else:
                            continue

                    if pending:
                        amount_count = len(AMOUNT_RX.findall(pending['text']))
                        should_finalize = amount_count >= 2 or (
                            pending.get('is_balance') and amount_count >= 1
                        )
                        if should_finalize:
                            row = _finalize_entry(pending, prev_saldo)
                            if row:
                                movimientos.append(row)
                                prev_saldo = row['Saldo']
                            pending = None
        flush_spei()
    finally:
        if ocr_doc is not None:
            ocr_doc.close()

    if pending:
        row = _finalize_entry(pending, prev_saldo)
        if row:
            movimientos.append(row)

    spei_env, spei_rec = _extract_spei_lookup(spei_sections)

    df = pd.DataFrame(movimientos)
    if df.empty:
        return df
    for column in ["LineaDetectada", "_fecha_iso"]:
        if column not in df.columns:
            df[column] = None
    df = df[
        ["Fecha", "Referencia", "Concepto", "Cargo", "Abono", "Saldo", "LineaDetectada", "_fecha_iso"]
    ].copy()
    period_label = _format_period_label(period_start, period_end)
    df["Cargo"] = pd.to_numeric(df["Cargo"], errors="coerce").fillna(0.0)
    df["Abono"] = pd.to_numeric(df["Abono"], errors="coerce").fillna(0.0)
    df["Saldo"] = pd.to_numeric(df["Saldo"], errors="coerce")
    df["Concepto"] = df["Concepto"].str.replace(r"\s+", " ", regex=True).str.strip()
    df["_fecha_raw"] = df["_fecha_iso"]
    df["_fecha_dt"] = pd.to_datetime(df["_fecha_iso"], errors="coerce")
    df = df.sort_values("_fecha_dt", kind="mergesort").reset_index(drop=True)
    df = _apply_transfer_labels(df, spei_env, spei_rec)
    df["Fecha"] = df["_fecha_dt"].dt.strftime("%d")
    missing_mask = df["Fecha"].isna()
    if missing_mask.any():
        df.loc[missing_mask, "Fecha"] = df.loc[missing_mask, "_fecha_raw"].str[-2:]
    df = df.drop(columns=["_fecha_dt", "_fecha_raw", "_fecha_iso"])
    df.attrs["period_label"] = period_label
    return df
TRANSFER_KEYWORDS = ("TRANSFERENCIA", "TRASPASO", "SPEI", "BPI")
PARTICIPANT_TOKENS = {
    "BANORTE",
    "BANCOMER",
    "BANAMEX",
    "BBVA",
    "BANCOPPEL",
    "BANCO",
    "BANAM",
    "SANTANDER",
    "SCOTIABANK",
    "HSBC",
    "INBURSA",
    "BANREGIO",
    "BANBAJIO",
    "AZTECA",
    "MULTIVA",
    "AFIRME",
    "BANSI",
    "CIBANCO",
    "BANCREA",
    "BANSEFI",
    "COMPARTAMOS",
    "FAMSA",
    "VE",
    "POR",
    "MAS",
}
DETAIL_HEADER_RX = re.compile(r"DETALLE\s+MOVIMIENT[O0][S5]", re.IGNORECASE)
SPEI_HEADER_ENVIADOS_RX = re.compile(r"INFORMACI[ÓO]N\s+SPEI'?S?\s+ENVIADOS", re.IGNORECASE)
SPEI_HEADER_RECIBIDOS_RX = re.compile(r"INFORMACI[ÓO]N\s+SPEI'?S?\s+RECIBIDOS", re.IGNORECASE)
DETAIL_END_PATTERNS = (
    "* DATO NO VERIFICADO",
    "CODI:",
    "OPERACION PROCESADA POR CODI",
    "EMITIDO POR:",
    "PASEO DE LA REFORMA",
    "CARGOS OBJETADOS POR EL CLIENTE",
)
