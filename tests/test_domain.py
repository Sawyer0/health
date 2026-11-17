"""Unit tests for domain schemas, bounds validation, and free-text parser."""

import pytest
from domain import parse_report
from tests.conftest import make_report


def test_vague_data_preserves_text_and_sets_flags() -> None:
    data = {
        "patient_id": "P01",
        "patient_name": "Alex",
        "report_date": "2026-10-25",
        "raw_text": "Felt completely off today.",
        "confidence": 0.45,
    }
    report = parse_report(data).report
    assert report.severity is None
    assert report.frequency is None
    assert report.raw_text == data["raw_text"]
    assert "missing_severity" in report.flags
    assert "low_confidence" in report.flags


@pytest.mark.parametrize("invalid_severity", [0, 11])
def test_rejects_out_of_bounds_severity(invalid_severity: int) -> None:
    with pytest.raises(Exception):
        make_report(severity=invalid_severity)


@pytest.mark.parametrize(
    "raw_text,expected_severity",
    [
        ("Pain was an 8 this morning.", 8),
        ("Pain has settled down to 3 now.", 3),
    ],
)
def test_extracts_numeric_severity(raw_text: str, expected_severity: int) -> None:
    result = parse_report({
        "patient_id": "P01",
        "patient_name": "Alex",
        "report_date": "2026-10-31",
        "raw_text": raw_text,
    })
    assert result.report.severity == expected_severity


def test_detects_contradiction_between_text_and_questionnaire() -> None:
    result = parse_report({
        "patient_id": "P04",
        "patient_name": "Jordan",
        "report_date": "2026-10-24",
        "raw_text": "I feel nauseous after lunch.",
        "symptom": "nausea",
        "severity": 4,
        "questionnaire": {"nausea": 9},
    })
    assert "conflicting_report" in result.report.flags
