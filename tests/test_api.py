"""Integration tests for FastAPI HTTP endpoints, ingestion idempotency, and dashboard UI."""

from pathlib import Path
from fastapi.testclient import TestClient
from storage import ReportStore
from tests.conftest import make_report


def test_api_endpoints_and_dashboard_view(api_client: tuple[TestClient, Path]) -> None:
    client, db_file = api_client

    res_404 = client.get("/patient/P99/chart")
    assert res_404.status_code == 404
    assert "No reports found" in res_404.json()["detail"]

    with ReportStore(db_file) as store:
        store.insert(make_report(patient_id="P99", date="2026-10-20", severity=6, symptom="pain"))
        store.insert(make_report(patient_id="P99", date="2026-10-21", severity=3, flags=["conflicting_report"]))

    res_chart = client.get("/patient/P99/chart")
    assert res_chart.status_code == 200
    assert res_chart.headers["content-type"] == "image/png"
    assert len(res_chart.content) > 0

    res_queue = client.get("/review-queue")
    assert res_queue.status_code == 200
    queue_data = res_queue.json()
    assert len(queue_data) == 1
    assert queue_data[0]["patient_id"] == "P99"

    res_conflicts = client.get("/conflicts")
    assert res_conflicts.status_code == 200
    assert isinstance(res_conflicts.json(), list)

    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200
    assert "text/html" in res_dash.headers["content-type"]
    assert "Clinical PRO Triage Dashboard" in res_dash.text
    assert "Review Queue" in res_dash.text

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


def test_ingestion_idempotency_and_conflict_flags(api_client: tuple[TestClient, Path]) -> None:
    """Ingest the same raw report twice (idempotent), then verify conflict flags."""
    client, _ = api_client
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

    r1 = client.post("/reports", json=raw)
    assert r1.status_code == 201
    id1 = r1.json()["id"]

    r2 = client.post("/reports", json=raw)
    assert r2.status_code == 201
    id2 = r2.json()["id"]
    assert id1 == id2

    queue = client.get("/review-queue").json()
    assert any(r["id"] == id1 and "conflicting_report" in r["flags"] for r in queue)

    conflicts = client.get("/conflicts").json()
    types = {c["type"] for c in conflicts}
    assert "raw_text_questionnaire_contradiction" in types


def test_ingestion_unknown_patient(api_client: tuple[TestClient, Path]) -> None:
    """Reports with missing patient_id fall back to UNKNOWN and are still stored."""
    client, _ = api_client
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


def test_dashboard_groups_by_patient_id_and_paginates(api_client: tuple[TestClient, Path]) -> None:
    """Two reports for the same patient_id paginate in one card; two patients sharing a name stay separate."""
    client, db_file = api_client
    with ReportStore(db_file) as store:
        store.insert(make_report(patient_id="P01", patient_name="Alex Morgan", date="2026-11-10", time="08:00", severity=None, confidence=0.4))
        store.insert(make_report(patient_id="P01", patient_name="Alex Morgan", date="2026-11-12", time="09:00", severity=8, flags=["conflicting_report"]))
        store.insert(make_report(patient_id="P09", patient_name="Alex Morgan", date="2026-11-11", time="10:00", severity=None, confidence=0.5))

    html_text = client.get("/dashboard").text
    assert 'data-patient-id="P01" data-total-pages="2"' in html_text
    assert 'data-patient-id="P09" data-total-pages="1"' in html_text
    assert "1 / 2" in html_text
    assert "patient-mrn always-visible" in html_text
    assert "2 patients &bull; 3 reports" in html_text


def test_patient_clinical_summaries_and_endpoint(api_client: tuple[TestClient, Path]) -> None:
    """Verifies SQL window-function computation of baseline/latest weight, % loss, and malnutrition risk."""
    client, db_file = api_client
    with ReportStore(db_file) as store:
        store.insert(make_report(patient_id="P01", patient_name="Alex Morgan", date="2026-10-19", severity=4, questionnaire={"weight_lbs": 200.0}))
        store.insert(make_report(patient_id="P01", patient_name="Alex Morgan", date="2026-11-01", severity=8, questionnaire={"weight_lbs": 188.0}, flags=["conflicting_report"]))

    res = client.get("/patients/summary")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    summary = data[0]
    assert summary["patient_id"] == "P01"
    assert summary["total_reports"] == 2
    assert summary["peak_severity"] == 8
    assert summary["avg_severity"] == 6.0
    assert summary["baseline_weight_lbs"] == 200.0
    assert summary["latest_weight_lbs"] == 188.0
    assert summary["weight_change_pct"] == -6.0
    assert summary["clinically_significant_weight_loss"] is True
    assert summary["review_flag_count"] == 1
