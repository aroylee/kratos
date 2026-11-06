"""Unit & Integration Tests for Kratos Auto-Ontology Substrate."""

from pathlib import Path
import pytest
from kratos.engines.registry import EngineRegistry, DatabaseEngine
from kratos.ontology.auto_ontology import AutoOntologyService, AutoOntologyExtractor
from kratos.ontology.grounder import AutoOntologyGrounder
from kratos.agents.orchestrator import InterpreterAgent, InvestigatorAgent
from kratos.contracts.schemas import DataTask


@pytest.fixture
def data_dir():
    return Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def registry(data_dir):
    return EngineRegistry(data_dir)


def test_auto_ontology_extraction_chinook(data_dir):
    """Verifies automated schema introspection and relationship extraction on Chinook."""
    engine = DatabaseEngine("chinook", data_dir / "chinook.db")
    model = AutoOntologyService.generate_for_engine(engine)

    assert model.engine_id == "chinook"
    assert len(model.entities) == 11
    assert any(e.name == "Invoice" for e in model.entities)
    assert any(e.name == "Track" for e in model.entities)
    assert any(e.name == "Genre" for e in model.entities)

    # Check discovered relationships (foreign keys)
    assert len(model.relationships) >= 10
    assert any("InvoiceId" in r.on_clause for r in model.relationships)
    assert any("TrackId" in r.on_clause for r in model.relationships)

    # Check semantic dimension classifications
    geo_dims = [d for d in model.dimensions if d.type == "geo"]
    assert len(geo_dims) > 0
    assert any("Pais" in d.id or "Country" in d.column for d in geo_dims)

    temporal_dims = [d for d in model.dimensions if d.type == "temporal"]
    assert len(temporal_dims) > 0
    assert any("Fecha" in d.id or "Date" in d.column for d in temporal_dims)

    # Check metric synthesis
    assert len(model.metrics) > 0
    assert any("USD" in m.unit or "registros" in m.unit for m in model.metrics)


def test_auto_ontology_answerability_check(data_dir):
    """Verifies epistemological validation against certified ontology."""
    engine = DatabaseEngine("chinook", data_dir / "chinook.db")
    model = AutoOntologyService.generate_for_engine(engine)

    # 1. Answerable query
    valid_res = AutoOntologyGrounder.check_answerable(
        "cuáles son los géneros que se venden más por país", model
    )
    assert valid_res.is_answerable is True
    assert valid_res.confidence >= 0.80
    assert len(valid_res.missing_concepts) == 0

    # 2. Out-of-scope query requesting missing business concepts (e.g. profit margins, employee salaries)
    invalid_res = AutoOntologyGrounder.check_answerable(
        "cuál es el margen de beneficio y los salarios de los empleados", model
    )
    assert invalid_res.is_answerable is False
    assert invalid_res.confidence <= 0.30
    assert "Margen" in invalid_res.missing_concepts
    assert "Salario" in invalid_res.missing_concepts
    assert "no contiene datos ni métricas para" in invalid_res.reason


def test_auto_ontology_orchestrator_guard(registry):
    """Ensures Kratos never executes hallucinated SQL when a query is out-of-scope."""
    interpreter = InterpreterAgent()
    interpreted = interpreter.interpret("dame los costos y salarios por empleado", "chinook")

    assert interpreted.needs_investigation is False
    assert len(interpreted.constraints) > 0
    assert any("OUT_OF_SCOPE:" in c for c in interpreted.constraints)

    task = DataTask(
        intent=interpreted.intent,
        engine_id="chinook",
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
        constraints=interpreted.constraints,
        required_evidence=interpreted.required_evidence,
    )

    inv = InvestigatorAgent(registry)
    evidence = inv.execute_task(task)

    # Zero SQL queries should be executed
    assert len(evidence.queries) == 0
    assert len(evidence.warnings) > 0
    assert "no contiene datos ni métricas" in evidence.warnings[0]

    # Executive storytelling should inform the user clearly
    storytelling = interpreter.formulate_storytelling(task, evidence)
    assert "fuera del alcance ontológico" in storytelling.key_takeaway
    assert any("Costo" in f or "Salario" in f for f in storytelling.quantitative_findings)
    assert len(storytelling.strategic_recommendations) > 0


def test_auto_ontology_export_yaml(data_dir, tmp_path):
    """Verifies that an auto-extracted ontology can be cleanly exported to Wren MDL YAML."""
    engine = DatabaseEngine("northwind", data_dir / "northwind.db")
    model = AutoOntologyService.generate_for_engine(engine)

    dest_file = tmp_path / "northwind_auto.yaml"
    yaml_content = AutoOntologyService.export_to_yaml(model, dest_file)

    assert dest_file.exists()
    assert "engine_id: northwind" in yaml_content
    assert "entities:" in yaml_content
    assert "dimensions:" in yaml_content
    assert "metrics:" in yaml_content
    assert "relationships:" in yaml_content


def test_data_engineering_agent_ingestion_and_grounded_erd(data_dir, tmp_path):
    """Verifies autonomous DataEngineeringAgent database ingestion, schema profiling, and grounded ERD."""
    from kratos.agents.data_engineer import DataEngineeringAgent

    agent = DataEngineeringAgent(models_dir=tmp_path)
    report = agent.ingest_database(data_dir / "northwind.db")

    assert report.engine_id == "northwind"
    assert report.tables_count == 11
    assert report.columns_count == 84
    assert report.relationships_count >= 10
    assert "Region" in report.dimensions
    assert "Pais" in report.dimensions
    assert "Ciudad" in report.dimensions

    # Verify that the generated ERD is 100% grounded and includes region in customers!
    erd = report.grounded_erd
    assert "erDiagram" in erd
    assert "CUSTOMERS" in erd
    assert "string region" in erd.lower() or "region" in erd
    assert "ORDERS" in erd
    assert "shipregion" in erd.lower() or "shipregion" in erd

