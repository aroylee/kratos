"""Tests for Wren AI-Style MDL Semantic Catalog and Compiler across all 5 databases."""

import pytest
from pathlib import Path
from kratos.semantics.mdl import SemanticCatalog, SemanticModelMDL
from kratos.semantics.compiler import SemanticCompiler
from kratos.contracts.schemas import DataTask, Intent, AnalyticalPattern, TimeGranularity
from kratos.security.sql_guard import validate_sql
from kratos.engines.registry import EngineRegistry


@pytest.fixture
def catalog():
    return SemanticCatalog()


@pytest.fixture
def registry():
    reg = EngineRegistry(Path("data"))
    reg.discover()
    return reg


def test_catalog_discovers_all_five_databases(catalog):
    engines = catalog.available_engines
    assert "northwind" in engines
    assert "chinook" in engines
    assert "sakila" in engines
    assert "adventureworks_dw" in engines
    assert "tpch" in engines


@pytest.mark.parametrize("engine_id,dim_name,metric_name,expected_col", [
    ("northwind", "Producto", "Ventas_USD", "Producto"),
    ("chinook", "Genero", "Facturacion_USD", "Genero"),
    ("sakila", "Actor", "Peliculas", "Actor"),
    ("adventureworks_dw", "Categoria", "Ventas_USD", "Categoria"),
    ("tpch", "Pais", "Monto_USD", "Pais"),
])
def test_wren_mdl_compile_and_execute_all_databases(catalog, registry, engine_id, dim_name, metric_name, expected_col):
    model = catalog.get_model(engine_id)
    assert model is not None

    task = DataTask(
        intent=Intent.QUERY_DATA,
        engine_id=engine_id,
        goal=f"top 3 {dim_name} con mejor desempeño",
        analytical_pattern=AnalyticalPattern.RANKING_TOP_N,
        dimensions=[dim_name],
        metrics=[metric_name],
        top_n=3,
        ranking_criterion="mejor desempeño",
    )

    sql = SemanticCompiler.compile(task, model)
    assert sql is not None
    assert "limit 3" in sql.lower()

    # Validate against AST Guard
    allowed_tables = set(registry.engines[engine_id].introspect().keys())
    guard_res = validate_sql(sql, allowed_tables=allowed_tables, dialect="sqlite")
    assert guard_res.allowed, f"Guard rejected for {engine_id}: {guard_res.reason} {guard_res.detail}"

    # Execute against read-only engine
    engine = registry.engines[engine_id]
    cols, rows, _, _ = engine.execute_readonly(guard_res.sanitized_sql)
    assert len(rows) <= 3
    assert len(rows) > 0
    assert expected_col in cols
    assert metric_name in cols


def test_wren_mdl_time_series_compilation(catalog, registry):
    model = catalog.get_model("northwind")
    task = DataTask(
        intent=Intent.QUERY_DATA,
        engine_id="northwind",
        goal="tendencia de ventas mensual",
        analytical_pattern=AnalyticalPattern.TIME_SERIES,
        time_granularity=TimeGranularity.MONTHLY,
        time_dimension="Mes",
        metrics=["Ventas_USD"],
    )

    sql = SemanticCompiler.compile(task, model)
    assert "strftime('%Y-%m'" in sql
    assert "limit 30" in sql.lower()

    allowed_tables = set(registry.engines["northwind"].introspect().keys())
    guard_res = validate_sql(sql, allowed_tables=allowed_tables, dialect="sqlite")
    assert guard_res.allowed

    cols, rows, _, _ = registry.engines["northwind"].execute_readonly(guard_res.sanitized_sql)
    assert "Mes" in cols
    assert "Ventas_USD" in cols
    assert len(rows) > 0


def test_wren_mdl_ratio_metric_multi_table(catalog, registry):
    """Tests compiled execution of a derived ratio metric requiring multiple tables."""
    model = catalog.get_model("northwind")
    task = DataTask(
        intent=Intent.QUERY_DATA,
        engine_id="northwind",
        goal="ticket promedio por categoría",
        analytical_pattern=AnalyticalPattern.CATEGORICAL_BREAKDOWN,
        dimensions=["Categoria"],
        metrics=["Ticket_Promedio_USD"],
        top_n=5,
        ranking_criterion="mejor desempeño",
    )

    sql = SemanticCompiler.compile(task, model)
    assert "Ticket_Promedio_USD" in sql
    # Must join order_details, orders, and categories
    assert "order_details" in sql
    assert "orders" in sql
    assert "categories" in sql

    allowed_tables = set(registry.engines["northwind"].introspect().keys())
    guard_res = validate_sql(sql, allowed_tables=allowed_tables, dialect="sqlite")
    assert guard_res.allowed

    cols, rows, _, _ = registry.engines["northwind"].execute_readonly(guard_res.sanitized_sql)
    assert "Categoria" in cols
    assert "Ticket_Promedio_USD" in cols
    assert len(rows) > 0
    # Values should be realistic positive numbers
    assert float(rows[0]["Ticket_Promedio_USD"]) > 0


def test_wren_mdl_quarterly_time_series(catalog, registry):
    """Tests quarterly time grain compilation and execution."""
    model = catalog.get_model("northwind")
    task = DataTask(
        intent=Intent.QUERY_DATA,
        engine_id="northwind",
        goal="tendencia de ventas trimestral",
        analytical_pattern=AnalyticalPattern.TIME_SERIES,
        time_granularity=TimeGranularity.QUARTERLY,
        time_dimension="Trimestre",
        metrics=["Ventas_USD"],
    )

    sql = SemanticCompiler.compile(task, model)
    assert "-Q" in sql

    allowed_tables = set(registry.engines["northwind"].introspect().keys())
    guard_res = validate_sql(sql, allowed_tables=allowed_tables, dialect="sqlite")
    assert guard_res.allowed

    cols, rows, _, _ = registry.engines["northwind"].execute_readonly(guard_res.sanitized_sql)
    assert "Trimestre" in cols
    assert "Ventas_USD" in cols
    assert len(rows) > 0
    # First row should have format YYYY-Q#
    assert "-Q" in str(rows[0]["Trimestre"])


def test_wren_mdl_entity_and_measure_metadata(catalog):
    """Tests discovery of entities, primary keys, and atomic measures."""
    for engine_id in ["northwind", "chinook", "sakila", "adventureworks_dw", "tpch"]:
        model = catalog.get_model(engine_id)
        assert model is not None
        assert len(model.entities) >= 4, f"Model {engine_id} missing entities"
        for entity in model.entities:
            assert len(entity.primary_key) >= 1, f"Entity {entity.name} in {engine_id} missing PK"
            assert entity.grain != "", f"Entity {entity.name} in {engine_id} missing grain"
        assert len(model.metrics) >= 4, f"Model {engine_id} missing metrics"
