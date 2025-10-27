"""Compatibility helpers for Streamlit API changes.

These utilities smooth over differences between older Streamlit releases
that exposed ``st.experimental_*`` helpers and the modern equivalents that
graduated to the public API.  They allow the rest of the codebase to call a
stable helper while transparently delegating to whichever attribute exists in
the currently installed version of Streamlit.
"""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st


def rerun() -> None:
    """Trigger a Streamlit rerun using whichever helper is available."""

    runner = getattr(st, "rerun", None)
    if callable(runner):
        runner()
        return

    experimental_runner = getattr(st, "experimental_rerun", None)
    if callable(experimental_runner):
        experimental_runner()
        return

    raise RuntimeError("Streamlit does not expose a rerun helper")


def set_query_params(params: Mapping[str, Any]) -> None:
    """Replace the current query parameters with ``params``.

    Streamlit 1.32+ exposes ``st.query_params`` as a mutable mapping. Older
    versions only provide the ``st.experimental_set_query_params`` function.
    This helper updates the query string via whichever interface is present.
    """

    query_params = getattr(st, "query_params", None)
    if query_params is not None:
        try:
            query_params.clear()
        except Exception:
            for key in list(query_params.keys()):
                try:
                    del query_params[key]
                except Exception:
                    pass
        query_params.update(params)
        return

    setter = getattr(st, "experimental_set_query_params", None)
    if callable(setter):
        setter(**params)
        return

    raise RuntimeError("Streamlit does not expose a query-param setter")
