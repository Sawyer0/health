"""Specialized report card components composing base card and badge primitives."""

import html
from typing import Dict, Sequence, List, Optional
from domain.schema import StoredSymptomReport, ConflictEvent, PatientClinicalSummary
from constants import LOW_CONFIDENCE_THRESHOLD, FLAG_LABELS, CONFLICT_LABELS
from components.badge import render_badge
from components.card import render_card


def _format_conflict_note(c: ConflictEvent) -> str:
    if c.type == "medication_change":
        parts: List[str] = []
        if c.added_medications:
            parts.append(f"Started {', '.join(c.added_medications)}")
        if c.removed_medications:
            parts.append(f"Stopped {', '.join(c.removed_medications)}")
        return "; ".join(parts) if parts else "Medication updated"
    if c.type == "same_day_divergence":
        return c.description.split(". Latest")[0]
    return ""


def _build_report_fields(
    r: StoredSymptomReport,
    associated_conflicts: Sequence[ConflictEvent] = (),
) -> tuple[List[str], Dict[str, str], List[str]]:
    seen_labels: set[str] = set()
    badges: List[str] = []

    for f in r.flags:
        if f == "weight_loss_alert" or f.startswith("llm_failed"):
            continue
        label = FLAG_LABELS.get(f, f.replace("_", " ").title())
        if label not in seen_labels:
            seen_labels.add(label)
            badges.append(render_badge(label, "flag"))

    notes: List[str] = []
    for c in associated_conflicts:
        label = CONFLICT_LABELS.get(c.type, c.type.replace("_", " ").title())
        if label not in seen_labels:
            seen_labels.add(label)
            badges.append(render_badge(label, "conflict"))
        note = _format_conflict_note(c)
        if note and note not in notes:
            notes.append(note)

    kv: Dict[str, str] = {}
    if r.symptom and r.symptom != "other":
        sev_str = f" ({r.severity}/10)" if r.severity is not None else " (unrated)"
        kv["Symptom"] = f"{r.symptom.replace('_', ' ').title()}{sev_str}"
    elif r.severity is not None:
        kv["Severity"] = f"{r.severity}/10"

    if r.frequency:
        kv["Frequency"] = r.frequency
    if r.medications:
        kv["Medications"] = ", ".join(r.medications)
    if r.side_effects:
        kv["Side Effects"] = ", ".join(s.replace("_", " ") for s in r.side_effects)
    if r.confidence < LOW_CONFIDENCE_THRESHOLD:
        kv["Confidence"] = f"{r.confidence:.0%}"

    if r.questionnaire:
        q_scores = [
            f"{k.replace('_', ' ')}: {v}"
            for k, v in r.questionnaire.items()
            if k != "weight_lbs"
        ]
        if q_scores:
            kv["Questionnaire"] = ", ".join(q_scores)
        if "weight_lbs" in r.questionnaire:
            kv["Weight"] = f"{r.questionnaire['weight_lbs']} lbs"

    return badges, kv, notes


def render_unified_report_card(
    r: StoredSymptomReport,
    associated_conflicts: Sequence[ConflictEvent] = (),
) -> str:
    """Renders a single clinical report card."""
    return render_patient_paginated_card([r], {r.id: list(associated_conflicts)})


def render_patient_paginated_card(
    reports: Sequence[StoredSymptomReport],
    conflicts_by_report: Dict[int, List[ConflictEvent]],
    show_mrn_in_header: bool = False,
    clinical_summary: Optional[PatientClinicalSummary] = None,
) -> str:
    """
    Renders a single patient card grouped by unique patient_id (MRN) with
    in-card pagination across all of that patient's review-queue reports.
    """
    first = reports[0]
    total = len(reports)

    mrn_class = "patient-mrn always-visible" if show_mrn_in_header else "patient-mrn"
    risk_badge = ""
    if clinical_summary and clinical_summary.clinically_significant_weight_loss and clinical_summary.weight_change_pct is not None:
        risk_badge = render_badge(f"Weight {clinical_summary.weight_change_pct:+.1f}%", "warn")

    title_html = (
        f'<span class="patient-name">{html.escape(first.patient_name)}</span>'
        f'<span class="{mrn_class}" title="Unique Patient ID (MRN)">MRN {html.escape(first.patient_id)}</span>'
        f'{risk_badge}'
    )

    pager_html = ""
    if total > 1:
        pager_html = (
            f'<div class="card-pager" onclick="event.stopPropagation()">'
            f'<button type="button" class="pager-btn" onclick="changeReportPage(this, -1)" disabled aria-label="Previous report">&lsaquo;</button>'
            f'<span class="pager-status">1 / {total}</span>'
            f'<button type="button" class="pager-btn" onclick="changeReportPage(this, 1)" aria-label="Next report">&rsaquo;</button>'
            f'</div>'
        )

    slides_html: List[str] = []
    for idx, r in enumerate(reports):
        badges, kv, notes = _build_report_fields(r, conflicts_by_report.get(r.id, []))
        badges_str = " ".join(badges)
        detail_items = "".join(
            f"<div><strong>{html.escape(k)}:</strong> {html.escape(v)}</div>"
            for k, v in kv.items()
        )
        notes_html = ""
        if notes:
            items = "".join(f"<li>{html.escape(n)}</li>" for n in notes)
            notes_html = f'<ul class="detail-notes">{items}</ul>'

        active_cls = " active-page" if idx == 0 else ""
        ts_str = r.timestamp.strftime("%b %d, %H:%M")

        slides_html.append(f"""
        <div class="report-page{active_cls}" data-page-index="{idx}" data-timestamp="{html.escape(ts_str)}">
            <p class="summary-line">{html.escape(r.raw_text)}</p>
            {f'<div class="card-badges">{badges_str}</div>' if badges_str else ''}
            <div class="card-detail">
                <div class="detail-grid">
                    {detail_items}
                </div>
                {notes_html}
            </div>
        </div>
        """)

    summary_strip_html = ""
    if clinical_summary:
        metrics: List[str] = []
        if clinical_summary.baseline_weight_lbs is not None and clinical_summary.latest_weight_lbs is not None:
            pct_str = f" ({clinical_summary.weight_change_pct:+.1f}%)" if clinical_summary.weight_change_pct is not None else ""
            metrics.append(f"<span><strong>Trajectory:</strong> {clinical_summary.baseline_weight_lbs} &rarr; {clinical_summary.latest_weight_lbs} lbs{pct_str}</span>")
        if clinical_summary.avg_severity is not None and clinical_summary.peak_severity is not None:
            metrics.append(f"<span><strong>Severity:</strong> Avg {clinical_summary.avg_severity:.1f} &bull; Peak {clinical_summary.peak_severity}/10</span>")
        if metrics:
            summary_strip_html = f'<div class="clinical-summary-strip">{"".join(metrics)}</div>'

    chart_html = f"""
    <div class="card-detail detail-chart">
        {summary_strip_html}
        <img src="/patient/{html.escape(first.patient_id)}/chart" alt="Patient trend chart" class="card-chart-img">
    </div>
    """

    return render_card(
        patient_id="",
        title_suffix=title_html,
        meta_badges=[pager_html] if pager_html else [],
        timestamp_str=first.timestamp.strftime("%b %d, %H:%M"),
        summary_text="",
        detail_kv={},
        onclick_attr="selectCard(this)",
        data_attrs=f'data-patient-id="{html.escape(first.patient_id)}" data-total-pages="{total}" data-current-page="0"',
        body_html="".join(slides_html) + chart_html,
    )
