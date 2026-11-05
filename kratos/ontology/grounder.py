"""Kratos Auto-Ontology Semantic Grounder & Answerability Checker.

Inspired by NVIDIA Auto-Ontology's epistemological validation:
Verifies whether a user prompt can be answered by the certified ontology
before query execution, avoiding hallucinations and mapping terms to certified concepts.
"""

from __future__ import annotations
import re
from typing import Any
from pydantic import BaseModel, Field

from kratos.semantics.mdl import SemanticModelMDL, DimensionMDL, MetricMDL


class AnswerabilityResult(BaseModel):
    """Result of the auto-ontology answerability and epistemological validation check."""
    is_answerable: bool
    confidence: float
    matched_entities: list[str] = Field(default_factory=list)
    matched_dimensions: list[str] = Field(default_factory=list)
    matched_metrics: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    reason: str
    suggested_alternatives: list[str] = Field(default_factory=list)


class GroundingContext(BaseModel):
    """Mapped semantic concepts extracted from natural language via Auto-Ontology."""
    primary_metric: MetricMDL | None = None
    primary_dimension: DimensionMDL | None = None
    secondary_dimension: DimensionMDL | None = None
    all_matched_dimensions: list[DimensionMDL] = Field(default_factory=list)
    detected_entities: list[str] = Field(default_factory=list)
    confidence: float = 1.0


class AutoOntologyGrounder:
    """Grounds natural language questions onto certified ontologies and evaluates answerability."""

    # Common business concepts that frequently cause hallucinations when absent from schemas
    KNOWN_OUT_OF_SCOPE_CONCEPTS: dict[str, list[str]] = {
        "costo": ["costo", "costos", "coste", "costes", "cost", "gastos", "egresos", "gasto"],
        "margen": ["margen", "margen de beneficio", "margen bruto", "rentabilidad", "profit margin"],
        "salario": ["salario", "salarios", "sueldo", "sueldos", "nómina", "payroll", "remuneración"],
        "clima": ["clima", "tiempo meteorológico", "temperatura", "lluvia", "weather"],
        "inventario": ["inventario", "stock disponible", "almacén", "bodega", "warehouse"],
    }

    @classmethod
    def check_answerable(cls, query: str, model: SemanticModelMDL) -> AnswerabilityResult:
        """Evaluates whether the user's natural language query is answerable by the ontology."""
        lowered = query.lower()

        # 1. Match Dimensions
        matched_dims: list[DimensionMDL] = []
        for d in model.dimensions:
            if d.id.lower() in lowered:
                matched_dims.append(d)
                continue
            for syn in d.synonyms:
                # Word boundary match
                if re.search(r"\b" + re.escape(syn.lower()) + r"\b", lowered):
                    matched_dims.append(d)
                    break

        # 2. Match Metrics
        matched_mets: list[MetricMDL] = []
        for m in model.metrics:
            if m.id.lower() in lowered:
                matched_mets.append(m)
                continue
            for syn in m.synonyms:
                if re.search(r"\b" + re.escape(syn.lower()) + r"\b", lowered):
                    matched_mets.append(m)
                    break

        # 3. Match Entities
        matched_ents: list[str] = []
        for e in model.entities:
            if e.name.lower() in lowered:
                matched_ents.append(e.name)

        # 4. Check for Out-of-Scope Concepts (Concepts asked by user but not supported in DB)
        missing_concepts: list[str] = []
        for concept_name, triggers in cls.KNOWN_OUT_OF_SCOPE_CONCEPTS.items():
            for trig in triggers:
                if re.search(r"\b" + re.escape(trig) + r"\b", lowered):
                    # Check if this concept is covered by any metric/dimension in model
                    has_coverage = any(
                        trig in m.id.lower() or any(trig in s.lower() for s in m.synonyms)
                        for m in model.metrics
                    ) or any(
                        trig in d.id.lower() or any(trig in s.lower() for s in d.synonyms)
                        for d in model.dimensions
                    )
                    cap_name = concept_name.capitalize()
                    if not has_coverage and cap_name not in missing_concepts:
                        missing_concepts.append(cap_name)

        # If user explicitly requested concepts absent from the ontology:
        if missing_concepts:
            available_metrics_str = ", ".join([m.id for m in model.metrics[:3]])
            available_dims_str = ", ".join([d.id for d in model.dimensions[:4]])
            return AnswerabilityResult(
                is_answerable=False,
                confidence=0.20,
                matched_entities=matched_ents,
                matched_dimensions=[d.id for d in matched_dims],
                matched_metrics=[m.id for m in matched_mets],
                missing_concepts=missing_concepts,
                reason=(
                    f"La ontología '{model.name}' no contiene datos ni métricas para '{', '.join(missing_concepts)}'. "
                    f"Métricas disponibles: [{available_metrics_str}]. Dimensiones disponibles: [{available_dims_str}]."
                ),
                suggested_alternatives=[
                    f"Consultar {model.metrics[0].id} por {model.dimensions[0].id}" if model.metrics and model.dimensions else "Explorar entidades disponibles"
                ]
            )

        # Compute confidence based on ontology grounding coverage
        has_dims = len(matched_dims) > 0
        has_mets = len(matched_mets) > 0

        if has_dims and has_mets:
            confidence = 0.95
            reason = f"Consulta perfectamente alineada con la ontología '{model.name}' (Métrica: {matched_mets[0].id}, Dimensiones: {[d.id for d in matched_dims]})."
        elif has_dims:
            confidence = 0.85
            reason = f"Dimensiones reconocidas en la ontología ({[d.id for d in matched_dims]}); se aplicará métrica analítica predeterminada ({model.metrics[0].id if model.metrics else 'Total'})."
        elif has_mets:
            confidence = 0.80
            reason = f"Métrica identificada ({matched_mets[0].id}); se aplicará dimensión categórica principal ({model.dimensions[0].id if model.dimensions else 'Entidad'})."
        else:
            confidence = 0.65
            reason = f"Consulta general; se resolverá mediante exploración heurística sobre las tablas de '{model.name}'."

        return AnswerabilityResult(
            is_answerable=True,
            confidence=confidence,
            matched_entities=matched_ents,
            matched_dimensions=[d.id for d in matched_dims],
            matched_metrics=[m.id for m in matched_mets],
            missing_concepts=[],
            reason=reason,
            suggested_alternatives=[]
        )

    @classmethod
    def ground(cls, query: str, model: SemanticModelMDL) -> GroundingContext:
        """Grounds a query by extracting primary and secondary dimensions and primary metric."""
        dims = model.find_all_non_temporal_dimensions(query)
        primary_dim = dims[0] if dims else model.find_dimension_by_synonym(query)
        secondary_dim = dims[1] if len(dims) > 1 else None

        metric = model.find_metric_by_synonym(query)
        if not metric and model.metrics:
            metric = model.metrics[0]

        detected_entities = [e.name for e in model.entities if e.name.lower() in query.lower()]

        return GroundingContext(
            primary_metric=metric,
            primary_dimension=primary_dim,
            secondary_dimension=secondary_dim,
            all_matched_dimensions=dims,
            detected_entities=detected_entities,
            confidence=0.95 if (primary_dim and metric) else 0.75
        )
