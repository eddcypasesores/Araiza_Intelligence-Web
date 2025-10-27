"""Streamlit entry point that routes to the requested multipage view."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import streamlit as st

from core.navigation import PAGE_PARAM_NAMES

st.set_page_config(page_title="Araiza Intelligence", layout="wide")


def _normalize(value) -> str | None:
    """Return the last truthy element from Streamlit query param values."""

    if isinstance(value, list):
        return value[-1] if value else None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _page_lookup() -> Mapping[str, str]:
    """Build a reverse lookup from label -> script path."""

    reverse: dict[str, str] = {}
    for script, label in PAGE_PARAM_NAMES.items():
        reverse[label] = script
    return reverse


def _resolve_target(label: str | None) -> str:
    """Resolve the script path to render given the ``page`` label."""

    if label:
        reverse = _page_lookup()
        target = reverse.get(label)
        if target:
            return target

        # Fallback: allow specifying the actual script path via the query string.
        # Streamlit expects paths relative to the project root and they must exist.
        if label.endswith(".py"):
            candidate = Path(label)
            if candidate.exists():
                return str(candidate)
            candidate = Path("pages") / label
            if candidate.exists():
                return str(candidate)

    # Default to the public home page.
    return "pages/0_Inicio.py"


requested_page = _normalize(st.query_params.get("page"))
st.switch_page(_resolve_target(requested_page))
