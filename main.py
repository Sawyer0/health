import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Union

from domain import SymptomReport, ConflictEvent, parse_report
from storage import ReportStore
from charts import symptom_trend_chart
from components import display_review_queue
from constants import DEFAULT_DB_PATH, DEFAULT_RAW_REPORTS_PATH, DEFAULT_CHART_PATH


def load_reports(path: Union[str, Path] = DEFAULT_RAW_REPORTS_PATH) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    with open(p) as f:
        data = json.load(f)
    if isinstance(data, dict):
        reports = data.get("reports", [])
        return [dict(item) for item in reports if isinstance(item, dict)] if isinstance(reports, list) else []
    return [dict(item) for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def ingest_reports(store: ReportStore, raw_reports: List[Dict[str, Any]]) -> List[SymptomReport]:
    """Parses raw report dictionaries and stores them idempotently."""
    parsed: List[SymptomReport] = []
    for raw in raw_reports:
        result = parse_report(raw)
        store.insert(result.report)
        parsed.append(result.report)
    print(f"\nIngested {len(parsed)} reports into {store.db_path}.")
    return parsed


def report_conflicts(store: ReportStore) -> List[ConflictEvent]:
    """Detects and prints summary of cross-report conflicts."""
    conflicts = store.detect_conflicts()
    print(f"\n--- Detected {len(conflicts)} Conflict/Delta Events ---")
    for c in conflicts[:5]:
        print(f"  [{c.type}] Pt {c.patient_id} on {c.report_date}: {c.description}")
    return conflicts


def report_medication_deltas(store: ReportStore, reports: List[SymptomReport]) -> None:
    """Logs timeline medication changes across all patients."""
    print("\n--- Medication-Change Deltas (symptoms_after_medication_change) ---")
    unique_pids = sorted({r.patient_id for r in reports})
    total_changes = 0
    for pid in unique_pids:
        med_deltas = store.symptoms_after_medication_change(pid)
        total_changes += len(med_deltas)
        for d in med_deltas:
            added = f"+{','.join(d.added_medications)}" if d.added_medications else ""
            removed = f"-{','.join(d.removed_medications)}" if d.removed_medications else ""
            changes = " ".join(filter(None, [added, removed]))
            print(f"  Patient {pid} ({d.report_date}): {changes} [Report #{d.report_ids[0]}]")
    print(f"Total medication changes logged: {total_changes}")


def generate_baseline_chart(store: ReportStore, chart_path: Union[str, Path]) -> None:
    """Generates the multi-track symptom/weight trend chart for the first patient."""
    all_rows = store.latest_reports_dashboard()
    if all_rows:
        pid = all_rows[0].patient_id
        p_rows = [r for r in all_rows if r.patient_id == pid]
        sym = p_rows[0].symptom or "pain"
        out = symptom_trend_chart(p_rows, pid, sym, chart_path)
        print(f"Saved trend dashboard chart to {out}")


def run_pipeline(
    raw_path: Union[str, Path] = DEFAULT_RAW_REPORTS_PATH,
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
    chart_path: Union[str, Path] = DEFAULT_CHART_PATH,
    serve: bool = False,
    port: int = 8000,
    reset_db: bool = False,
) -> None:
    raw_reports = load_reports(raw_path)
    print(f"Loaded {len(raw_reports)} raw reports.")

    if reset_db and Path(db_path).exists():
        Path(db_path).unlink()
        print(f"Reset database at {db_path}.")

    with ReportStore(db_path) as store:
        parsed = ingest_reports(store, raw_reports)
        report_conflicts(store)
        report_medication_deltas(store, parsed)
        display_review_queue(store.review_queue())
        generate_baseline_chart(store, chart_path)

    if serve:
        import uvicorn
        from app import app
        print(f"\nStarting Clinical Dashboard server at http://127.0.0.1:{port}/dashboard ...")
        print(f"Review Queue API endpoint: http://127.0.0.1:{port}/review-queue")
        print(f"Conflicts API endpoint:    http://127.0.0.1:{port}/conflicts")
        uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    should_serve = "--serve" in sys.argv
    should_reset = "--reset-db" in sys.argv
    clean_args = [a for a in sys.argv[1:] if a not in ("--serve", "--reset-db")]
    r_path = clean_args[0] if len(clean_args) > 0 else DEFAULT_RAW_REPORTS_PATH
    d_path = clean_args[1] if len(clean_args) > 1 else DEFAULT_DB_PATH
    c_path = clean_args[2] if len(clean_args) > 2 else DEFAULT_CHART_PATH
    run_pipeline(r_path, d_path, c_path, serve=should_serve, reset_db=should_reset)
