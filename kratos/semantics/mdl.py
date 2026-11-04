"""Kratos Semantic Modeling Definition Language (MDL) - Inspired by Wren AI.

Declarative business semantics, metric definitions, and graph-based relationship paths.
"""

from collections import deque
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field


class EntityMDL(BaseModel):
    """Semantic entity representing a physical table, grain, and key constraints."""
    name: str
    primary_key: list[str] = Field(default_factory=list)
    description: str = ""
    grain: str = ""


class DimensionMDL(BaseModel):
    """Semantic dimension representing an analytical entity or attribute."""
    id: str
    table: str
    column: str | None = None
    expression: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    type: str = "categorical"  # categorical, temporal, geo
    allowed_grains: list[str] = Field(default_factory=lambda: ["day", "week", "month", "quarter", "year"])
    description: str = ""

    @property
    def select_expression(self) -> str:
        """Returns the SQL select expression for this dimension."""
        if self.expression:
            return self.expression
        if self.column:
            return f"{self.table}.{self.column}"
        return f"{self.table}.{self.id}"


class MeasureMDL(BaseModel):
    """Atomic column-level aggregation measure."""
    id: str
    table: str
    column: str | None = None
    agg_type: str = "sum"  # sum, count, count_distinct, avg, min, max
    expression: str
    unit: str = ""
    is_currency: bool = False
    synonyms: list[str] = Field(default_factory=list)
    description: str = ""


class MetricMDL(BaseModel):
    """Formally curated business metric calculation (atomic or derived/ratio)."""
    id: str
    table: str
    expression: str
    metric_type: str = "atomic"  # atomic, ratio, derived
    required_tables: list[str] = Field(default_factory=list)
    unit: str = ""
    is_currency: bool = False
    synonyms: list[str] = Field(default_factory=list)
    description: str = ""


class RelationshipMDL(BaseModel):
    """Pre-approved join relationship between two tables."""
    from_table: str
    to_table: str
    on_clause: str
    cardinality: str = "many_to_one"  # one_to_many, many_to_one, one_to_one


class SemanticModelMDL(BaseModel):
    """Complete semantic definition of a database engine."""
    engine_id: str
    name: str
    description: str
    entities: list[EntityMDL] = Field(default_factory=list)
    dimensions: list[DimensionMDL] = Field(default_factory=list)
    measures: list[MeasureMDL] = Field(default_factory=list)
    metrics: list[MetricMDL] = Field(default_factory=list)
    relationships: list[RelationshipMDL] = Field(default_factory=list)

    def get_entity(self, table_name: str) -> EntityMDL | None:
        t_lower = table_name.lower()
        for e in self.entities:
            if e.name.lower() == t_lower:
                return e
        return None

    def get_measure(self, measure_id: str) -> MeasureMDL | None:
        m_lower = measure_id.lower()
        for m in self.measures:
            if m.id.lower() == m_lower:
                return m
        return None

    def get_dimension(self, dim_id: str) -> DimensionMDL | None:
        dim_id_lower = dim_id.lower()
        for d in self.dimensions:
            if d.id.lower() == dim_id_lower:
                return d
        return None

    def get_metric(self, metric_id: str) -> MetricMDL | None:
        metric_id_lower = metric_id.lower()
        for m in self.metrics:
            if m.id.lower() == metric_id_lower:
                return m
        return None

    def find_dimension_by_synonym(self, text: str) -> DimensionMDL | None:
        """Finds a dimension whose ID or synonyms appear in text."""
        lowered = text.lower()
        for d in self.dimensions:
            if d.id.lower() in lowered:
                return d
            for syn in d.synonyms:
                if syn.lower() in lowered:
                    return d
        return None

    def find_metric_by_synonym(self, text: str) -> MetricMDL | None:
        """Finds a metric whose ID or synonyms appear in text."""
        lowered = text.lower()
        for m in self.metrics:
            if m.id.lower() in lowered:
                return m
            for syn in m.synonyms:
                if syn.lower() in lowered:
                    return m
        return None

    def resolve_join_tree(self, required_tables: set[str], primary_table: str | None = None) -> list[RelationshipMDL]:
        """Resolves the minimal spanning tree of relationships to connect all required tables."""
        if not required_tables or len(required_tables) <= 1:
            return []

        # Build adjacency graph
        adj: dict[str, list[RelationshipMDL]] = {}
        for r in self.relationships:
            adj.setdefault(r.from_table, []).append(r)
            # Add reverse edge
            reversed_rel = RelationshipMDL(
                from_table=r.to_table,
                to_table=r.from_table,
                on_clause=r.on_clause,
                cardinality="one_to_many" if r.cardinality == "many_to_one" else "many_to_one"
            )
            adj.setdefault(r.to_table, []).append(reversed_rel)

        # Choose start table
        start_table = primary_table if (primary_table and primary_table in required_tables) else next(iter(required_tables))

        visited: set[str] = {start_table}
        queue: deque[tuple[str, list[RelationshipMDL]]] = deque([(start_table, [])])
        connected_rels: list[RelationshipMDL] = []
        found_tables: set[str] = {start_table}

        # Multi-target BFS to find paths to all required tables
        while queue and found_tables != required_tables:
            current, path = queue.popleft()
            if current in required_tables and current != start_table:
                # Add this path to connected_rels
                for rel in path:
                    # check if rel already in connected_rels
                    if not any(
                        (cr.from_table == rel.from_table and cr.to_table == rel.to_table) or
                        (cr.from_table == rel.to_table and cr.to_table == rel.from_table)
                        for cr in connected_rels
                    ):
                        connected_rels.append(rel)
                found_tables.add(current)

            for rel in adj.get(current, []):
                neighbor = rel.to_table
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [rel]))

        return connected_rels


class SemanticCatalog:
    """Catalog discovering and managing all Wren MDL semantic models."""

    def __init__(self, models_dir: Path | None = None):
        self.models_dir = models_dir or Path(__file__).resolve().parent / "models"
        self._models: dict[str, SemanticModelMDL] = {}
        self.reload()

    def reload(self) -> None:
        """Discovers and reloads all YAML models from models_dir."""
        self._models.clear()
        if not self.models_dir.exists():
            return

        for yml_path in self.models_dir.glob("*.yaml"):
            try:
                with open(yml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "engine_id" in data:
                        model = SemanticModelMDL(**data)
                        self._models[model.engine_id] = model
            except Exception as exc:
                print(f"[WARN] Error loading semantic model from {yml_path.name}: {exc}")

    def get_model(self, engine_id: str) -> SemanticModelMDL | None:
        return self._models.get(engine_id)

    @property
    def available_engines(self) -> list[str]:
        return list(self._models.keys())
