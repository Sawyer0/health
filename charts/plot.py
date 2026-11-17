"""Longitudinal symptom progression and weight trajectory multi-track plotting."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, Any, Union, Sequence, BinaryIO, overload
from pathlib import Path
from domain.schema import StoredSymptomReport
from constants import DEFAULT_CHART_PATH
from charts.data import prepare_chart_series, ChartSeries


@overload
def symptom_trend_chart(
    rows: Sequence[Union[Dict[str, Any], StoredSymptomReport]],
    patient_id: str,
    symptom: str = ...,
    out_path: Union[str, Path] = ...,
) -> Path: ...


@overload
def symptom_trend_chart(
    rows: Sequence[Union[Dict[str, Any], StoredSymptomReport]],
    patient_id: str,
    symptom: str = ...,
    out_path: BinaryIO = ...,
) -> BinaryIO: ...


def symptom_trend_chart(
    rows: Sequence[Union[Dict[str, Any], StoredSymptomReport]],
    patient_id: str,
    symptom: str = "pain",
    out_path: Union[str, Path, BinaryIO] = DEFAULT_CHART_PATH,
) -> Union[Path, BinaryIO]:
    """Renders dual-track clinical visualization: severity progression and weight tracking."""
    target: Union[Path, BinaryIO]
    if isinstance(out_path, (str, Path)):
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        target = p
    else:
        target = out_path

    series: ChartSeries = prepare_chart_series(rows)
    if not series.dates:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, f"No data recorded for patient {patient_id}", ha="center", va="center")
        ax.axis("off")
        fig.savefig(target, bbox_inches="tight")
        plt.close(fig)
        return target

    fig, (ax_sev, ax_weight) = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(10, 5.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.8, 1.1]}
    )

    # Panel 1: Severity Trend
    ax_sev.axhspan(0, 3.5, color="#f0fdf4", alpha=0.8)
    ax_sev.axhspan(3.5, 6.5, color="#fefce8", alpha=0.8)
    ax_sev.axhspan(6.5, 10.5, color="#fef2f2", alpha=0.8)

    valid_sev = [(d, s) for d, s in zip(series.dates, series.severities) if s is not None]
    if valid_sev:
        vx, vy = zip(*valid_sev)
        ax_sev.plot(vx, vy, color="#0284c7", linewidth=2, marker="o", markersize=5, label="Severity (1–10)")

    if series.flagged_points:
        fx, fy, _ = zip(*series.flagged_points)
        ax_sev.scatter(fx, fy, color="#dc2626", s=65, zorder=5, label="Questionnaire Mismatch")

    ax_sev.set_ylabel("Severity", fontsize=9, fontweight="bold", color="#334155")
    ax_sev.set_ylim(0, 10.5)
    ax_sev.set_yticks([0, 2, 4, 6, 8, 10])
    ax_sev.tick_params(labelsize=8)
    ax_sev.grid(True, linestyle="--", alpha=0.35)
    ax_sev.legend(loc="upper left", frameon=False, fontsize=8, ncol=2)
    ax_sev.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))  # type: ignore[no-untyped-call]
    ax_sev.xaxis.set_major_locator(mdates.DayLocator(interval=3))  # type: ignore[no-untyped-call]

    # Panel 2: Weight Tracking & Medication Starts
    valid_weights = [(d, w) for d, w in zip(series.dates, series.weights) if w is not None]
    if valid_weights:
        wx, wy = zip(*valid_weights)
        ax_weight.plot(wx, wy, color="#475569", linewidth=1.8, marker="s", markersize=4, label="Weight (lbs)")
        ax_weight.set_ylabel("Weight (lbs)", fontsize=9, fontweight="bold", color="#334155")
        w_min, w_max = min(wy), max(wy)
        ax_weight.set_ylim(w_min - 2, w_max + 2)
    else:
        ax_weight.text(0.5, 0.5, "No weight recorded", ha="center", va="center", transform=ax_weight.transAxes, color="#94a3b8", fontsize=8)
        ax_weight.set_ylabel("Weight", fontsize=9, color="#334155")

    seen_meds: set[str] = set()
    for m_date, m_list in series.meds_by_date:
        new_meds = [m for m in m_list if m not in seen_meds]
        if new_meds:
            ax_weight.axvline(m_date, color="#7c3aed", linestyle=":", linewidth=1.2, alpha=0.75)
            ax_weight.annotate(
                f"+ {', '.join(new_meds)}",
                xy=(m_date, ax_weight.get_ylim()[0] if valid_weights else 0.1),
                xytext=(3, 4),
                textcoords="offset points",
                rotation=90,
                fontsize=7.5,
                color="#5b21b6",
            )
            seen_meds.update(new_meds)

    ax_weight.tick_params(labelsize=8)
    ax_weight.grid(True, linestyle="--", alpha=0.35)
    ax_weight.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))  # type: ignore[no-untyped-call]
    ax_weight.xaxis.set_major_locator(mdates.DayLocator(interval=3))  # type: ignore[no-untyped-call]
    fig.autofmt_xdate(rotation=25, ha="right")
    fig.tight_layout()

    fig.savefig(target, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return target
