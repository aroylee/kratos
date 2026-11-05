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

    top_cats = sorted(cat_totals.keys(), key=lambda k: cat_totals[k], reverse=True)[:10]

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
        "#3B82F6", "#8B5CF6", "#14B8A6", "#F97316",
        "#06B6D4", "#E11D48"
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
    has_zoom = len(time_points) > 12

    option: Dict[str, Any] = {
        "title": {"text": title, "textStyle": {"color": "#E2E8F0"}},
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": "#0F172A",
            "borderColor": "#334155",
            "textStyle": {"color": "#E2E8F0"}
        },
        "legend": {
            "data": top_cats,
            "textStyle": {"color": "#94A3B8"},
            "top": 25,
            "type": "scroll",
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "14%" if has_zoom else "5%",
            "top": "18%",
            "containLabel": True
        },
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

    if has_zoom:
        option["dataZoom"] = [
            {"type": "inside", "start": 0, "end": 100},
            {
                "type": "slider",
                "start": 0,
                "end": 100,
                "height": 22,
                "bottom": 6,
                "borderColor": "#334155",
                "fillerColor": "rgba(99, 102, 241, 0.15)",
                "handleStyle": {"color": "#6366F1"},
                "textStyle": {"color": "#94A3B8"}
            }
        ]

    return option


COUNTRY_NAME_MAPPINGS = {
    "usa": "United States",
    "united states": "United States",
    "estados unidos": "United States",
    "eeuu": "United States",
    "ee.uu.": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "reino unido": "United Kingdom",
    "gran bretaña": "United Kingdom",
    "germany": "Germany",
    "alemania": "Germany",
    "france": "France",
    "francia": "France",
    "brazil": "Brazil",
    "brasil": "Brazil",
    "canada": "Canada",
    "canadá": "Canada",
    "mexico": "Mexico",
    "méxico": "Mexico",
    "spain": "Spain",
    "españa": "Spain",
    "italy": "Italy",
    "italia": "Italy",
    "austria": "Austria",
    "belgium": "Belgium",
    "bélgica": "Belgium",
    "switzerland": "Switzerland",
    "suiza": "Switzerland",
    "sweden": "Sweden",
    "suecia": "Sweden",
    "norway": "Norway",
    "noruega": "Norway",
    "finland": "Finland",
    "finlandia": "Finland",
    "poland": "Poland",
    "polonia": "Poland",
    "portugal": "Portugal",
    "ireland": "Ireland",
    "irlanda": "Ireland",
    "denmark": "Denmark",
    "dinamarca": "Denmark",
    "argentina": "Argentina",
    "venezuela": "Venezuela",
    "australia": "Australia",
    "japan": "Japan",
    "japón": "Japan",
    "china": "China",
    "india": "India",
    "russia": "Russia",
    "rusia": "Russia",
    "chile": "Chile",
    "colombia": "Colombia",
    "peru": "Peru",
    "perú": "Peru",
    "czech republic": "Czech Rep.",
    "republica checa": "Czech Rep.",
    "república checa": "Czech Rep.",
    "netherlands": "Netherlands",
    "holanda": "Netherlands",
    "países bajos": "Netherlands",
    "paises bajos": "Netherlands",
    "south africa": "South Africa",
    "sudáfrica": "South Africa",
    "hungary": "Hungary",
    "hungría": "Hungary",
}


def normalize_country_name(name: str) -> str:
    cleaned = name.strip()
    return COUNTRY_NAME_MAPPINGS.get(cleaned.lower(), cleaned)


def _compile_geo_map_echarts(
    rows: List[Dict[str, Any]],
    dim_col: str,
    metric_col: str,
    title: str,
    category_col: str | None = None
) -> Dict[str, Any]:
    """Compiles an interactive choropleth World Map with visualMap heat gradient and optional category attribution."""
    geo_data = []
    numeric_vals = []
    categories = []
    categories_secondary = []

    for r in rows:
        raw_name = str(r.get(dim_col, ""))
        norm_name = normalize_country_name(raw_name)
        cat_val = str(r.get(category_col, "")) if category_col else None
        try:
            val = float(r.get(metric_col, 0) or 0)
        except (ValueError, TypeError):
            val = 0.0

        item = {
            "name": norm_name,
            "value": round(val, 2),
            "raw_name": raw_name,
        }
        if cat_val:
            item["category"] = cat_val
            categories_secondary.append(cat_val)

        geo_data.append(item)
        numeric_vals.append(val)
        categories.append(raw_name)

    min_val = min(numeric_vals) if numeric_vals else 0
    max_val = max(numeric_vals) if numeric_vals else 100
    primary_unit = infer_column_unit(metric_col)

    meta = {
        "chart_type": "map",
        "is_geo": True,
        "dim_col": dim_col,
        "metric_col": metric_col,
        "categories": categories,
        "values": numeric_vals,
        "unit": primary_unit
    }
    if category_col:
        meta["category_col"] = category_col
        meta["categories_secondary"] = categories_secondary

    return {
        "title": {"text": title, "textStyle": {"color": "#E2E8F0"}},
        "tooltip": {
            "trigger": "item",
            "backgroundColor": "#0F172A",
            "borderColor": "#334155",
            "textStyle": {"color": "#E2E8F0"},
            "formatter": f"{{b}}: {{c}} {primary_unit}".strip()
        },
        "visualMap": {
            "min": min_val,
            "max": max_val,
            "text": ["Alto", "Bajo"],
            "realtime": False,
            "calculable": True,
            "inRange": {
                "color": ["#1E293B", "#312E81", "#4F46E5", "#818CF8", "#F43F5E"]
            },
            "textStyle": {"color": "#94A3B8"},
            "left": 10,
            "bottom": 10
        },
        "geo": {
            "map": "world",
            "roam": True,
            "zoom": 1.15,
            "emphasis": {
                "label": {"show": True, "color": "#FFFFFF"},
                "itemStyle": {"areaColor": "#6366F1"}
            },
            "itemStyle": {
                "areaColor": "#1E293B",
                "borderColor": "#334155",
                "borderWidth": 0.8
            }
        },
        "series": [
            {
                "name": metric_col,
                "type": "map",
                "geoIndex": 0,
                "data": geo_data
            }
        ],
        "_meta": meta
    }


def compile_echarts(rows: List[Dict[str, Any]], title: str = "Analytical Overview") -> Dict[str, Any] | None:
    """Produces valid, production-grade ECharts 5 options with strict unit compliance."""
    if not rows:
        return None

    columns = list(rows[0].keys())
    if len(columns) < 2:
        return None

    # Detect 3-Column Patterns
    if len(columns) == 3:
        c0, c1, c2 = columns[0], columns[1], columns[2]
        sample_val = rows[0].get(c2)
        try:
            float(sample_val) if sample_val is not None else 0.0
            is_c2_numeric = True
        except (ValueError, TypeError):
            is_c2_numeric = False

        # 1. Geo-Partitioned Pattern: (geo_col, category_col, metric_col)
        is_c0_geo = any(w in c0.lower() for w in ["pais", "país", "country", "nation", "nacion", "nación", "region", "región"])
        is_c1_geo = any(w in c1.lower() for w in ["pais", "país", "country", "nation", "nacion", "nación", "region", "región"])
        if is_c0_geo and is_c2_numeric:
            return _compile_geo_map_echarts(rows, dim_col=c0, metric_col=c2, title=title, category_col=c1)
        elif is_c1_geo and is_c2_numeric:
            return _compile_geo_map_echarts(rows, dim_col=c1, metric_col=c2, title=title, category_col=c0)

        # 2. Multi-Series Pivot Pattern: (time_col, category_col, metric_col)
        is_c0_time = any(w in c0.lower() for w in [
            "date", "fecha", "mes", "month", "year", "ano", "day", "dia", "semana", "week"
        ])
        if is_c0_time and is_c2_numeric:
            return _compile_multi_series_echarts(rows, c0, c1, c2, title)

    # Detect dimension (categorical/temporal) vs measure (numeric)
    dim_col = columns[0]
    metric_cols = columns[1:]

    # Detect Geo Pattern: dim_col is Pais / Country / Nation / BillingCountry
    is_geo = any(w in dim_col.lower() for w in ["pais", "país", "country", "nation", "nacion", "nación"])
    if is_geo and len(metric_cols) >= 1:
        return _compile_geo_map_echarts(rows, dim_col, metric_cols[0], title)

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
    has_zoom = is_temporal and len(categories) > 12

    option: Dict[str, Any] = {
        "title": {"text": title, "textStyle": {"color": "#E2E8F0"}},
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": "#0F172A",
            "borderColor": "#334155",
            "textStyle": {"color": "#E2E8F0"}
        },
        "legend": {"textStyle": {"color": "#94A3B8"}, "top": 25},
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "14%" if has_zoom else "5%",
            "containLabel": True
        },
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

    if has_zoom:
        option["dataZoom"] = [
            {"type": "inside", "start": 0, "end": 100},
            {
                "type": "slider",
                "start": 0,
                "end": 100,
                "height": 22,
                "bottom": 6,
                "borderColor": "#334155",
                "fillerColor": "rgba(99, 102, 241, 0.15)",
                "handleStyle": {"color": "#6366F1"},
                "textStyle": {"color": "#94A3B8"}
            }
        ]

    return option
