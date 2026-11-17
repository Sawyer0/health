"""Free-text rule extraction and questionnaire validation for patient reports."""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from domain.schema import SymptomReport, ParseResult
from constants import (
    SEVERITY_MAP,
    SYMPTOM_KEYWORDS,
    MEDICATION_HINTS,
    FREQUENCY_HINTS,
    LOW_CONFIDENCE_THRESHOLD,
    CONTRADICTION_SEVERITY_DELTA_THRESHOLD,
)

SEVERITY_PATTERN = re.compile(
    r"(?:pain|severity|closer to|about|around|rated|rated a|level|was an|maybe a|probably a|is a|down to|at a)\s*[:=]?\s*(?:an\s+|a\s+)?(10|[1-9])\b"
)


def rule_based_extract(raw_text: str) -> Dict[str, Any]:
    text = raw_text.lower()
    symptom = next((k for k, kws in SYMPTOM_KEYWORDS.items() if any(kw in text for kw in kws)), "other")

    severity: Optional[int] = None
    num_match = SEVERITY_PATTERN.search(text)
    if num_match:
        severity = int(num_match.group(1))
    else:
        severity = next((val for word, val in SEVERITY_MAP.items() if word in text), None)

    frequency = next((freq for freq in FREQUENCY_HINTS if freq in text), None)
    medications = [m for m in MEDICATION_HINTS if m in text]
    side_effects = [s for s, terms in [("nausea", ["nausea", "vomit"]), ("mouth_sores", ["mouth sore"])] if any(t in text for t in terms)]

    return {
        "symptom": symptom,
        "severity": severity,
        "frequency": frequency,
        "medications": medications,
        "side_effects": side_effects,
        "confidence": 0.5 if symptom != "other" else 0.3,
    }


def parse_report(raw_report: Dict[str, Any]) -> ParseResult:
    raw_text = str(raw_report.get("raw_text", ""))
    ts_str = str(raw_report.get("timestamp") or f"{raw_report.get('report_date', '')} {raw_report.get('report_time', '00:00')}")
    try:
        timestamp = datetime.fromisoformat(ts_str.replace(" ", "T"))
    except ValueError:
        timestamp = datetime.now()

    warnings: List[str] = [str(f) for f in raw_report.get("flags", []) if isinstance(raw_report.get("flags"), list)]
    rule = rule_based_extract(raw_text)

    if "symptom" in raw_report and ("severity" in raw_report or "confidence" in raw_report):
        extracted = {k: raw_report.get(k) for k in ["symptom", "severity", "frequency", "medications", "side_effects", "confidence"]}
        method = str(raw_report.get("source", "pre-extracted"))
    else:
        warnings.append("llm_failed:LLM extraction hook not configured; using rules")
        extracted = rule
        method = "rule"

    symptom = extracted.get("symptom") or rule.get("symptom")
    severity = extracted.get("severity") if extracted.get("severity") is not None else rule.get("severity")
    frequency = extracted.get("frequency") or rule.get("frequency")
    medications = list(set((extracted.get("medications") or []) + rule.get("medications", [])))
    confidence = float(str(extracted.get("confidence") or rule.get("confidence", 0.5)))

    if confidence < LOW_CONFIDENCE_THRESHOLD and "low_confidence" not in warnings:
        warnings.append("low_confidence")

    questionnaire = raw_report.get("questionnaire")
    if isinstance(questionnaire, dict) and severity is not None:
        q_sev = questionnaire.get("pain") if questionnaire.get("pain") is not None else questionnaire.get(str(symptom))
        if q_sev is not None and abs(int(severity) - int(q_sev)) >= CONTRADICTION_SEVERITY_DELTA_THRESHOLD:
            if "conflicting_report" not in warnings:
                warnings.append("conflicting_report")

    report = SymptomReport(
        patient_id=str(raw_report.get("patient_id", "UNKNOWN")),
        patient_name=str(raw_report.get("patient_name", "Unknown Patient")),
        report_date=str(raw_report.get("report_date", "")),
        report_time=str(raw_report.get("report_time", "")),
        raw_text=raw_text,
        timestamp=timestamp,
        symptom=symptom,
        severity=severity,
        frequency=frequency,
        medications=medications,
        side_effects=extracted.get("side_effects") or rule.get("side_effects", []),
        confidence=confidence,
        flags=warnings,
        source=str(raw_report.get("source", "synthetic")),
        questionnaire=questionnaire if isinstance(questionnaire, dict) else None,
    )
    return ParseResult(report=report, method=method, warnings=warnings)
