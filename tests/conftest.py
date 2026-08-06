"""Shared fixtures.

The database fixtures point `config.settings` at a temporary file *before*
`database.connection` reads it, so tests never touch `data/app.db`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A fresh, empty database for one test, with output/ redirected too."""
    from database import connection
    from database.connection import init_db

    db_path = tmp_path / "test.db"
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    monkeypatch.setattr(settings, "DATABASE_PATH", db_path)
    monkeypatch.setattr(settings, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(connection, "DATABASE_PATH", db_path)

    import database.repository as repository

    monkeypatch.setattr(repository, "OUTPUT_DIR", output_dir)

    init_db()
    return db_path


@pytest.fixture
def brand():
    """The real brand.yaml. Validation rules are brand-driven, so testing
    against a synthetic brand would test the fixture rather than the rules."""
    from brand.loader import load_brand

    return load_brand()
