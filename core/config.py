# core/config.py
from pathlib import Path
import os
from typing import Iterable

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for Python < 3.11
    try:
        import tomli as tomllib  # type: ignore[assignment]
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        tomllib = None  # type: ignore[assignment]


def _first_existing(paths: Iterable[Path], default: Path) -> Path:
    for candidate in paths:
        if candidate.exists():
            return candidate
    return default


BASE_DIR = Path(__file__).resolve().parents[1]

db_env = os.getenv("DB_PATH", "").strip()
DB_PATH = Path(db_env).expanduser() if db_env else BASE_DIR / "db" / "tolls.db"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
PORTAL_DATABASE_URL = os.getenv("PORTAL_DATABASE_URL", "").strip() or DATABASE_URL

verified_routes_env = os.getenv("VERIFIED_ROUTES_XLSX", "").strip()
if verified_routes_env:
    VERIFIED_ROUTES_XLSX = Path(verified_routes_env).expanduser()
else:
    VERIFIED_ROUTES_XLSX = BASE_DIR / "data" / "CASETAS TRAFICO TOLUCA.xlsx"

tariffs_env = os.getenv("TARIFFS_XLSX", "").strip()
if tariffs_env:
    TARIFFS_XLSX = Path(tariffs_env).expanduser()
else:
    TARIFFS_XLSX = _first_existing(
        [
            BASE_DIR / "data" / "PEAJE_PASE_2025.xlsx",
            BASE_DIR / "PEAJE_PASE_2025.xlsx",
        ],
        BASE_DIR / "data" / "PEAJE_PASE_2025.xlsx",
    )


def _read_first_existing_text(paths: Iterable[Path]) -> str:
    for path in paths:
        if path and path.is_file():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
    return ""


def _parse_toml_key(raw: str, key: str) -> str:
    if not raw or tomllib is None:
        return ""
    try:
        data = tomllib.loads(raw)  # type: ignore[union-attr]
    except Exception:
        return ""

    if key in data and isinstance(data[key], str):
        return data[key]

    for value in data.values():
        if isinstance(value, dict) and key in value and isinstance(value[key], str):
            return value[key]
    return ""


def _parse_env_key(raw: str, key: str) -> str:
    if not raw:
        return ""
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


def _load_google_maps_key() -> str:
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if key:
        return key

    secrets_candidates = []
    secrets_env = os.getenv("STREAMLIT_SECRETS_FILE", "").strip()
    if secrets_env:
        secrets_candidates.append(Path(secrets_env).expanduser())
    secrets_candidates.extend(
        [
            BASE_DIR / ".streamlit" / "secrets.toml",
            Path.home() / ".streamlit" / "secrets.toml",
        ]
    )

    secrets_raw = _read_first_existing_text(secrets_candidates)
    key = _parse_toml_key(secrets_raw, "GOOGLE_MAPS_API_KEY").strip()
    if key:
        return key

    env_candidates = [
        BASE_DIR / ".env",
        Path.cwd() / ".env",
    ]
    env_raw = _read_first_existing_text(env_candidates)
    key = _parse_env_key(env_raw, "GOOGLE_MAPS_API_KEY").strip()
    return key


# Google Maps key (required para autocompletado y rutas)
GOOGLE_MAPS_API_KEY = _load_google_maps_key()
