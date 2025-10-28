"""Reusable hero layout helpers shared across public-facing pages."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Iterable, Union

import streamlit as st

PathLike = Union[str, Path]

_HERO_CSS = """
<style>
  :root {
    --brand-red: #dc2626;
    --brand-red-dark: #b91c1c;
    --text-color: #333333;
    --background-color: #f9f9f9;
    --dark-gray: #666666;
  }

  .stApp > header {
    display: none;
  }

  .hero-title {
    font-size: 2.8em;
    font-weight: 700;
    margin-bottom: 20px;
    color: var(--brand-red);
  }

  .hero-subtitle {
    font-size: 1.1em;
    line-height: 1.6;
    margin-bottom: 25px;
    color: var(--dark-gray);
  }

  .hero-list {
    list-style: none;
    padding-left: 0;
    margin-top: 20px;
  }

  .hero-list li {
    margin-bottom: 10px;
    font-size: 1em;
    color: var(--text-color);
    display: flex;
    align-items: center;
  }

  .hero-list li::before {
    content: "\\2022";
    color: var(--brand-red);
    font-weight: bold;
    margin-right: 10px;
    font-size: 1.2em;
  }

  .hero-image {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    object-fit: cover;
    box-shadow: 0 18px 32px rgba(15, 23, 42, 0.16);
  }

  .hero-actions .stButton > button {
    background-color: var(--brand-red);
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 12px 24px;
    font-size: 1.05em;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.3s ease;
  }

  .hero-actions .stButton > button:hover {
    background-color: var(--brand-red-dark);
  }
</style>
"""


def inject_hero_css() -> None:
    """Inject shared hero styles into the current Streamlit page."""

    st.markdown(_HERO_CSS, unsafe_allow_html=True)


def load_image_base64(path: PathLike) -> str | None:
    """Return a base64-encoded data URI for the provided image path."""

    candidate = Path(path)
    if not candidate.exists():
        return None

    mime = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
    data = candidate.read_bytes()
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def first_image_base64(candidates: Iterable[PathLike]) -> str | None:
    """Return the first available image encoded as base64 from the candidates."""

    for candidate in candidates:
        encoded = load_image_base64(candidate)
        if encoded:
            return encoded
    return None
