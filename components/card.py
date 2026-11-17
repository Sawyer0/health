"""Base reusable card container component."""

import html
from typing import Dict, Optional, List


def render_card(
    patient_id: str,
    title_suffix: str,
    meta_badges: List[str],
    timestamp_str: str,
    summary_text: str,
    detail_kv: Dict[str, str],
    custom_detail_html: str = "",
    extra_badges: Optional[List[str]] = None,
    card_modifier: str = "",
    onclick_attr: str = "this.classList.toggle('open')",
    data_attrs: str = "",
    body_html: str = "",
) -> str:
    """
    Unified reusable card container.
    Supports either single-report layout or multi-page (paginated) body_html.
    """
    badges_html = " ".join(extra_badges or [])
    meta_html = " ".join(meta_badges)
    card_class = f"card {card_modifier}".strip()
    id_html = f'<span class="patient-id">{html.escape(patient_id)}</span>' if patient_id else ""
    ts_html = f'<span class="timestamp">{html.escape(timestamp_str)}</span>' if timestamp_str else ""

    if body_html:
        inner_content = body_html
    else:
        detail_items = "".join(
            f"<div><strong>{html.escape(k)}:</strong> {html.escape(v)}</div>"
            for k, v in detail_kv.items()
        )
        inner_content = f"""
        <p class="summary-line">{html.escape(summary_text)}</p>
        {f'<div class="card-badges">{badges_html}</div>' if badges_html else ''}
        <div class="card-detail">
            <div class="detail-grid">
                {detail_items}
            </div>
            {custom_detail_html}
        </div>
        """

    return f"""
    <article class="{card_class}" onclick="{onclick_attr}" {data_attrs}>
        <header class="card-header">
            <div class="card-title">
                {id_html}
                {title_suffix}
            </div>
            <div class="card-meta">
                {meta_html}
                {ts_html}
            </div>
        </header>
        {inner_content}
    </article>
    """
