"""Tests for SQLite persistence, versioning, conflict detection, and analytical SQL queries."""

from pathlib import Path
from storage import ReportStore
from charts import symptom_trend_chart
from tests.conftest import make_report


def test_versions_same_day_reports_without_overwriting(tmp_path: Path) -> None:
    with ReportStore(tmp_path / "t.db") as store:
        store.insert(make_report(time="20:00", severity=3))
        store.insert(make_report(time="08:00", severity=8))

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
        store.insert(make_report(patient_id="P02", date="2026-10-22", raw_text="throat pain", symptom="pain", side_effects=["nausea"], severity=None, confidence=0.5))

        weekly = store.vomiting_episodes_per_week("P02")
        assert len(weekly) == 1
        assert weekly[0]["week"] == "2026-10-19"
        assert weekly[0]["episode_count"] == 3
        assert weekly[0]["avg_severity"] == 5.0
        assert weekly[0]["peak_severity"] == 6


def test_chart_generation(tmp_path: Path) -> None:
    out = symptom_trend_chart([{"timestamp": "2026-10-20T08:00:00", "severity": 4, "symptom": "pain"}], "P01", "pain", tmp_path / "trend.png")
    assert out.exists() and out.stat().st_size > 0
