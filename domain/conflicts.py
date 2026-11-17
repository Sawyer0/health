"""Pure domain rules for detecting clinical conflicts, medication deltas, and review queue candidates."""

from typing import List, Optional, Set, Tuple
from domain.schema import StoredSymptomReport, ConflictEvent
from constants import LOW_CONFIDENCE_THRESHOLD


def detect_same_day_divergence(
    reports: List[StoredSymptomReport]
) -> List[ConflictEvent]:
    by_patient_date: dict[Tuple[str, str], List[StoredSymptomReport]] = {}
    for r in reports:
        by_patient_date.setdefault((r.patient_id, r.report_date), []).append(r)

    conflicts: List[ConflictEvent] = []
    for (pid, date_str), day_rows in by_patient_date.items():
        if len(day_rows) > 1:
            severities = [r.severity for r in day_rows if r.severity is not None]
            if len(set(severities)) > 1:
                latest_report = max(day_rows, key=lambda x: x.timestamp)
                conflicts.append(
                    ConflictEvent(
                        type="same_day_divergence",
                        patient_id=pid,
                        report_date=date_str,
                        timestamp=latest_report.timestamp.isoformat(),
                        description=(
                            f"Multiple reports on {date_str} for patient {pid} with divergent severities: {severities}. "
                            "Latest timestamp takes precedence for dashboard."
                        ),
                        report_ids=[r.id for r in day_rows],
                    )
                )
    return conflicts


def detect_questionnaire_contradictions(
    reports: List[StoredSymptomReport]
) -> List[ConflictEvent]:
    conflicts: List[ConflictEvent] = []
    for r in reports:
        if "conflicting_report" in r.flags or "raw_text_questionnaire_contradiction" in r.flags:
            conflicts.append(
                ConflictEvent(
                    type="raw_text_questionnaire_contradiction",
                    patient_id=r.patient_id,
                    report_date=r.report_date,
                    timestamp=r.timestamp.isoformat(),
                    description=f"Report ID {r.id} has contradictory severity between raw text and questionnaire: '{r.raw_text}'",
                    report_ids=[r.id],
                )
            )
    return conflicts


def compute_medication_deltas(
    reports: List[StoredSymptomReport]
) -> List[ConflictEvent]:
    by_patient: dict[str, List[StoredSymptomReport]] = {}
    for r in reports:
        by_patient.setdefault(r.patient_id, []).append(r)

    changes: List[ConflictEvent] = []
    for pid, p_rows in by_patient.items():
        sorted_rows = sorted(p_rows, key=lambda x: x.timestamp)
        prev_meds: Optional[Set[str]] = None
        for r in sorted_rows:
            current_meds = set(r.medications)
            if prev_meds is not None and current_meds != prev_meds:
                added = sorted(current_meds - prev_meds)
                removed = sorted(prev_meds - current_meds)
                changes.append(
                    ConflictEvent(
                        type="medication_change",
                        patient_id=pid,
                        report_date=r.report_date,
                        timestamp=r.timestamp.isoformat(),
                        added_medications=added,
                        removed_medications=removed,
                        description=f"Medication regimen changed on {r.timestamp.isoformat()}: added={added}, removed={removed}",
                        report_ids=[r.id],
                    )
                )
            prev_meds = current_meds
    return changes


def detect_all_conflicts(
    reports: List[StoredSymptomReport]
) -> List[ConflictEvent]:
    return (
        detect_same_day_divergence(reports)
        + detect_questionnaire_contradictions(reports)
        + compute_medication_deltas(reports)
    )


def is_review_candidate(report: StoredSymptomReport) -> bool:
    """
    Determines whether a report requires clinical triage / review queue presence.
    Reports flagged solely for weight_loss_alert are chart-level concerns and excluded.
    """
    review_flags = [f for f in report.flags if f != "weight_loss_alert"]
    return bool(review_flags or report.confidence < LOW_CONFIDENCE_THRESHOLD or report.severity is None)
