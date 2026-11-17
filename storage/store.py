"""Data storage layer for patient reports using SQLite with versioning and audit trails."""

import sqlite3
from typing import List, Dict, Any, Optional, Tuple, Union, Self
from pathlib import Path
from domain.schema import (
    SymptomReport,
    StoredSymptomReport,
    ConflictEvent,
    PatientClinicalSummary,
)
from domain.conflicts import detect_all_conflicts, compute_medication_deltas
from constants import (
    DEFAULT_DB_PATH,
    LOW_CONFIDENCE_THRESHOLD,
    WEIGHT_LOSS_CLINICAL_THRESHOLD_PCT,
)
from storage.queries import (
    SCHEMA_SQL,
    QUERY_LATEST_DASHBOARD,
    QUERY_REVIEW_QUEUE,
    QUERY_VOMITING_EPISODES,
    QUERY_PATIENT_CLINICAL_SUMMARIES,
)
from storage.serializer import row_to_stored_report, report_to_insert_params


class ReportStore:
    def __init__(self, db_path: Union[str, Path] = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def insert(self, report: SymptomReport) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO symptom_reports
            (patient_id, patient_name, report_date, report_time, raw_text, timestamp,
             symptom, severity, frequency, medications, side_effects, confidence, flags, source, questionnaire)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            report_to_insert_params(report),
        )
        self.conn.commit()

        if cur.lastrowid and cur.rowcount > 0:
            return int(cur.lastrowid)

        cur.execute(
            """
            SELECT id FROM symptom_reports
            WHERE patient_id = ? AND timestamp = ? AND raw_text = ?
            LIMIT 1
            """,
            (report.patient_id, report.timestamp.isoformat(), report.raw_text),
        )
        existing = cur.fetchone()
        if existing is None:
            raise RuntimeError("Database insertion failed to yield a row id")
        return int(str(existing[0]))

    def insert_many(self, reports: List[SymptomReport]) -> List[int]:
        return [self.insert(r) for r in reports]

    def vomiting_episodes_per_week(self, patient_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(QUERY_VOMITING_EPISODES, (patient_id,))
        rows = cur.fetchall()
        return [
            {
                "week": r[0],
                "episode_count": int(r[1]),
                "avg_severity": round(float(r[2]), 2) if r[2] is not None else None,
                "peak_severity": int(r[3]) if r[3] is not None else None,
            }
            for r in rows
        ]

    def patient_clinical_summaries(self, patient_id: Optional[str] = None) -> List[PatientClinicalSummary]:
        """Computes per-patient clinical risk metrics, severity bounds, and weight-loss percentage in SQL."""
        where_clause = "WHERE patient_id = ?" if patient_id else ""
        params: Tuple[Any, ...] = (
            (patient_id, LOW_CONFIDENCE_THRESHOLD)
            if patient_id
            else (LOW_CONFIDENCE_THRESHOLD,)
        )
        cur = self.conn.cursor()
        cur.execute(QUERY_PATIENT_CLINICAL_SUMMARIES.format(where_clause=where_clause), params)
        summaries: List[PatientClinicalSummary] = []
        for row in cur.fetchall():
            weight_pct = float(row[7]) if row[7] is not None else None
            summaries.append(
                PatientClinicalSummary(
                    patient_id=str(row[0]),
                    patient_name=str(row[1]),
                    total_reports=int(row[2]),
                    peak_severity=int(row[3]) if row[3] is not None else None,
                    avg_severity=float(row[4]) if row[4] is not None else None,
                    baseline_weight_lbs=float(row[5]) if row[5] is not None else None,
                    latest_weight_lbs=float(row[6]) if row[6] is not None else None,
                    weight_change_pct=weight_pct,
                    clinically_significant_weight_loss=(
                        weight_pct is not None and weight_pct <= WEIGHT_LOSS_CLINICAL_THRESHOLD_PCT
                    ),
                    review_flag_count=int(row[8] or 0),
                )
            )
        return summaries

    def symptoms_after_medication_change(self, patient_id: str) -> List[ConflictEvent]:
        reports = self.all_reports(patient_id)
        return compute_medication_deltas(reports)

    def _query_reports(self, sql: str, params: Tuple[Any, ...] = ()) -> List[StoredSymptomReport]:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [row_to_stored_report(cols, r) for r in cur.fetchall()]

    def all_reports(self, patient_id: Optional[str] = None) -> List[StoredSymptomReport]:
        if patient_id:
            return self._query_reports(
                "SELECT * FROM symptom_reports WHERE patient_id = ? ORDER BY timestamp",
                (patient_id,),
            )
        return self._query_reports("SELECT * FROM symptom_reports ORDER BY timestamp")

    def detect_conflicts(self, patient_id: Optional[str] = None) -> List[ConflictEvent]:
        reports = self.all_reports(patient_id)
        return detect_all_conflicts(reports)

    def latest_reports_dashboard(self, patient_id: Optional[str] = None) -> List[StoredSymptomReport]:
        where_clause = "WHERE sr.patient_id = ?" if patient_id else ""
        params: Tuple[Any, ...] = (patient_id,) if patient_id else ()
        return self._query_reports(
            QUERY_LATEST_DASHBOARD.format(where_clause=where_clause),
            params,
        )

    def review_queue(self, patient_id: Optional[str] = None) -> List[StoredSymptomReport]:
        patient_filter = "AND sr.patient_id = ?" if patient_id else ""
        params: Tuple[Any, ...] = (
            (LOW_CONFIDENCE_THRESHOLD, patient_id)
            if patient_id
            else (LOW_CONFIDENCE_THRESHOLD,)
        )
        return self._query_reports(
            QUERY_REVIEW_QUEUE.format(patient_filter=patient_filter),
            params,
        )

    def get_report_by_id(self, report_id: int) -> Optional[StoredSymptomReport]:
        """Fetches a single stored symptom report by primary key id."""
        rows = self._query_reports("SELECT * FROM symptom_reports WHERE id = ?", (report_id,))
        return rows[0] if rows else None

    def close(self) -> None:
        self.conn.close()
