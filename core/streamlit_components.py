"""Reusable Streamlit component wrappers for the project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components


_COMPONENT_BASE = Path(__file__).resolve().parent.parent / "pages" / "components"
_GMAPS_COMPONENT_DIR = _COMPONENT_BASE / "gmaps_autocomplete"


if _GMAPS_COMPONENT_DIR.exists():
    _gmaps_autocomplete_component = components.declare_component(
        "gmaps_autocomplete", path=str(_GMAPS_COMPONENT_DIR.resolve())
    )
else:
    _gmaps_autocomplete_component = None


def gmaps_autocomplete_component(**kwargs: Any) -> Any:
    """Return the Google Maps autocomplete component if available.

    This helper centralises the declaration to avoid import-time issues on
    Windows/`streamlit run`, while keeping a graceful fallback during tests.
    """

    if _gmaps_autocomplete_component is None:
        raise RuntimeError(
            "Google Maps autocomplete component assets were not found at "
            f"{_GMAPS_COMPONENT_DIR}"
        )
    return _gmaps_autocomplete_component(**kwargs)
