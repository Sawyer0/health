"""Pydantic domain models for clinical PRO ingestion, storage, and conflict detection."""

from pydantic import BaseModel, Field, model_validator, ConfigDict
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

from constants import LOW_CONFIDENCE_THRESHOLD


class SymptomReport(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    patient_id: str
    patient_name: str
    report_date: str
    report_time: str
    raw_text: str
    timestamp: datetime
    symptom: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=10)
    frequency: Optional[str] = None
    medications: List[str] = []
    side_effects: List[str] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = []
    source: str = "synthetic"
    questionnaire: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_flags(self) -> "SymptomReport":
        if self.severity is None and self.raw_text:
            if "missing_severity" not in self.flags:
                self.flags.append("missing_severity")
        if self.confidence < LOW_CONFIDENCE_THRESHOLD:
            if "low_confidence" not in self.flags:
                self.flags.append("low_confidence")
        return self


class ParseResult(BaseModel):
    report: SymptomReport
    method: str
    warnings: List[str] = []


class StoredSymptomReport(SymptomReport):
    """SymptomReport persisted with primary key id and created_at metadata."""
    id: int
    created_at: Optional[str] = None


class ConflictEvent(BaseModel):
    """Structured domain model for patient conflict and anomaly events."""
    type: Literal["same_day_divergence", "raw_text_questionnaire_contradiction", "medication_change"]
    patient_id: str
    report_date: str
    description: str
    report_ids: List[int]
    timestamp: Optional[str] = None
    added_medications: List[str] = []
    removed_medications: List[str] = []


class PatientClinicalSummary(BaseModel):
    """Business/clinical risk summary per patient across their reporting timeline."""
    patient_id: str
    patient_name: str
    total_reports: int
    peak_severity: Optional[int] = None
    avg_severity: Optional[float] = None
    baseline_weight_lbs: Optional[float] = None
    latest_weight_lbs: Optional[float] = None
    weight_change_pct: Optional[float] = None
    clinically_significant_weight_loss: bool = False
    review_flag_count: int = 0
