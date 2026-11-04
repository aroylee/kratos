"""Kratos Advanced Diagnostic Analytics & Statistical Profiler.

Calculates executive diagnostic intelligence on query results:
  - Pareto Concentration & Volume Shares (CR1, CR3)
  - Dominance Gap Analysis (Top 1 vs Top 2 spread)
  - Sample Dispersion (Mean, Median, Standard Deviation)
  - Time-Series Velocity, Peaks, Volatility & Anomaly Outliers
"""

import math
from typing import Any
from pydantic import BaseModel, Field

from kratos.semantics.unit_utils import infer_column_unit, format_metric_value


class DistributionDiagnostics(BaseModel):
    """Statistical & business diagnostics for rankings and categorical breakdowns."""
    metric_col: str
    dimension_col: str
    sample_size: int
    total_volume: float
    unit: str
    top_1_label: str | None = None
    top_1_val: float | None = None
    top_1_share_pct: float | None = None
    top_2_label: str | None = None
    top_2_val: float | None = None
    dominance_gap_pct: float | None = None  # (Top1 - Top2) / Top2 * 100
    top_3_share_pct: float | None = None    # Cumulative share of top 3
    mean_val: float = 0.0
    median_val: float = 0.0
    is_concentrated: bool = False           # True if Top 1 > 40% or Top 3 > 70%


class TimeSeriesDiagnostics(BaseModel):
    """Temporal velocity, volatility, peaks, and anomaly diagnostics."""
    metric_col: str
    time_col: str
    period_count: int
    total_volume: float
    unit: str
    peak_date: str | None = None
    peak_val: float | None = None
    trough_date: str | None = None
    trough_val: float | None = None
    mean_val: float = 0.0
    std_dev: float = 0.0
    coefficient_of_variation: float = 0.0   # sigma / mu
    volatility_level: str = "Baja"          # Baja (<0.3), Moderada (0.3-0.7), Alta (>0.7)
    anomalies: list[dict[str, Any]] = Field(default_factory=list)  # Points with |z-score| > 2
    trend_direction: str = "Estable"        # Creciente, Decreciente, Estable


def analyze_distribution(rows: list[dict[str, Any]], dim_hint: str | None = None, met_hint: str | None = None) -> DistributionDiagnostics | None:
    """Analyzes a list of categorical / ranking rows and computes Pareto & gap diagnostics."""
    if not rows:
        return None

    # Identify metric column (numeric) and dimension column (text)
    metric_col = met_hint if (met_hint and met_hint in rows[0]) else None
    dimension_col = dim_hint if (dim_hint and dim_hint in rows[0]) else None

    if not metric_col or not dimension_col:
        for col, val in rows[0].items():
            try:
                float(val)
                if not metric_col:
                    metric_col = col
            except (ValueError, TypeError):
                if not dimension_col:
                    dimension_col = col

    if not metric_col:
        return None
    if not dimension_col:
        dimension_col = list(rows[0].keys())[0]

    # Extract numeric values
    items: list[tuple[str, float]] = []
    for r in rows:
        try:
            val = float(r.get(metric_col, 0) or 0)
            lbl = str(r.get(dimension_col, ""))
            items.append((lbl, val))
        except (ValueError, TypeError):
            continue

    if not items:
        return None

    # Sort descending by value
    items.sort(key=lambda x: x[1], reverse=True)
    vals = [x[1] for x in items]
    total_vol = sum(vals)
    n = len(vals)
    unit = infer_column_unit(metric_col)

    top_1_lbl, top_1_val = items[0]
    top_1_share = (top_1_val / total_vol * 100) if total_vol > 0 else 0.0

    top_2_lbl, top_2_val = (items[1] if n > 1 else (None, None))
    gap_pct = None
    if top_2_val is not None and top_2_val > 0:
        gap_pct = ((top_1_val - top_2_val) / top_2_val) * 100

    top_3_share = (sum(vals[:3]) / total_vol * 100) if total_vol > 0 else 0.0

    mean_val = total_vol / n if n > 0 else 0.0
    sorted_vals = sorted(vals)
    median_val = sorted_vals[n // 2] if n % 2 != 0 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

    is_concentrated = (top_1_share >= 40.0) or (n >= 3 and top_3_share >= 70.0)

    return DistributionDiagnostics(
        metric_col=metric_col,
        dimension_col=dimension_col,
        sample_size=n,
        total_volume=round(total_vol, 2),
        unit=unit,
        top_1_label=top_1_lbl,
        top_1_val=round(top_1_val, 2),
        top_1_share_pct=round(top_1_share, 1),
        top_2_label=top_2_lbl,
        top_2_val=round(top_2_val, 2) if top_2_val is not None else None,
        dominance_gap_pct=round(gap_pct, 1) if gap_pct is not None else None,
        top_3_share_pct=round(top_3_share, 1),
        mean_val=round(mean_val, 2),
        median_val=round(median_val, 2),
        is_concentrated=is_concentrated,
    )


def analyze_time_series(rows: list[dict[str, Any]], time_hint: str | None = None, met_hint: str | None = None) -> TimeSeriesDiagnostics | None:
    """Analyzes chronological rows and detects velocity, volatility, peaks, and statistical anomalies."""
    if not rows or len(rows) < 2:
        return None

    time_col = time_hint if (time_hint and time_hint in rows[0]) else None
    met_col = met_hint if (met_hint and met_hint in rows[0]) else None

    if not time_col or not met_col:
        for col, val in rows[0].items():
            try:
                float(val)
                if not met_col:
                    met_col = col
            except (ValueError, TypeError):
                if not time_col:
                    time_col = col

    if not met_col or not time_col:
        return None

    timeline: list[tuple[str, float]] = []
    for r in rows:
        try:
            val = float(r.get(met_col, 0) or 0)
            t_lbl = str(r.get(time_col, ""))
            timeline.append((t_lbl, val))
        except (ValueError, TypeError):
            continue

    if not timeline:
        return None

    # Preserve chronological order
    vals = [x[1] for x in timeline]
    n = len(vals)
    total_vol = sum(vals)
    unit = infer_column_unit(met_col)

    peak_lbl, peak_val = max(timeline, key=lambda x: x[1])
    trough_lbl, trough_val = min(timeline, key=lambda x: x[1])

    mean_val = total_vol / n if n > 0 else 0.0
    variance = sum((v - mean_val) ** 2 for v in vals) / n if n > 0 else 0.0
    std_dev = math.sqrt(variance)
    cv = (std_dev / mean_val) if mean_val > 0 else 0.0

    if cv > 0.7:
        volatility = "Alta"
    elif cv > 0.3:
        volatility = "Moderada"
    else:
        volatility = "Baja"

    # Detect outliers (|z-score| > 2)
    anomalies: list[dict[str, Any]] = []
    if std_dev > 0:
        for t_lbl, v in timeline:
            z = (v - mean_val) / std_dev
            if abs(z) >= 2.0:
                anomalies.append({
                    "date": t_lbl,
                    "value": round(v, 2),
                    "z_score": round(z, 2),
                    "type": "Pico inusual" if z > 0 else "Caída inusual"
                })

    # Trend direction (slope estimate: second half vs first half)
    half = n // 2
    first_half_avg = sum(vals[:half]) / half if half > 0 else 0.0
    second_half_avg = sum(vals[half:]) / (n - half) if (n - half) > 0 else 0.0
    diff_pct = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0.0

    if diff_pct >= 15.0:
        trend = "Creciente (+{:.1f}%)".format(diff_pct)
    elif diff_pct <= -15.0:
        trend = "Decreciente ({:.1f}%)".format(diff_pct)
    else:
        trend = "Estable ({:+.1f}%)".format(diff_pct)

    return TimeSeriesDiagnostics(
        metric_col=met_col,
        time_col=time_col,
        period_count=n,
        total_volume=round(total_vol, 2),
        unit=unit,
        peak_date=peak_lbl,
        peak_val=round(peak_val, 2),
        trough_date=trough_lbl,
        trough_val=round(trough_val, 2),
        mean_val=round(mean_val, 2),
        std_dev=round(std_dev, 2),
        coefficient_of_variation=round(cv, 2),
        volatility_level=volatility,
        anomalies=anomalies[:3],
        trend_direction=trend,
    )
