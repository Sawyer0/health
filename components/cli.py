"""CLI tabular formatting for the clinical review queue."""

from typing import List
from domain.schema import StoredSymptomReport


def render_review_queue_table(queue: List[StoredSymptomReport]) -> str:
    """Renders tabular text for terminal triage display."""
    if not queue:
        return "Review queue is clear. No flagged or low-confidence reports."

    lines = [
        "=" * 95,
        "CLINICAL REVIEW QUEUE (TRIAGE DASHBOARD)",
        "=" * 95,
        f"{'ID':<4} | {'Pt ID':<6} | {'Timestamp':<16} | {'Conf':<6} | {'Sev':<4} | {'Flags':<30} | {'Raw Text'}",
        "-" * 95,
    ]
    for r in queue:
        r_id = str(r.id)
        p_id = str(r.patient_id)
        ts = r.timestamp.strftime("%Y-%m-%dT%H:%M")
        conf = f"{r.confidence:.2f}"
        sev = str(r.severity) if r.severity is not None else "None"
        flags_str = ", ".join(r.flags)
        if len(flags_str) > 28:
            flags_str = flags_str[:25] + "..."
        raw = r.raw_text
        if len(raw) > 35:
            raw = raw[:32] + "..."
        lines.append(f"{r_id:<4} | {p_id:<6} | {ts:<16} | {conf:<6} | {sev:<4} | {flags_str:<30} | {raw}")
    lines.append("=" * 95)
    return "\n".join(lines)


def display_review_queue(queue: List[StoredSymptomReport]) -> List[StoredSymptomReport]:
    print("\n" + render_review_queue_table(queue))
    return queue
