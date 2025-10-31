"""Herramienta Excel -> TXT para DIOT con barra de navegación fija."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from pages.components.admin import init_admin_section


def insert_after_nth_bar(line: str, n: int, chunk: str) -> str:
    """Insert `chunk` immediately after the nth '|' if present; otherwise return line unchanged."""

    count = 0
    for idx, ch in enumerate(line):
        if ch == "|":
            count += 1
            if count == n:
                return line[: idx + 1] + chunk + line[idx + 1 :]
    return line


OPS: list[tuple[int, str]] = [
    (3, "||||"),
    (8, "|"),
    (10, "|"),
    (12, "|||||"),
    (18, "|"),
    (20, "|"),
    (22, "|||||||||||||||||||||||||"),  # 25 barras
    (48, "|"),
    (51, "||"),
]


def excel_to_txt_with_rules(buffer: io.BytesIO | io.BufferedReader) -> str:
    df = pd.read_excel(buffer, header=None, dtype=str).fillna("")
    df = df.iloc[2:]  # datos desde la fila 3
    lines = ["|".join(row.astype(str).tolist()) for _, row in df.iterrows()]

    result: list[str] = []
    for line in lines:
        for nth, chunk in OPS:
            line = insert_after_nth_bar(line, nth, chunk)
        result.append(line)
    return "\n".join(result)


def main() -> None:
    conn = init_admin_section(
        page_title="Excel -> TXT (DIOT)",
        active_top="diot",
        active_child="diot_excel_txt",
        layout="centered",
        show_inicio=False,
    )
    conn.close()

    st.title("📄 Excel -> TXT (DIOT)")
    st.caption(
        "Sube tu Excel y generamos un TXT con el formato y las inserciones solicitadas "
        "(a partir de la **fila 3**)."
    )

    uploaded = st.file_uploader(
        "Arrastra y suelta tu archivo Excel aquí",
        type=["xlsx"],
        help="Lmite 200 MB por archivo  • XLSX. Las filas 1 y 2 se ignoran; el TXT se genera desde la fila 3.",
    )

    if uploaded is None:
        st.info("Esperando un archivo .xlsx…")
        return

    try:
        txt_data = excel_to_txt_with_rules(io.BytesIO(uploaded.read()))
    except Exception as exc:
        st.error(f"Ocurrió un error procesando el archivo: {exc}")
        return

    st.success("TXT generado correctamente.")

    preview_lines = txt_data.splitlines()
    st.code("\n".join(preview_lines[:5]) if preview_lines else "(Sin líneas)", language="text")

    st.download_button(
        label="⬇️ Descargar TXT",
        data=txt_data.encode("utf-8"),
        file_name=f"{uploaded.name.rsplit('.', 1)[0]}_procesado.txt",
        mime="text/plain",
    )


if __name__ == "__main__":
    main()

