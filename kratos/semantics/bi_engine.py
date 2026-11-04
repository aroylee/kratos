"""Kratos Heuristic BI Engine & ECharts 5 Multi-Series Generator."""

from typing import Any, List, Dict
from kratos.semantics.unit_utils import infer_column_unit, format_metric_value


def _compile_multi_series_echarts(
    rows: List[Dict[str, Any]],
    time_col: str,
    cat_col: str,
    metric_col: str,
    title: str
) -> Dict[str, Any]:
    """Pivots flat tabular rows (time, category, metric) into an ECharts 5 Multi-Line chart."""
    time_points = sorted(list(dict.fromkeys(str(r.get(time_col, "")) for r in rows if r.get(time_col))))
    
    # Calculate totals per category to rank and show top categories
    cat_totals: Dict[str, float] = {}
    for r in rows:
        cat = str(r.get(cat_col, "Otro"))
        try:
            val = float(r.get(metric_col, 0) or 0)
        except (ValueError, TypeError):
            val = 0.0
        cat_totals[cat] = cat_totals.get(cat, 0.0) + val

    top_cats = sorted(cat_totals.keys(), key=lambda k: cat_totals[k], reverse=True)[:8]

    # Map fast lookup
    lookup: Dict[tuple, float] = {}
    for r in rows:
        t = str(r.get(time_col, ""))
        c = str(r.get(cat_col, ""))
        try:
            v = float(r.get(metric_col, 0) or 0)
        except (ValueError, TypeError):
            v = 0.0
        lookup[(t, c)] = v

    palette = [
        "#6366F1", "#10B981", "#F59E0B", "#EC4899",
        "#3B82F6", "#8B5CF6", "#14B8A6", "#F97316"
    ]

    series = []
    for idx, cat in enumerate(top_cats):
        color = palette[idx % len(palette)]
        data_points = [round(lookup.get((t, cat), 0.0), 2) for t in time_points]
        series.append({
            "name": cat,
            "type": "line",
            "smooth": True,
            "showSymbol": len(time_points) <= 25,
            "itemStyle": {"color": color},
            "lineStyle": {"width": 2.5},
            "data": data_points,
        })

    primary_unit = infer_column_unit(metric_col)

    return {
        "title": {"text": title, "textStyle": {"color": "#E2E8F0"}},
        "tooltip": {"trigger": "axis"},
        "legend": {
            "data": top_cats,
            "textStyle": {"color": "#94A3B8"},
            "top": 25,
            "type": "scroll",
        },
        "grid": {"left": "3%", "right": "4%", "bottom": "5%", "top": "18%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": time_points,
            "axisLabel": {"color": "#94A3B8", "rotate": 30 if len(time_points) > 10 else 0},
        },
        "yAxis": {
            "type": "value",
            "name": primary_unit if primary_unit else None,
            "axisLabel": {"color": "#94A3B8"},
            "splitLine": {"lineStyle": {"color": "#334155"}},
        },
        "series": series,
    }


def compile_echarts(rows: List[Dict[str, Any]], title: str = "Analytical Overview") -> Dict[str, Any] | None:
    """Produces valid, production-grade ECharts 5 options with strict unit compliance."""
    if not rows:
        return None

    columns = list(rows[0].keys())
    if len(columns) < 2:
        return None

    # Detect Multi-Series Pivot Pattern: (time_col, category_col, metric_col)
    if len(columns) == 3:
        c0, c1, c2 = columns[0], columns[1], columns[2]
        is_c0_time = any(w in c0.lower() for w in [
            "date", "fecha", "mes", "month", "year", "ano", "day", "dia", "semana", "week"
        ])
        sample_val = rows[0].get(c2)
        try:
            float(sample_val) if sample_val is not None else 0.0
            is_c2_numeric = True
        except (ValueError, TypeError):
            is_c2_numeric = False

        if is_c0_time and is_c2_numeric:
            return _compile_multi_series_echarts(rows, c0, c1, c2, title)

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

        # Decide chart type: time-series always prefers line
        is_temporal = any(w in dim_col.lower() for w in [
            "date", "fecha", "mes", "month", "year", "ano", "day", "dia",
            "semana", "week", "periodo", "trimestre", "quarter"
        ])
        chart_type = "line" if is_temporal else "bar"
        if not is_temporal and len(rows) <= 6 and len(metric_cols) == 1:
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
            "smooth": True if chart_type == "line" else False,
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
