"""Entrypoint ASGI.

Jalankan dengan:
    uv run uvicorn main:app --reload
"""

from app.server import app

__all__ = ["app"]
