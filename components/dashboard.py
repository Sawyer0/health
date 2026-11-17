"""Dashboard page layout component (HTML shell, styles, and client-side interactions)."""

from typing import Sequence, Dict, List
from domain.schema import StoredSymptomReport, ConflictEvent, PatientClinicalSummary
from components.report_card import render_patient_paginated_card


DASHBOARD_CSS = """
:root {
    --bg: #f8fafc;
    --surface: #ffffff;
    --border: #e2e8f0;
    --border-hover: #cbd5e1;
    --text-main: #0f172a;
    --text-muted: #64748b;
    --primary: #0284c7;
    --danger: #dc2626;
    --danger-bg: #fef2f2;
    --warn: #d97706;
    --warn-bg: #fffbeb;
    --ok: #16a34a;
    --ok-bg: #f0fdf4;
    --conflict-bg: #eff6ff;
    --conflict: #1d4ed8;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text-main);
    padding: 1.5rem;
    line-height: 1.4;
}
header.dashboard-header {
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.75rem;
}
h1 { font-size: 1.25rem; font-weight: 700; color: var(--text-main); }
.dashboard-grid {
    max-width: 800px;
    margin: 0 auto;
}
.column-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}
.column-title { font-size: 0.95rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); }
.count-pill { background: var(--border); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 999px; font-weight: 600; color: var(--text-main); }
.card-list { display: flex; flex-direction: column; gap: 0.5rem; }
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.75rem 1rem;
    cursor: pointer;
    transition: all 0.15s ease;
}
.card:hover {
    border-color: var(--border-hover);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
}
.card.active {
    border-color: var(--primary);
    box-shadow: 0 0 0 1px var(--primary);
}
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.35rem;
}
.card-title { display: flex; align-items: center; gap: 0.45rem; }
.patient-name { font-size: 0.9rem; font-weight: 600; color: var(--text-main); }
.patient-mrn {
    display: none;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.72rem;
    color: var(--text-muted);
    background: #f1f5f9;
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
}
.card.open .patient-mrn, .patient-mrn.always-visible { display: inline-block; }
.card-meta { display: flex; align-items: center; gap: 0.5rem; }
.card-pager {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.05rem 0.2rem;
}
.pager-btn {
    background: none;
    border: none;
    color: var(--text-main);
    font-size: 0.95rem;
    line-height: 1;
    padding: 0.1rem 0.3rem;
    cursor: pointer;
    border-radius: 3px;
}
.pager-btn:hover:not(:disabled) { background: #e2e8f0; }
.pager-btn:disabled { color: #cbd5e1; cursor: default; }
.pager-status { font-size: 0.72rem; font-weight: 600; color: var(--text-muted); min-width: 2.2rem; text-align: center; }
.report-page { display: none; }
.report-page.active-page { display: block; }
.timestamp { font-size: 0.75rem; color: var(--text-muted); }
.summary-line {
    font-size: 0.85rem;
    color: #334155;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.card-badges { margin-top: 0.4rem; display: flex; flex-wrap: wrap; gap: 0.25rem; }
.badge {
    font-size: 0.7rem;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-weight: 600;
}
.badge-flag { background: var(--danger-bg); color: var(--danger); border: 1px solid #fecaca; }
.badge-warn { background: var(--warn-bg); color: var(--warn); border: 1px solid #fed7aa; }
.badge-conflict { background: var(--conflict-bg); color: var(--conflict); border: 1px solid #bfdbfe; text-transform: capitalize; }
.card-detail {
    display: none;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px dashed var(--border);
    font-size: 0.82rem;
}
.card.open .card-detail { display: block; }
.card.open .summary-line { white-space: normal; }
.detail-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.35rem 1rem;
    margin-bottom: 0.5rem;
    color: #475569;
}
.detail-notes {
    margin: 0 0 0.6rem 1.1rem;
    color: var(--conflict);
    font-weight: 500;
}
.detail-chart { margin-top: 0.6rem; }
.clinical-summary-strip {
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem;
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: 5px;
    padding: 0.4rem 0.65rem;
    margin-bottom: 0.5rem;
    font-size: 0.78rem;
    color: #334155;
}
.card-chart-img {
    width: 100%;
    height: auto;
    border-radius: 6px;
    border: 1px solid var(--border);
    display: block;
}
.empty-state {
    padding: 2rem;
    text-align: center;
    color: var(--text-muted);
    border: 1px dashed var(--border);
    border-radius: 6px;
    font-size: 0.85rem;
}
"""

DASHBOARD_JS = """
function selectCard(self) {
    const wasOpen = self.classList.contains('open');
    document.querySelectorAll('.card').forEach(function(c) {
        c.classList.remove('open');
        c.classList.remove('active');
    });
    if (!wasOpen) {
        self.classList.add('open');
        self.classList.add('active');
    }
}

function changeReportPage(btn, delta) {
    const card = btn.closest('.card');
    if (!card) return;
    const total = parseInt(card.getAttribute('data-total-pages') || '1', 10);
    const current = parseInt(card.getAttribute('data-current-page') || '0', 10);
    const next = current + delta;
    if (next < 0 || next >= total) return;

    card.setAttribute('data-current-page', String(next));
    const pages = card.querySelectorAll('.report-page');
    pages.forEach(function(p, idx) {
        if (idx === next) {
            p.classList.add('active-page');
            const ts = p.getAttribute('data-timestamp');
            const tsEl = card.querySelector('.card-header .timestamp');
            if (tsEl && ts) tsEl.textContent = ts;
        } else {
            p.classList.remove('active-page');
        }
    });

    const statusEl = card.querySelector('.pager-status');
    if (statusEl) statusEl.textContent = (next + 1) + ' / ' + total;

    const btns = card.querySelectorAll('.pager-btn');
    if (btns.length === 2) {
        btns[0].disabled = (next === 0);
        btns[1].disabled = (next === total - 1);
    }
}
"""


def render_dashboard_page(
    queue: Sequence[StoredSymptomReport],
    conflicts: Sequence[ConflictEvent],
    summaries: Sequence[PatientClinicalSummary] = (),
) -> str:
    """Renders the full Clinical PRO Triage Dashboard HTML document."""
    conflicts_by_report: Dict[int, List[ConflictEvent]] = {}
    for c in conflicts:
        for r_id in c.report_ids:
            conflicts_by_report.setdefault(r_id, []).append(c)

    summaries_by_pid: Dict[str, PatientClinicalSummary] = {
        s.patient_id: s for s in summaries
    }

    grouped_by_patient: Dict[str, List[StoredSymptomReport]] = {}
    for r in queue:
        grouped_by_patient.setdefault(r.patient_id, []).append(r)

    pids_by_name: Dict[str, set[str]] = {}
    for pid, p_reports in grouped_by_patient.items():
        pids_by_name.setdefault(p_reports[0].patient_name, set()).add(pid)

    queue_cards = [
        render_patient_paginated_card(
            p_reports,
            conflicts_by_report,
            show_mrn_in_header=len(pids_by_name.get(p_reports[0].patient_name, set())) > 1,
            clinical_summary=summaries_by_pid.get(pid),
        )
        for pid, p_reports in grouped_by_patient.items()
    ]

    rendered_queue = (
        "".join(queue_cards)
        if queue_cards
        else '<div class="empty-state">No items requiring review</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clinical PRO Triage Dashboard</title>
    <style>{DASHBOARD_CSS}</style>
</head>
<body>
    <header class="dashboard-header">
        <h1>Clinical PRO Triage Dashboard</h1>
    </header>
    <div class="dashboard-grid" id="dashboardGrid">
        <section>
            <div class="column-header">
                <span class="column-title">Review Queue</span>
                <span class="count-pill">{len(grouped_by_patient)} patients &bull; {len(queue)} reports</span>
            </div>
            <div class="card-list">
                {rendered_queue}
            </div>
        </section>
    </div>
    <script>{DASHBOARD_JS}</script>
</body>
</html>
"""
