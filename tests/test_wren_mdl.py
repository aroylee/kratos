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
