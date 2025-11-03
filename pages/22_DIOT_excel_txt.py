"""Herramienta Excel -> TXT para DIOT con barra de navegación fija."""

from __future__ import annotations

import html
import io
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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

    # Oculta el uploader nativo y despliega una UI personalizada.
    st.markdown('<div class="diot-native-wrapper">', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Selecciona un archivo Excel",
        type=["xlsx"],
        key="diot_native_uploader",
        label_visibility="collapsed",
        help=(
            "Limite de 200 MB por archivo. Solo XLSX. Las filas 1 y 2 se ignoran; "
            "el TXT se genera desde la fila 3."
        ),
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        .diot-native-wrapper {
            position: relative;
        }
        .diot-native-wrapper > div[data-testid="stFileUploader"] {
            position: absolute;
            inset: 0;
            width: 1px;
            height: 1px;
            opacity: 0;
            pointer-events: none;
            overflow: hidden;
        }
        .diot-hidden-native {
            position: absolute !important;
            inset: 0 !important;
            width: 1px !important;
            height: 1px !important;
            opacity: 0 !important;
            pointer-events: none !important;
            overflow: hidden !important;
            margin: 0 !important;
        }
        .diot-hidden-native * {
            opacity: 0 !important;
            pointer-events: none !important;
            height: 0 !important;
        }
        .diot-hidden-native input[type="file"] {
            opacity: 0 !important;
            pointer-events: auto !important;
            width: 1px !important;
            height: 1px !important;
        }
        </style>
        <script>
        (function() {
            const doc = window.document;
            function hideNative(retries = 0) {
                const node = doc.querySelector("div[data-testid='stFileUploader']");
                if (!node) {
                    if (retries < 50) {
                        window.setTimeout(() => hideNative(retries + 1), 100);
                    }
                    return;
                }
                if (!node.classList.contains("diot-hidden-native")) {
                    node.classList.add("diot-hidden-native");
                }
            }
            hideNative();
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    displayed_name = html.escape(uploaded.name) if uploaded else "Ningún archivo seleccionado"
    selected_js = json.dumps(uploaded.name if uploaded else "")
    selected_class = "" if uploaded else " empty"

    components.html(
        f"""
<div class="diot-upload-wrapper">
  <div class="diot-dropzone" id="diot-dropzone">
    <div class="diot-dropzone-left">
      <div class="diot-icon">📁</div>
      <div class="diot-text">
        <p class="diot-title">Arrastra y suelta tu archivo Excel aquí</p>
        <p class="diot-subtitle">Límite de 200 MB por archivo - XLSX</p>
      </div>
    </div>
    <button class="diot-button" type="button" id="diot-trigger">Seleccionar archivo</button>
  </div>
  <p class="diot-selected{selected_class}" id="diot-selected">{displayed_name}</p>
</div>
<style>
:root {{
  --diot-primary: #4a5cff;
  --diot-primary-dark: #3e50f5;
  --diot-border: rgba(90, 94, 154, 0.25);
  --diot-background: rgba(226, 229, 255, 0.45);
}}
.diot-upload-wrapper {{
  font-family: "Segoe UI", sans-serif;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}}
.diot-dropzone {{
  border: 1px solid var(--diot-border);
  border-radius: 14px;
  padding: 1.2rem 1.6rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--diot-background);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  cursor: pointer;
  gap: 1rem;
}}
.diot-dropzone--active {{
  border-color: var(--diot-primary);
  background: rgba(226, 229, 255, 0.8);
  box-shadow: 0 0 0 3px rgba(74, 92, 255, 0.18);
}}
.diot-dropzone-left {{
  display: flex;
  align-items: center;
  gap: 1rem;
}}
.diot-icon {{
  font-size: 2.25rem;
  line-height: 1;
}}
.diot-text {{
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}}
.diot-title {{
  margin: 0;
  font-weight: 600;
  color: #1f1f2d;
  font-size: 1rem;
}}
.diot-subtitle {{
  margin: 0;
  font-size: 0.85rem;
  color: #5c6070;
}}
.diot-button {{
  background: var(--diot-primary);
  color: #fff;
  font-weight: 600;
  border: none;
  border-radius: 10px;
  padding: 0.7rem 1.4rem;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}}
.diot-button:hover {{
  background: var(--diot-primary-dark);
  transform: translateY(-1px);
}}
.diot-selected {{
  margin: 0;
  font-size: 0.9rem;
  color: #3f4254;
  padding-left: 0.25rem;
}}
.diot-selected.empty {{
  color: #888b9c;
}}
@media (max-width: 640px) {{
  .diot-dropzone {{
    flex-direction: column;
    align-items: stretch;
  }}
  .diot-button {{
    width: 100%;
  }}
}}
</style>
<script>
(function() {{
  const initialName = {selected_js};
  const frameDoc = window.parent.document;

  function formatName(name) {{
    return name && name.length ? name : "Ningún archivo seleccionado";
  }}

  function setLabel(name) {{
    const label = document.getElementById("diot-selected");
    if (!label) return;
    const text = formatName(name);
    label.textContent = text;
    if (name && name.length) {{
      label.classList.remove("empty");
    }} else {{
      label.classList.add("empty");
    }}
  }}

  function waitForInput(retries = 0) {{
    const input = frameDoc.querySelector("div[data-testid='stFileUploader'] input[type='file']");
    if (!input) {{
      if (retries < 50) {{
        setTimeout(() => waitForInput(retries + 1), 100);
      }}
      return;
    }}
    setup(input);
  }}

  function setup(input) {{
    const dropzone = document.getElementById("diot-dropzone");
    const trigger = document.getElementById("diot-trigger");
    if (!dropzone || !trigger) return;

    const root = input.closest("div[data-testid='stFileUploader']");
    if (root) {{
      root.classList.add("diot-hidden-native");
      root.setAttribute("aria-hidden", "true");
    }}

    function openDialog(event) {{
      event.preventDefault();
      input.click();
    }}

    trigger.addEventListener("click", openDialog);
    dropzone.addEventListener("click", openDialog);

    ["dragenter", "dragover"].forEach(evt => {{
      dropzone.addEventListener(evt, event => {{
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.add("diot-dropzone--active");
      }});
    }});

    ["dragleave", "dragend"].forEach(evt => {{
      dropzone.addEventListener(evt, event => {{
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove("diot-dropzone--active");
      }});
    }});

    dropzone.addEventListener("drop", event => {{
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove("diot-dropzone--active");

      if (!event.dataTransfer || !event.dataTransfer.files || !event.dataTransfer.files.length) {{
        return;
      }}

      const dt = new DataTransfer();
      Array.from(event.dataTransfer.files).forEach(file => dt.items.add(file));
      input.files = dt.files;
      input.dispatchEvent(new Event("change", {{ bubbles: true }}));
      setLabel(input.files[0] ? input.files[0].name : "");
    }});

    input.addEventListener("change", () => {{
      const name = input.files && input.files.length ? input.files[0].name : "";
      setLabel(name);
    }});

    setLabel(initialName);
  }}

  setLabel(initialName);
  waitForInput();
}})();
</script>
        """,
        height=240,
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

