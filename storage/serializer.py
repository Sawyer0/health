"""Pure domain serialization and deserialization helpers for StoredSymptomReport."""

import json
from typing import List, Tuple, Any
from datetime import datetime
from domain.schema import StoredSymptomReport, SymptomReport


def row_to_stored_report(cols: List[str], row: Tuple[Any, ...]) -> StoredSymptomReport:
    """Deserializes an SQLite row tuple into a strongly typed StoredSymptomReport."""
    d = dict(zip(cols, row))
    raw_flags = d.get("flags")
    flags = json.loads(str(raw_flags)) if raw_flags else []
    raw_meds = d.get("medications")
    medications = json.loads(str(raw_meds)) if raw_meds else []
    raw_effects = d.get("side_effects")
    side_effects = json.loads(str(raw_effects)) if raw_effects else []
    raw_q = d.get("questionnaire")
    questionnaire = json.loads(str(raw_q)) if raw_q else None

    ts_raw = d.get("timestamp")
    timestamp = datetime.fromisoformat(str(ts_raw)) if ts_raw else datetime.now()

    return StoredSymptomReport(
        id=int(str(d["id"])),
        patient_id=str(d.get("patient_id", "")),
        patient_name=str(d.get("patient_name", "")),
        report_date=str(d.get("report_date", "")),
        report_time=str(d.get("report_time", "")),
        raw_text=str(d.get("raw_text", "")),
        timestamp=timestamp,
        symptom=str(d["symptom"]) if d.get("symptom") is not None else None,
        severity=int(str(d["severity"])) if d.get("severity") is not None else None,
        frequency=str(d["frequency"]) if d.get("frequency") is not None else None,
        medications=medications,
        side_effects=side_effects,
        confidence=float(str(d.get("confidence", 0.0))),
        flags=flags,
        source=str(d.get("source", "synthetic")),
        questionnaire=questionnaire,
        created_at=str(d.get("created_at", "")),
    )


def report_to_insert_params(report: SymptomReport) -> Tuple[Any, ...]:
    """Serializes a SymptomReport into an insert parameters tuple."""
    return (
        report.patient_id,
        report.patient_name,
        report.report_date,
        report.report_time,
        report.raw_text,
        report.timestamp.isoformat(),
        report.symptom,
        report.severity,
        report.frequency,
        json.dumps(report.medications),
        json.dumps(report.side_effects),
        report.confidence,
        json.dumps(report.flags),
        report.source,
        json.dumps(report.questionnaire) if report.questionnaire else None,
    )
