"""Badge rendering primitive."""

import html


def render_badge(text: str, badge_type: str) -> str:
    """Renders a standard badge element."""
    return f'<span class="badge badge-{badge_type}">{html.escape(text)}</span>'
