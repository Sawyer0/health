import pytest
from datetime import datetime
from pathlib import Path
from typing import Any

from domain import SymptomReport, parse_report
from storage import ReportStore
from charts import symptom_trend_chart


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


def test_vague_data_preserves_text_and_sets_flags() -> None:
    data = {
        "patient_id": "P01",
        "patient_name": "Alex",
        "report_date": "2026-10-25",
        "raw_text": "Felt completely off today.",
        "confidence": 0.45,
    }
    report = parse_report(data).report
    assert report.severity is None
    assert report.frequency is None
    assert report.raw_text == data["raw_text"]
    assert "missing_severity" in report.flags
    assert "low_confidence" in report.flags


@pytest.mark.parametrize("invalid_severity", [0, 11])
def test_rejects_out_of_bounds_severity(invalid_severity: int) -> None:
    with pytest.raises(Exception):
        make_report(severity=invalid_severity)


@pytest.mark.parametrize(
    "raw_text,expected_severity",
    [
        ("Pain was an 8 this morning.", 8),
        ("Pain has settled down to 3 now.", 3),
    ],
)
def test_extracts_numeric_severity(raw_text: str, expected_severity: int) -> None:
    result = parse_report({
        "patient_id": "P01",
        "patient_name": "Alex",
        "report_date": "2026-10-31",
        "raw_text": raw_text,
    })
    assert result.report.severity == expected_severity


def test_detects_contradiction_between_text_and_questionnaire() -> None:
    result = parse_report({
        "patient_id": "P04",
        "patient_name": "Jordan",
        "report_date": "2026-10-24",
        "raw_text": "I feel nauseous after lunch.",
        "symptom": "nausea",
        "severity": 4,
        "questionnaire": {"nausea": 9},
    })
    assert "conflicting_report" in result.report.flags


def test_versions_same_day_reports_without_overwriting(tmp_path: Path) -> None:
    with ReportStore(tmp_path / "t.db") as store:
        store.insert(make_report(time="08:00", severity=8))
        store.insert(make_report(time="20:00", severity=3))

        all_reports = store.all_reports("P01")
        assert len(all_reports) == 2
        assert [r.severity for r in all_reports] == [8, 3]

        dashboard = store.latest_reports_dashboard("P01")
        assert len(dashboard) == 1
        assert dashboard[0].severity == 3


def test_detects_all_conflict_types(tmp_path: Path) -> None:
    with ReportStore(tmp_path / "t.db") as store:
        store.insert(make_report(date="2026-10-21", medications=["ibuprofen"], severity=4))
        store.insert(make_report(date="2026-10-23", time="08:00", medications=["oxycodone"], severity=7))
        store.insert(make_report(date="2026-10-23", time="20:00", medications=["oxycodone"], severity=2, flags=["conflicting_report"]))

        conflicts = store.detect_conflicts("P01")
        types = {c.type for c in conflicts}
        assert types == {"same_day_divergence", "medication_change", "raw_text_questionnaire_contradiction"}

        med_change = next(c for c in conflicts if c.type == "medication_change")
        assert med_change.added_medications == ["oxycodone"]
        assert med_change.removed_medications == ["ibuprofen"]


def test_review_queue_filters_clean_reports(tmp_path: Path) -> None:
    with ReportStore(tmp_path / "t.db") as store:
        store.insert(make_report(time="08:00", severity=2, flags=[]))
        store.insert(make_report(time="12:00", severity=None, confidence=0.5, flags=["missing_severity", "low_confidence"]))
        store.insert(make_report(patient_id="P02", time="16:00", severity=8, flags=["conflicting_report"]))

        queue = store.review_queue()
        assert len(queue) == 2
        assert all(q.severity is None or q.flags for q in queue)


def test_vomiting_episodes_per_week(tmp_path: Path) -> None:
    with ReportStore(tmp_path / "t.db") as store:
        store.insert(make_report(patient_id="P02", date="2026-10-20", raw_text="vomiting", symptom="nausea", severity=6))
        store.insert(make_report(patient_id="P02", date="2026-10-21", raw_text="nausea", symptom="nausea", severity=4))

        weekly = store.vomiting_episodes_per_week("P02")
        # Both reports fall in the same Monday-start week: 2026-10-19
        assert len(weekly) == 1
        assert weekly[0]["week"] == "2026-10-19"
        assert weekly[0]["episode_count"] == 2
        assert weekly[0]["avg_severity"] == 5.0


def test_chart_generation(tmp_path: Path) -> None:
    out = symptom_trend_chart([{"timestamp": "2026-10-20T08:00:00", "severity": 4, "symptom": "pain"}], "P01", "pain", tmp_path / "trend.png")
    assert out.exists() and out.stat().st_size > 0


def test_api_endpoints_and_dashboard_view(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from app import app, get_store

    db_file = tmp_path / "api_test.db"

    # Dependency override for isolated test state
    def override_get_store() -> ReportStore:
        return ReportStore(db_file)

    app.dependency_overrides[get_store] = override_get_store

    try:
        client = TestClient(app)

        # 1. 404 test on empty database for chart
        res_404 = client.get("/patient/P99/chart")
        assert res_404.status_code == 404
        assert "No reports found" in res_404.json()["detail"]

        # 2. Seed database
        with ReportStore(db_file) as store:
            store.insert(make_report(patient_id="P99", date="2026-10-20", severity=6, symptom="pain"))
            store.insert(make_report(patient_id="P99", date="2026-10-21", severity=3, flags=["conflicting_report"]))

        # 3. Dynamic Patient Chart endpoint with seeded DB
        res_chart = client.get("/patient/P99/chart")
        assert res_chart.status_code == 200
        assert res_chart.headers["content-type"] == "image/png"
        assert len(res_chart.content) > 0

        # 4. JSON review queue endpoint with seeded DB
        res_queue = client.get("/review-queue")
        assert res_queue.status_code == 200
        queue_data = res_queue.json()
        assert len(queue_data) == 1
        assert queue_data[0]["patient_id"] == "P99"

        # 5. JSON conflicts endpoint with seeded DB
        res_conflicts = client.get("/conflicts")
        assert res_conflicts.status_code == 200
        assert isinstance(res_conflicts.json(), list)

        # 6. HTML Dashboard endpoint with seeded DB
        res_dash = client.get("/dashboard")
        assert res_dash.status_code == 200
        assert "text/html" in res_dash.headers["content-type"]
        assert "Clinical PRO Triage Dashboard" in res_dash.text
        assert "Review Queue" in res_dash.text

        # 7. POST /reports endpoint
        new_report = {
            "patient_id": "P99",
            "patient_name": "Test Ingest",
            "report_date": "2026-10-22",
            "report_time": "14:00",
            "raw_text": "Pain was an 8 this afternoon. Difficulty swallowing.",
        }
        res_ingest = client.post("/reports", json=new_report)
        assert res_ingest.status_code == 201
        ingested = res_ingest.json()
        assert ingested["id"] > 0
        assert ingested["patient_id"] == "P99"
        assert ingested["severity"] == 8

        # 8. POST /reports/batch endpoint
        batch = [
            {
                "patient_id": "P99",
                "patient_name": "Test Ingest",
                "report_date": "2026-10-23",
                "raw_text": "Feeling slightly better, pain down to 3.",
            }
        ]
        res_batch = client.post("/reports/batch", json=batch)
        assert res_batch.status_code == 201
        batch_out = res_batch.json()
        assert len(batch_out) == 1
        assert batch_out[0]["severity"] == 3
    finally:
        app.dependency_overrides.clear()


def test_ingestion_idempotency_and_conflict_flags(tmp_path: Path) -> None:
    """Ingest the same raw report twice (idempotent), then verify conflict flags."""
    from fastapi.testclient import TestClient
    from app import app, get_store

    db_file = tmp_path / "idem.db"

    def override_get_store() -> ReportStore:
        return ReportStore(db_file)

    app.dependency_overrides[get_store] = override_get_store
    try:
        client = TestClient(app)

        raw = {
            "patient_id": "P99",
            "patient_name": "Test Patient",
            "report_date": "2026-12-01",
            "report_time": "09:00",
            "raw_text": "Pain is a 7 today. Questionnaire says 2, but I punched in 7 by accident.",
            "symptom": "pain",
            "severity": 7,
            "questionnaire": {"pain": 2},
            "confidence": 0.95,
        }

        # First insert
        r1 = client.post("/reports", json=raw)
        assert r1.status_code == 201
        id1 = r1.json()["id"]

        # Second insert — must not create a new row
        r2 = client.post("/reports", json=raw)
        assert r2.status_code == 201
        id2 = r2.json()["id"]
        assert id1 == id2, "Ingesting the same report twice must be idempotent"

        # Review queue must contain the conflicting report
        queue = client.get("/review-queue").json()
        assert any(r["id"] == id1 and "conflicting_report" in r["flags"] for r in queue)

        # Conflicts endpoint must surface the contradiction
        conflicts = client.get("/conflicts").json()
        types = {c["type"] for c in conflicts}
        assert "raw_text_questionnaire_contradiction" in types
    finally:
        app.dependency_overrides.clear()


def test_ingestion_unknown_patient(tmp_path: Path) -> None:
    """Reports with missing patient_id fall back to UNKNOWN and are still stored."""
    from fastapi.testclient import TestClient
    from app import app, get_store

    db_file = tmp_path / "missing_patient.db"

    def override_get_store() -> ReportStore:
        return ReportStore(db_file)

    app.dependency_overrides[get_store] = override_get_store
    try:
        client = TestClient(app)
        res = client.post("/reports", json={
            "patient_name": "Anonymous Guy",
            "report_date": "2026-12-01",
            "report_time": "10:00",
            "raw_text": "Just feeling off today.",
        })
        assert res.status_code == 201
        body = res.json()
        assert body["patient_id"] == "UNKNOWN"
        assert body["patient_name"] == "Anonymous Guy"
    finally:
        app.dependency_overrides.clear()


def test_dashboard_groups_by_patient_id_and_paginates(tmp_path: Path) -> None:
    """Two reports for the same patient_id paginate in one card; two patients sharing a name stay separate."""
    from fastapi.testclient import TestClient
    from app import app, get_store

    db_file = tmp_path / "paginated.db"

    def override_get_store() -> ReportStore:
        return ReportStore(db_file)

    app.dependency_overrides[get_store] = override_get_store
    try:
        with ReportStore(db_file) as store:
            # P01 ("Alex Morgan") has 2 flagged reports -> 1 card with 2 pages
            store.insert(make_report(patient_id="P01", patient_name="Alex Morgan", date="2026-11-10", time="08:00", severity=None, confidence=0.4))
            store.insert(make_report(patient_id="P01", patient_name="Alex Morgan", date="2026-11-12", time="09:00", severity=8, flags=["conflicting_report"]))
            # P09 ALSO named "Alex Morgan" -> must be a separate card and show MRN in header
            store.insert(make_report(patient_id="P09", patient_name="Alex Morgan", date="2026-11-11", time="10:00", severity=None, confidence=0.5))

        client = TestClient(app)
        html_text = client.get("/dashboard").text
        assert 'data-patient-id="P01" data-total-pages="2"' in html_text
        assert 'data-patient-id="P09" data-total-pages="1"' in html_text
        assert "1 / 2" in html_text
        assert "patient-mrn always-visible" in html_text
        assert "2 patients &bull; 3 reports" in html_text
    finally:
        app.dependency_overrides.clear()

