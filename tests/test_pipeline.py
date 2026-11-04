"""End-to-End Test Suite for Kratos Pipeline, Schema Pruning & Engines."""

from pathlib import Path
import pytest
from kratos.engines.registry import EngineRegistry
from kratos.inference.schema_pruner import SchemaPruner
from kratos.semantics.unit_utils import infer_column_unit, format_metric_value
from kratos.contracts.schemas import DataTask, Intent, AnalyticalPattern, TimeGranularity, MetricTarget
from kratos.agents.orchestrator import InterpreterAgent, InvestigatorAgent
from kratos.semantics.bi_engine import compile_echarts


@pytest.fixture
def registry():
    base_dir = Path(__file__).resolve().parent.parent
    return EngineRegistry(base_dir / "data")


def test_schema_pruning(registry):
    pruner = SchemaPruner()
    engine = registry.engines["northwind"]
    full_schema = engine.introspect()

    pruned, rules = pruner.prune("ventas por empleado y ordenes", "northwind", full_schema, max_tables=3)
    assert len(pruned) <= 3
    assert any("order" in t.lower() or "employee" in t.lower() for t in pruned.keys())
    assert len(rules) > 0


def test_unit_inference():
    assert infer_column_unit("Total_Sales") == "$ USD"
    assert infer_column_unit("unitPrice") == "$ USD"
    assert infer_column_unit("discount_rate") == "%"
    assert infer_column_unit("dias_entrega") == "días"
    assert infer_column_unit("total_pedidos") == "pedidos"
    assert infer_column_unit("unitsInStock") == "unidades"


def test_metric_formatting():
    assert format_metric_value(1250000, "$ USD") == "$1.25M"
    assert format_metric_value(4500, "$ USD") == "$4.50K"
    assert format_metric_value(0.15, "%") == "15.0%"
    assert format_metric_value(12.4, "días") == "12.4 días"
    assert format_metric_value(532, "pedidos") == "532 pedidos"


def test_end_to_end_northwind_execution(registry):
    inv = InvestigatorAgent(registry)
    task = DataTask(intent=Intent.QUERY_DATA, engine_id="northwind", goal="Ventas por empleado")
    evidence = inv.execute_task(task)

    assert evidence.confidence > 0.8
    assert len(evidence.queries) == 1
    assert evidence.queries[0].row_count > 0
    assert "Peacock" in str(evidence.queries[0].rows)


def test_end_to_end_chinook_execution(registry):
    inv = InvestigatorAgent(registry)
    task = DataTask(intent=Intent.QUERY_DATA, engine_id="chinook", goal="Canciones por artista")
    evidence = inv.execute_task(task)

    assert evidence.confidence > 0.8
    assert len(evidence.queries) == 1
    assert "Iron Maiden" in str(evidence.queries[0].rows)


def test_end_to_end_sakila_execution(registry):
    inv = InvestigatorAgent(registry)
    task = DataTask(intent=Intent.QUERY_DATA, engine_id="sakila", goal="Top actores con mas peliculas")
    evidence = inv.execute_task(task)

    assert evidence.confidence > 0.8
    assert len(evidence.queries) == 1
    assert "SUSAN DAVIS" in str(evidence.queries[0].rows)


def test_documentation_page_endpoint():
    from fastapi.testclient import TestClient
    from kratos.api.main import app

    client = TestClient(app)
    response = client.get("/documentation")
    assert response.status_code == 200
    assert "KRATOS // Arquitectura y Documentación" in response.text
    assert "mermaid" in response.text
    assert "Restaurante de Alta Cocina" in response.text

    # Also test index page has documentation link
    index_res = client.get("/")
    assert index_res.status_code == 200
    assert 'href="/documentation"' in index_res.text


def test_interpreter_weekly_sales_trend():
    interpreter = InterpreterAgent()
    interpreted = interpreter.interpret("dame una tendencia de ventas semanal a través del tiempo", "northwind")

    assert interpreted.analytical_pattern == AnalyticalPattern.TIME_SERIES
    assert interpreted.time_granularity == TimeGranularity.WEEKLY
    assert interpreted.metric_target == MetricTarget.REVENUE
    assert "Semana" in interpreted.dimensions
    assert "Ventas_USD" in interpreted.metrics


def test_end_to_end_weekly_sales_trend(registry):
    interpreter = InterpreterAgent()
    investigator = InvestigatorAgent(registry)

    interpreted = interpreter.interpret("dame una tendencia de ventas semanal a través del tiempo", "northwind")
    task = DataTask(
        intent=interpreted.intent,
        engine_id="northwind",
        goal=interpreted.goal,
        analytical_pattern=interpreted.analytical_pattern,
        time_granularity=interpreted.time_granularity,
        metric_target=interpreted.metric_target,
        dimensions=interpreted.dimensions,
        metrics=interpreted.metrics,
    )
    evidence = investigator.execute_task(task)

    assert evidence.confidence > 0.8
    assert len(evidence.queries) == 1
    q = evidence.queries[0]
    assert "Semana" in q.columns
    assert "Ventas_USD" in q.columns
    assert "strftime" in q.sql.lower()
    assert len(q.rows) > 0
    assert "1996-W" in str(q.rows[0]["Semana"])

    # Verify chart is line
    echarts = compile_echarts(q.rows, title=task.goal)
    assert echarts is not None
    assert echarts["series"][0]["type"] == "line"


def test_interpreter_multi_series_daily_sales():
    interpreter = InterpreterAgent()
    query = "dame una tendencia de ventas diaria a través del tiempo por categoría"
    interpreted = interpreter.interpret(query, "northwind")

    assert interpreted.analytical_pattern == AnalyticalPattern.MULTI_SERIES_TIME_SERIES
    assert interpreted.time_granularity == TimeGranularity.DAILY
    assert interpreted.time_dimension == "Fecha"
    assert interpreted.series_dimension == "Categoria"
    assert "Fecha" in interpreted.dimensions
    assert "Categoria" in interpreted.dimensions


def test_end_to_end_multi_series_daily_sales(registry):
    interpreter = InterpreterAgent()
    investigator = InvestigatorAgent(registry)

    query = "dame una tendencia de ventas diaria a través del tiempo por categoría"
    interpreted = interpreter.interpret(query, "northwind")
    task = DataTask(
        intent=interpreted.intent,
        engine_id="northwind",
        goal=interpreted.goal,
        analytical_pattern=interpreted.analytical_pattern,
        time_granularity=interpreted.time_granularity,
        time_dimension=interpreted.time_dimension,
        series_dimension=interpreted.series_dimension,
        metric_target=interpreted.metric_target,
        dimensions=interpreted.dimensions,
        metrics=interpreted.metrics,
    )
    evidence = investigator.execute_task(task)

    assert evidence.confidence > 0.8
    assert len(evidence.queries) == 1
    q = evidence.queries[0]
    assert "Fecha" in q.columns
    assert "Categoria" in q.columns
    assert "Ventas_USD" in q.columns
    assert len(q.rows) > 0

    # Multi-series ECharts validation: multiple lines for categories
    echarts = compile_echarts(q.rows, title=task.goal)
    assert echarts is not None
    assert len(echarts["series"]) > 1
    assert all(s["type"] == "line" for s in echarts["series"])
    assert "legend" in echarts
    assert len(echarts["legend"]["data"]) > 1


def test_interpreter_and_cte_multi_series_top_3(registry):
    interpreter = InterpreterAgent()
    investigator = InvestigatorAgent(registry)

    query = "dame una tendencia de ventas diaria a través del tiempo por categoría de las 3 categorías con mejor desempeño"
    interpreted = interpreter.interpret(query, "northwind")

    assert interpreted.analytical_pattern == AnalyticalPattern.MULTI_SERIES_TIME_SERIES
    assert interpreted.time_granularity == TimeGranularity.DAILY
    assert interpreted.top_n == 3
    assert interpreted.ranking_criterion == "mejor desempeño"

    task = DataTask(
        intent=interpreted.intent,
        engine_id="northwind",
        goal=interpreted.goal,
        analytical_pattern=interpreted.analytical_pattern,
        time_granularity=interpreted.time_granularity,
        time_dimension=interpreted.time_dimension,
        series_dimension=interpreted.series_dimension,
        metric_target=interpreted.metric_target,
        top_n=interpreted.top_n,
        ranking_criterion=interpreted.ranking_criterion,
        dimensions=interpreted.dimensions,
        metrics=interpreted.metrics,
    )
    evidence = investigator.execute_task(task)
    assert evidence.confidence > 0.8
    assert len(evidence.queries) == 1
    q = evidence.queries[0]
    assert "with top_categories as" in q.sql.lower()

    # Verify exactly 3 distinct categories are returned in the rows
    distinct_cats = set(r["Categoria"] for r in q.rows)
    assert len(distinct_cats) == 3
    assert distinct_cats == {"Beverages", "Dairy Products", "Confections"}

    storytelling = interpreter.formulate_storytelling(task, evidence)
    assert "Top 3" in storytelling.key_takeaway
    assert "Dairy Products" in storytelling.key_takeaway


def test_interpreter_and_investigator_top_3_products(registry):
    interpreter = InterpreterAgent()
    investigator = InvestigatorAgent(registry)

    query = "cuales son los 3 productos con mejor desempeño en todo el set de datos?"
    interpreted = interpreter.interpret(query, "northwind")

    assert interpreted.analytical_pattern == AnalyticalPattern.RANKING_TOP_N
    assert interpreted.top_n == 3
    assert interpreted.ranking_criterion == "mejor desempeño"
    assert "Producto" in interpreted.dimensions

    task = DataTask(
        intent=interpreted.intent,
        engine_id="northwind",
        goal=interpreted.goal,
        analytical_pattern=interpreted.analytical_pattern,
        time_granularity=interpreted.time_granularity,
        metric_target=interpreted.metric_target,
        top_n=interpreted.top_n,
        ranking_criterion=interpreted.ranking_criterion,
        dimensions=interpreted.dimensions,
        metrics=interpreted.metrics,
    )
    evidence = investigator.execute_task(task)
    assert evidence.confidence > 0.8
    assert len(evidence.queries) == 1
    q = evidence.queries[0]
    assert "limit 3" in q.sql.lower()
    assert len(q.rows) == 3
    assert q.rows[0]["Producto"] == "Côte de Blaye"

    storytelling = interpreter.formulate_storytelling(task, evidence)
    assert "Top 3" in storytelling.key_takeaway
    assert "Producto" in storytelling.key_takeaway
    assert len(storytelling.quantitative_findings) >= 3
    assert len(storytelling.risk_alerts) >= 1
    assert "top_1_share_pct" in storytelling.diagnostic_metrics


def test_interpreter_and_cte_multi_series_bottom_3_products(registry):
    """Tests multi-series time series with bottom 3 products cohort."""
    interpreter = InterpreterAgent()
    investigator = InvestigatorAgent(registry)

    query = "quiero que encuentres los 3 productos con peor desempeño en general y que me muestres la tendencia diaria de esos productos a través del tiempo"
    interpreted = interpreter.interpret(query, "northwind")

    assert interpreted.analytical_pattern == AnalyticalPattern.MULTI_SERIES_TIME_SERIES
    assert interpreted.time_granularity == TimeGranularity.DAILY
    assert interpreted.top_n == 3
    assert interpreted.ranking_criterion == "menor desempeño"
    assert interpreted.series_dimension == "Producto"

    task = DataTask(
        intent=interpreted.intent,
        engine_id="northwind",
        goal=interpreted.goal,
        analytical_pattern=interpreted.analytical_pattern,
        time_granularity=interpreted.time_granularity,
        time_dimension=interpreted.time_dimension,
        series_dimension=interpreted.series_dimension,
        metric_target=interpreted.metric_target,
        top_n=interpreted.top_n,
        ranking_criterion=interpreted.ranking_criterion,
        dimensions=interpreted.dimensions,
        metrics=interpreted.metrics,
    )
    evidence = investigator.execute_task(task)
    assert evidence.confidence > 0.8
    assert len(evidence.queries) == 1
    q = evidence.queries[0]
    assert "with bottom_products as" in q.sql.lower()

    # Verify exactly 3 distinct products in rows
    distinct_prods = set(r["Producto"] for r in q.rows)
    assert len(distinct_prods) == 3
    assert distinct_prods == {"Geitost", "Genen Shouyu", "Chocolade"}

    storytelling = interpreter.formulate_storytelling(task, evidence)
    assert "Bottom 3" in storytelling.key_takeaway
    assert "Producto" in storytelling.key_takeaway


def test_geo_map_echarts_compilation():
    sample_rows = [
        {"Pais": "USA", "Ventas_USD": 245584.61},
        {"Pais": "Germany", "Ventas_USD": 230284.63},
        {"Pais": "Brasil", "Ventas_USD": 106925.78},
        {"Pais": "Reino Unido", "Ventas_USD": 58971.31},
    ]
    vis = compile_echarts(sample_rows, title="Ventas Globales")
    assert vis is not None
    assert vis["geo"]["map"] == "world"
    assert vis["series"][0]["type"] == "map"
    assert vis["_meta"]["is_geo"] is True
    assert vis["_meta"]["chart_type"] == "map"
    assert vis["_meta"]["unit"] == "$ USD"
    # Ensure name normalization mapped 'Brasil' to 'Brazil' and 'Reino Unido' to 'United Kingdom'
    names = [item["name"] for item in vis["series"][0]["data"]]
    assert "United States" in names
    assert "Brazil" in names
    assert "United Kingdom" in names







