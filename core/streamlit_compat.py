"""Compatibility helpers for Streamlit APIs that changed across versions.

This module provides small wrappers so code can call a consistent API
(`rerun`, `set_query_params`) regardless of the installed Streamlit version.
"""

from __future__ import annotations

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

