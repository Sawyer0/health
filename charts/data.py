"""Time-series data preparation for longitudinal patient charts."""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Sequence, Union
from domain.schema import StoredSymptomReport
from constants import CHART_ANNOTATION_FLAGS


class ChartSeries:
    def __init__(
        self,
        dates: List[datetime],
        severities: List[Optional[int]],
        weights: List[Optional[float]],
        flagged_points: List[Tuple[datetime, int, str]],
        meds_by_date: List[Tuple[datetime, List[str]]],
    ) -> None:
        self.dates = dates
        self.severities = severities
        self.weights = weights
        self.flagged_points = flagged_points
        self.meds_by_date = meds_by_date


def prepare_chart_series(rows: Sequence[Union[Dict[str, Any], StoredSymptomReport]]) -> ChartSeries:
    """Normalizes and extracts chronological chart time-series data."""
    normalized: List[Dict[str, Any]] = []
    for r in rows:
        if isinstance(r, StoredSymptomReport):
            normalized.append({
                "timestamp": r.timestamp.isoformat(),
                "severity": r.severity,
                "symptom": r.symptom,
                "questionnaire_parsed": r.questionnaire or {},
                "flags_parsed": r.flags,
                "meds_parsed": r.medications,
            })
        else:
            normalized.append(r)

    sorted_rows = sorted(normalized, key=lambda x: str(x.get("timestamp", "")))

    dates: List[datetime] = []
    severities: List[Optional[int]] = []
    weights: List[Optional[float]] = []
    flagged: List[Tuple[datetime, int, str]] = []
    meds: List[Tuple[datetime, List[str]]] = []

    for r in sorted_rows:
        ts_str = str(r.get("timestamp", ""))
        try:
            dt = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        dates.append(dt)

        sev = r.get("severity")
        severities.append(int(sev) if sev is not None else None)

        q = r.get("questionnaire_parsed") or {}
        w = q.get("weight_lbs")
        weights.append(float(w) if w is not None else None)

        flags = [f for f in (r.get("flags_parsed") or []) if f in CHART_ANNOTATION_FLAGS]
        if sev is not None and flags:
            flagged.append((dt, int(sev), "Mismatch"))

        med_list = r.get("meds_parsed") or []
        if med_list:
            meds.append((dt, med_list))

    return ChartSeries(dates, severities, weights, flagged, meds)
