"""FastAPI routing and HTTP controller layer for clinical PRO triage."""

import io
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Query, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, Response
from domain import (
    StoredSymptomReport,
    ConflictEvent,
    PatientClinicalSummary,
    parse_report,
)
from storage import ReportStore
from constants import DEFAULT_DB_PATH
from components import render_dashboard_page
from charts import symptom_trend_chart

app = FastAPI(
    title="Clinical PRO Review Queue & Dashboard",
    description="Unified clinical triage dashboard and longitudinal patient explorer",
    version="1.0.0",
)


def get_store() -> ReportStore:
    """Dependency provider yielding the configured ReportStore instance."""
    return ReportStore(DEFAULT_DB_PATH)


def _persist_report(store: ReportStore, raw_report: Dict[str, Any]) -> StoredSymptomReport:
    result = parse_report(raw_report)
    with store:
        report_id = store.insert(result.report)
        persisted = store.get_report_by_id(report_id)
        if not persisted:
            raise HTTPException(status_code=500, detail="Failed to retrieve persisted report")
        return persisted


@app.post("/reports", response_model=StoredSymptomReport, status_code=status.HTTP_201_CREATED)
def ingest_report(
    raw_report: Dict[str, Any],
    store: ReportStore = Depends(get_store),
) -> StoredSymptomReport:
    """Ingests a raw patient report JSON dictionary."""
    return _persist_report(store, raw_report)


@app.post("/reports/batch", response_model=List[StoredSymptomReport], status_code=status.HTTP_201_CREATED)
def ingest_reports_batch(
    raw_reports: List[Dict[str, Any]],
    store: ReportStore = Depends(get_store),
) -> List[StoredSymptomReport]:
    """Ingests a batch of raw patient reports."""
    persisted_reports: List[StoredSymptomReport] = []
    with store:
        for raw in raw_reports:
            persisted_reports.append(_persist_report(store, raw))
    return persisted_reports


@app.get("/review-queue", response_model=List[StoredSymptomReport])
def get_review_queue(
    patient_id: Optional[str] = Query(None, description="Optional patient ID filter"),
    store: ReportStore = Depends(get_store),
) -> List[StoredSymptomReport]:
    """JSON API endpoint returning reports that require clinical triage."""
    with store:
        return store.review_queue(patient_id=patient_id)


@app.get("/conflicts", response_model=List[ConflictEvent])
def get_conflicts(
    patient_id: Optional[str] = Query(None, description="Optional patient ID filter"),
    store: ReportStore = Depends(get_store),
) -> List[ConflictEvent]:
    """JSON API endpoint returning all detected conflicts, same-day divergences, and medication deltas."""
    with store:
        return store.detect_conflicts(patient_id=patient_id)


@app.get("/patients/summary", response_model=List[PatientClinicalSummary])
def get_patient_summaries(
    patient_id: Optional[str] = Query(None, description="Optional patient ID filter"),
    store: ReportStore = Depends(get_store),
) -> List[PatientClinicalSummary]:
    """Returns per-patient clinical risk metrics, severity bounds, and weight-loss trajectory."""
    with store:
        return store.patient_clinical_summaries(patient_id=patient_id)


@app.get("/patient/{patient_id}/chart")
def get_patient_chart(
    patient_id: str,
    symptom: str = "pain",
    store: ReportStore = Depends(get_store),
) -> Response:
    """Returns dynamic PNG chart for selected patient."""
    with store:
        reports = store.latest_reports_dashboard(patient_id=patient_id)

    if not reports:
        raise HTTPException(status_code=404, detail=f"No reports found for patient {patient_id}")

    buf = io.BytesIO()
    symptom_trend_chart(reports, patient_id=patient_id, symptom=symptom, out_path=buf)
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(
    patient_id: Optional[str] = Query(None, description="Optional patient ID filter"),
    store: ReportStore = Depends(get_store),
) -> str:
    """Renders the Clinical PRO Triage Dashboard view."""
    with store:
        queue = store.review_queue(patient_id=patient_id)
        all_conflicts = store.detect_conflicts(patient_id=patient_id)
        summaries = store.patient_clinical_summaries(patient_id=patient_id)
    return render_dashboard_page(queue, all_conflicts, summaries)
