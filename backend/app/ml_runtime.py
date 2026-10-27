"""Resolve the Python interpreter used for local image validation/inference."""

from pathlib import Path
import sys

from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def python_executable() -> str:
    if settings.plantmitra_ml_python:
        configured = Path(settings.plantmitra_ml_python)
        if configured.is_file():
            return str(configured)

    for candidate in (
        PROJECT_ROOT / "ml" / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / "ml" / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)

    # Hosted deployments install inference dependencies alongside FastAPI.
    return sys.executable
