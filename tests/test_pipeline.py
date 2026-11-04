"""End-to-End Test Suite for Kratos Pipeline, Schema Pruning & Engines."""

from pathlib import Path
import pytest
from kratos.engines.registry import EngineRegistry
from kratos.inference.schema_pruner import SchemaPruner
from kratos.semantics.unit_utils import infer_column_unit, format_metric_value
from kratos.contracts.schemas import DataTask, Intent
from kratos.agents.orchestrator import InterpreterAgent, InvestigatorAgent


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

