"""SQLite table schema definitions and DDL for the patient health store."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS symptom_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    patient_name TEXT NOT NULL,
    report_date TEXT NOT NULL,
    report_time TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    symptom TEXT,
    severity INTEGER,
    frequency TEXT,
    medications TEXT,       -- JSON list
    side_effects TEXT,      -- JSON list
    confidence REAL NOT NULL,
    flags TEXT,             -- JSON list
    source TEXT NOT NULL,
    questionnaire TEXT,     -- JSON object
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_patient_timestamp ON symptom_reports(patient_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_symptom ON symptom_reports(symptom);
CREATE INDEX IF NOT EXISTS idx_confidence ON symptom_reports(confidence);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_report ON symptom_reports(patient_id, timestamp, raw_text);
"""

QUERY_LATEST_DASHBOARD = """
SELECT sr.*
FROM symptom_reports sr
INNER JOIN (
    SELECT patient_id, report_date, MAX(id) as max_id
    FROM symptom_reports
    GROUP BY patient_id, report_date
) latest ON sr.id = latest.max_id
"""

QUERY_VOMITING_EPISODES = """
SELECT
    strftime('%Y-%m-%d', timestamp, '-6 days', 'weekday 0', '+1 day') AS week_start,
    COUNT(*) AS episode_count,
    AVG(COALESCE(severity, 0)) AS avg_severity
FROM symptom_reports
WHERE patient_id = ?
  AND symptom = 'nausea'
GROUP BY week_start
ORDER BY week_start
"""
