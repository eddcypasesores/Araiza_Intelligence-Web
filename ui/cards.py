# ui/cards.py
from pathlib import Path
import base64
from typing import Optional
import streamlit as st

def _mime_from_suffix(suffix: str) -> str:
    s = suffix.lower()
    if s in (".jpg", ".jpeg"):
        return "jpeg"
    if s == ".webp":
        return "webp"
    return "png"

def link_card(
    img_path: str | Path,
    url: str,
    label: Optional[str] = None,
    new_tab: bool = False,
    img_max_h: Optional[int] = 54,
    img_max_w: Optional[int] = 140,
    extra_class: Optional[str] = None,   # retrocompatibilidad
    variant: Optional[str] = None,       # preferido: "bank"
    **kwargs,                             # ignora argumentos extra antiguos
) -> None:
    """
    Tarjeta clickeable con imagen que lleva al URL asignado.
    - variant="bank" aplica el estilo de card de bancos (logo contenido).
    - extra_class también es aceptado por retrocompatibilidad.
    - Si img_max_h/w son None y variant="bank", no se impone límite inline,
      el tamaño lo gobierna el CSS global (.card.bank img).
    """
    p = Path(img_path)
    if not p.exists():
        st.warning(f"No se encontró la imagen: {p}")
        return

    img_b64 = base64.b64encode(p.read_bytes()).decode()
    mime = _mime_from_suffix(p.suffix)
    target = "_blank" if new_tab else "_self"

    classes = "card"
    # Normaliza clases
    if extra_class:
        classes += f" {extra_class}"
    if variant == "bank" and "bank" not in classes.split():
        classes += " bank"

    # Solo aplicamos límites inline cuando NO es un card de banco
    img_style = ""
    if (variant != "bank") and ("bank" not in classes.split()) and (img_max_h is not None and img_max_w is not None):
        img_style = f"max-height:{img_max_h}px; max-width:{img_max_w}px; width:auto; height:auto;"

    style_attr = f' style="{img_style}"' if img_style else ""

    html = f"""
    <a class="{classes}" href="{url}" target="{target}" rel="noopener noreferrer">
      <img{style_attr} src="data:image/{mime};base64,{img_b64}" alt="{(label or '')}" />
      {f'<div style="margin-top:8px;font-weight:600">{label}</div>' if label else ''}
    </a>
    """
    st.markdown(html, unsafe_allow_html=True)
