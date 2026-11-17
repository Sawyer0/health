"""Shared test fixtures and factory helpers."""

from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
import pytest
from fastapi.testclient import TestClient
from app import app, get_store
from domain import SymptomReport
from storage import ReportStore


def make_report(date: str = "2026-10-31", time: str = "08:00", **overrides: Any) -> SymptomReport:
    fields: dict[str, Any] = {
        "patient_id": "P01",
        "patient_name": "Test Patient",
        "report_date": date,
        "report_time": time,
        "raw_text": "Sample text",
        "timestamp": datetime.fromisoformat(f"{date}T{time}:00"),
        "confidence": 0.9,
    }
    fields.update(overrides)
    return SymptomReport(**fields)


@pytest.fixture
def api_client(tmp_path: Path) -> Iterator[tuple[TestClient, Path]]:
    """Provides a FastAPI TestClient wired to an isolated temporary SQLite database."""
    db_file = tmp_path / "api_test.db"
    app.dependency_overrides[get_store] = lambda: ReportStore(db_file)
    try:
        yield TestClient(app), db_file
    finally:
        app.dependency_overrides.clear()
