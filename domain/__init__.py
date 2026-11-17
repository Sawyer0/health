"""Pure domain layer: models, free-text parser, and conflict detection rules."""

from domain.schema import SymptomReport, ParseResult, StoredSymptomReport, ConflictEvent
from domain.parser import parse_report, rule_based_extract
from domain.conflicts import (
    detect_same_day_divergence,
    detect_questionnaire_contradictions,
    compute_medication_deltas,
    detect_all_conflicts,
    is_review_candidate,
)

__all__ = [
    "SymptomReport",
    "ParseResult",
    "StoredSymptomReport",
    "ConflictEvent",
    "parse_report",
    "rule_based_extract",
    "detect_same_day_divergence",
    "detect_questionnaire_contradictions",
    "compute_medication_deltas",
    "detect_all_conflicts",
    "is_review_candidate",
]
