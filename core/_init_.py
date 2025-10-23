"""Core package for Costos Traslados application."""

from pathlib import Path
import sys

# Ensure the package directory itself is on sys.path when imported relatively.
_PACKAGE_DIR = Path(__file__).resolve().parent
if str(_PACKAGE_DIR.parent) not in sys.path:
    sys.path.append(str(_PACKAGE_DIR.parent))

__all__ = []