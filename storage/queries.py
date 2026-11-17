"""SQLite table schema definitions and clinical/business analytical SQL queries."""

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

# Deterministically picks the latest report per (patient_id, report_date) by timestamp DESC,
# using id DESC only as a tie-breaker when two reports share the exact same minute.
QUERY_LATEST_DASHBOARD = """
WITH ranked_reports AS (
    SELECT
        sr.*,
        ROW_NUMBER() OVER (
            PARTITION BY sr.patient_id, sr.report_date
            ORDER BY sr.timestamp DESC, sr.id DESC
        ) AS rn
    FROM symptom_reports sr
    {where_clause}
)
SELECT
    id, patient_id, patient_name, report_date, report_time, raw_text, timestamp,
    symptom, severity, frequency, medications, side_effects, confidence,
    flags, source, questionnaire, created_at
FROM ranked_reports
WHERE rn = 1
ORDER BY patient_id, timestamp
"""

# Filters triage candidates directly in SQL: missing severity, low confidence,
# or clinical flags other than chart-only weight_loss_alert.
QUERY_REVIEW_QUEUE = """
SELECT sr.*
FROM symptom_reports sr
WHERE (
    sr.severity IS NULL
    OR sr.confidence < ?
    OR EXISTS (
        SELECT 1
        FROM json_each(COALESCE(sr.flags, '[]')) AS jf
        WHERE jf.value != 'weight_loss_alert'
    )
)
{patient_filter}
ORDER BY sr.timestamp DESC, sr.id DESC
"""

# Weekly nausea/vomiting episode burden:
# - Matches primary symptom = 'nausea', 'nausea' in side_effects JSON array, or vomit/nausea text
# - Uses true AVG(severity) (ignoring NULLs instead of coercing NULL -> 0)
QUERY_VOMITING_EPISODES = """
SELECT
    strftime('%Y-%m-%d', sr.timestamp, '-6 days', 'weekday 0', '+1 day') AS week_start,
    COUNT(*) AS episode_count,
    AVG(sr.severity) AS avg_severity,
    MAX(sr.severity) AS peak_severity
FROM symptom_reports sr
WHERE sr.patient_id = ?
  AND (
      sr.symptom = 'nausea'
      OR EXISTS (
          SELECT 1 FROM json_each(COALESCE(sr.side_effects, '[]')) AS se
          WHERE se.value = 'nausea'
      )
      OR lower(sr.raw_text) LIKE '%vomit%'
      OR lower(sr.raw_text) LIKE '%nause%'
  )
GROUP BY week_start
ORDER BY week_start
"""

# Patient clinical & weight-loss risk summary across their timeline:
# Extracts baseline (first recorded) and latest weight from questionnaire JSON,
# computes percentage weight change, peak/average severity, and active triage flags.
QUERY_PATIENT_CLINICAL_SUMMARIES = """
WITH weight_timeline AS (
    SELECT
        patient_id,
        patient_name,
        id,
        timestamp,
        severity,
        confidence,
        flags,
        CAST(json_extract(questionnaire, '$.weight_lbs') AS REAL) AS weight_lbs
    FROM symptom_reports
    {where_clause}
),
patient_weights AS (
    SELECT DISTINCT
        patient_id,
        FIRST_VALUE(weight_lbs) OVER (
            PARTITION BY patient_id
            ORDER BY CASE WHEN weight_lbs IS NOT NULL THEN 0 ELSE 1 END, timestamp ASC, id ASC
        ) AS baseline_weight_lbs,
        FIRST_VALUE(weight_lbs) OVER (
            PARTITION BY patient_id
            ORDER BY CASE WHEN weight_lbs IS NOT NULL THEN 0 ELSE 1 END, timestamp DESC, id DESC
        ) AS latest_weight_lbs
    FROM weight_timeline
)
SELECT
    wt.patient_id,
    MAX(wt.patient_name) AS patient_name,
    COUNT(*) AS total_reports,
    MAX(wt.severity) AS peak_severity,
    ROUND(AVG(wt.severity), 2) AS avg_severity,
    pw.baseline_weight_lbs,
    pw.latest_weight_lbs,
    CASE
        WHEN pw.baseline_weight_lbs IS NOT NULL AND pw.baseline_weight_lbs > 0 AND pw.latest_weight_lbs IS NOT NULL
        THEN ROUND(((pw.latest_weight_lbs - pw.baseline_weight_lbs) / pw.baseline_weight_lbs) * 100.0, 2)
        ELSE NULL
    END AS weight_change_pct,
    SUM(
        CASE
            WHEN wt.severity IS NULL
              OR wt.confidence < ?
              OR EXISTS (
                  SELECT 1 FROM json_each(COALESCE(wt.flags, '[]')) AS jf
                  WHERE jf.value != 'weight_loss_alert'
              )
            THEN 1 ELSE 0
        END
    ) AS review_flag_count
FROM weight_timeline wt
JOIN patient_weights pw ON wt.patient_id = pw.patient_id
GROUP BY wt.patient_id
ORDER BY wt.patient_id
"""
