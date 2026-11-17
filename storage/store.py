"""Data storage layer for patient reports using SQLite with versioning and audit trails."""

import sqlite3
from typing import List, Dict, Any, Optional, Tuple, Union, Self
from pathlib import Path
from domain.schema import SymptomReport, StoredSymptomReport, ConflictEvent
from domain.conflicts import detect_all_conflicts, compute_medication_deltas, is_review_candidate
from constants import DEFAULT_DB_PATH
from storage.queries import SCHEMA_SQL, QUERY_LATEST_DASHBOARD, QUERY_VOMITING_EPISODES
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
            {"week": r[0], "episode_count": r[1], "avg_severity": round(r[2], 2) if r[2] else None}
            for r in rows
        ]

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
        query = QUERY_LATEST_DASHBOARD
        params: Tuple[Any, ...] = ()
        if patient_id:
            query += " WHERE sr.patient_id = ? "
            params = (patient_id,)
        query += " ORDER BY sr.patient_id, sr.timestamp"
        return self._query_reports(query, params)

    def review_queue(self, patient_id: Optional[str] = None) -> List[StoredSymptomReport]:
        query = "SELECT * FROM symptom_reports "
        params: Tuple[Any, ...] = ()
        if patient_id:
            query += "WHERE patient_id = ? "
            params = (patient_id,)
        query += "ORDER BY timestamp DESC"
        return [r for r in self._query_reports(query, params) if is_review_candidate(r)]

    def get_report_by_id(self, report_id: int) -> Optional[StoredSymptomReport]:
        """Fetches a single stored symptom report by primary key id."""
        rows = self._query_reports("SELECT * FROM symptom_reports WHERE id = ?", (report_id,))
        return rows[0] if rows else None

    def close(self) -> None:
        self.conn.close()
