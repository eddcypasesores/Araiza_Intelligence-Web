"""Compatibility helpers for Streamlit APIs that changed across versions.

This module provides small wrappers so code can call a consistent API
(`rerun`, `set_query_params`) regardless of the installed Streamlit version.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Any

import streamlit as st


def rerun() -> None:
    """Trigger a Streamlit app rerun.

    Uses ``st.rerun()`` when available, otherwise falls back to
    ``st.experimental_rerun()``.
    """

    try:
        # Streamlit >= 1.27
        st.rerun()  # type: ignore[attr-defined]
    except Exception:
        # Older Streamlit
        try:
            st.experimental_rerun()  # type: ignore[attr-defined]
        except Exception:
            # As a last resort, do nothing.
            pass


def set_query_params(params: Mapping[str, Any] | None) -> None:
    """Set URL query parameters in a version-tolerant way.

    Attempts the modern ``st.query_params`` mapping first, then falls back to
    ``st.experimental_set_query_params`` for older versions.
    """

    params = dict(params or {})

    # Try modern API first (Streamlit >= 1.30): mapping-like proxy
    try:
        qp = st.query_params  # type: ignore[attr-defined]
        try:
            # Clear existing params, then update with provided mapping
            if hasattr(qp, "clear"):
                qp.clear()  # type: ignore[call-arg]
        except Exception:
            # Ignore if clear is not supported
            pass
        try:
            if hasattr(qp, "update"):
                qp.update(params)  # type: ignore[call-arg]
                return
        except Exception:
            # If update not supported or failed, continue to fallback
            pass
    except Exception:
        # ``st.query_params`` not available or failed
        pass

    # Fallback for older Streamlit versions
    try:
        st.experimental_set_query_params(**params)  # type: ignore[attr-defined]
    except Exception:
        # Last resort: no-op
        pass


def normalize_page_path(raw: str | None) -> str | None:
    """Return a Streamlit-friendly ``pages/...`` path from various inputs.

    Handles Windows backslashes, absolute paths inside the workspace and
    bare filenames (prefixed with ``pages/`` when they exist in the pages dir).
    """

    if raw is None:
        return None

    candidate = str(raw).strip()
    if not candidate:
        return None

    normalized: str | None = None
    try:
        path = Path(candidate)
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(Path.cwd())
            except Exception:
                # Keep absolute path if it cannot be relativized
                pass
        normalized = path.as_posix()
    except Exception:
        normalized = candidate.replace("\\", "/")

    if not normalized:
        return None

    normalized = normalized.replace("\\", "/").lstrip("./")

    if normalized.endswith(".py") and not normalized.startswith("pages/"):
        potential = Path("pages") / normalized
        if potential.exists():
            normalized = potential.as_posix()

    return normalized or None

