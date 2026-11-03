"""Kratos Heuristic BI Engine & ECharts 5 Generator."""

from typing import Any, List, Dict
from kratos.semantics.unit_utils import infer_column_unit, format_metric_value


def compile_echarts(rows: List[Dict[str, Any]], title: str = "Analytical Overview") -> Dict[str, Any] | None:
    """Produces valid, production-grade ECharts 5 options with strict unit compliance."""
    if not rows:
        return None

    columns = list(rows[0].keys())
    if len(columns) < 2:
        return None

    # Detect dimension (categorical/temporal) vs measure (numeric)
    dim_col = columns[0]
    metric_cols = columns[1:]

    categories = [str(r.get(dim_col, "")) for r in rows]
    series = []

    for m_col in metric_cols:
        unit = infer_column_unit(m_col)
        values = []
        for r in rows:
            v = r.get(m_col, 0)
            try:
                values.append(float(v) if v is not None else 0.0)
            except (ValueError, TypeError):
                values.append(0.0)

        # Decide chart type
        chart_type = "line" if any(w in dim_col.lower() for w in ["date", "fecha", "mes", "month", "year", "ano", "day"]) else "bar"
        if len(rows) <= 6 and len(metric_cols) == 1:
            chart_type = "pie"

        if chart_type == "pie":
            pie_data = [{"name": cat, "value": val} for cat, val in zip(categories, values)]
            return {
                "title": {"text": title, "left": "center", "textStyle": {"color": "#E2E8F0"}},
                "tooltip": {"trigger": "item"},
                "legend": {"orient": "vertical", "left": "left", "textStyle": {"color": "#94A3B8"}},
                "series": [
                    {
                        "name": m_col,
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "avoidLabelOverlap": False,
                        "itemStyle": {"borderRadius": 8, "borderColor": "#0F172A", "borderWidth": 2},
                        "data": pie_data,
                    }
                ],
            }

        series.append({
            "name": m_col,
            "type": chart_type,
            "data": values,
            "itemStyle": {"borderRadius": [4, 4, 0, 0]} if chart_type == "bar" else {},
        })

    primary_unit = infer_column_unit(metric_cols[0])

    return {
        "title": {"text": title, "textStyle": {"color": "#E2E8F0"}},
        "tooltip": {"trigger": "axis"},
        "legend": {"textStyle": {"color": "#94A3B8"}, "top": 25},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {"color": "#94A3B8", "rotate": 30 if len(categories) > 8 else 0},
        },
        "yAxis": {
            "type": "value",
            "name": primary_unit if primary_unit else None,
            "axisLabel": {"color": "#94A3B8"},
            "splitLine": {"lineStyle": {"color": "#334155"}},
        },
        "series": series,
    }
