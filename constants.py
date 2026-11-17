"""Centralized configuration and domain constants for clinical PRO analysis."""

from typing import Dict, List
from pathlib import Path

# Paths computed dynamically relative to this file (no hardcoded absolute or working directory paths)
PROJECT_ROOT: Path = Path(__file__).resolve().parent
DATA_DIR: Path = PROJECT_ROOT / "data"
DEFAULT_DB_PATH: Path = DATA_DIR / "reports.db"
DEFAULT_RAW_REPORTS_PATH: Path = DATA_DIR / "patient_reports.json"
DEFAULT_CHART_PATH: Path = DATA_DIR / "trend.png"

# Confidence & quality thresholds
LOW_CONFIDENCE_THRESHOLD: float = 0.6
CONTRADICTION_SEVERITY_DELTA_THRESHOLD: int = 2
WEIGHT_LOSS_CLINICAL_THRESHOLD_PCT: float = -5.0

# Severity mappings from patient natural language
SEVERITY_MAP: Dict[str, int] = {
    "mild": 3,
    "moderate": 5,
    "severe": 8,
    "extreme": 10,
    "little": 3,
    "some": 5,
    "bad": 7,
    "awful": 8,
}

# Symptom keywords for classification
SYMPTOM_KEYWORDS: Dict[str, List[str]] = {
    "mouth_sores": ["mouth sore", "mouth sores", "canker", "oral", "tongue", "gum"],
    "pain": ["pain", "hurt", "hurting", "ache", "sore", "throat pain"],
    "swallowing": ["swallow", "swallowing", "gulp", "throat"],
    "weight_loss": ["weight", "pound", "lost weight", "weigh"],
    "nausea": ["nausea", "nauseous", "throw up", "vomiting", "vomit", "sick to stomach"],
    "fatigue": ["tired", "fatigue", "exhausted", "weak", "weakness"],
}

# Recognized oncology medications for Head & Neck cancer
MEDICATION_HINTS: List[str] = [
    "oxycodone",
    "morphine",
    "ondansetron",
    "zofran",
    "magic mouthwash",
    "lidocaine",
    "ibuprofen",
    "acetaminophen",
    "tylenol",
    "gabapentin",
]

# Standard frequency strings
FREQUENCY_HINTS: List[str] = [
    "daily",
    "after meals",
    "at night",
    "morning",
    "evening",
    "twice daily",
    "once daily",
]

# Display labels & flag subsets for triage UI and charts
FLAG_LABELS: Dict[str, str] = {
    "conflicting_report": "Questionnaire Mismatch",
    "raw_text_questionnaire_contradiction": "Questionnaire Mismatch",
    "missing_severity": "Missing Severity",
    "low_confidence": "Low Confidence",
    "medication_change": "Med Change",
}

CONFLICT_LABELS: Dict[str, str] = {
    "same_day_divergence": "Same-Day Divergence",
    "raw_text_questionnaire_contradiction": "Questionnaire Mismatch",
    "medication_change": "Med Change",
}

CHART_ANNOTATION_FLAGS: frozenset[str] = frozenset({
    "conflicting_report",
    "raw_text_questionnaire_contradiction",
})
