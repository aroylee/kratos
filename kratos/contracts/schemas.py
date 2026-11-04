"""Kratos Formal Agent Contracts & Typed Schemas.

Enforces deterministic communication between agents:
    User Request -> InterpretedRequest -> DataTask -> DataEvidence -> FinalAnswer
"""

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class Intent(StrEnum):
    """User intent classification."""
    DESCRIBE_DATABASE = "DESCRIBE_DATABASE"
    EXPLORE_SCHEMA = "EXPLORE_SCHEMA"
    FIND_DATA = "FIND_DATA"
    QUERY_DATA = "QUERY_DATA"
    ANALYZE_DATA = "ANALYZE_DATA"
    COMPARE_DATA = "COMPARE_DATA"
    EXPLAIN_RELATIONSHIP = "EXPLAIN_RELATIONSHIP"
    PROFILE_DATA = "PROFILE_DATA"
    DISCOVER_INSIGHTS = "DISCOVER_INSIGHTS"
    FOLLOW_UP = "FOLLOW_UP"


class AnalyticalPattern(StrEnum):
    """Core analytical pattern requested in natural language."""
    TIME_SERIES = "TIME_SERIES"                     # Tendencias temporales (semanal, mensual, anual)
    CATEGORICAL_BREAKDOWN = "CATEGORICAL_BREAKDOWN" # Distribución por categorías o grupos
    RANKING_TOP_N = "RANKING_TOP_N"                 # Rankings líderes (Top 5, Top 10)
    GEO_DISTRIBUTION = "GEO_DISTRIBUTION"           # Distribución por país, región o ciudad
    AGGREGATE_KPI = "AGGREGATE_KPI"                 # Métrica agregada global (total, promedio)
    SCHEMA_OVERVIEW = "SCHEMA_OVERVIEW"             # Estructura del esquema


class TimeGranularity(StrEnum):
    """Temporal grain for time-series analysis."""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"
    NONE = "NONE"


class MetricTarget(StrEnum):
    """Business metric requested."""
    REVENUE = "REVENUE"       # Ventas / Facturación ($ USD)
    ORDERS = "ORDERS"         # Conteo de pedidos / transacciones
    QUANTITY = "QUANTITY"     # Unidades físicas de producto
    CUSTOMERS = "CUSTOMERS"   # Conteo de clientes
    AVERAGE = "AVERAGE"       # Promedio
    COUNT_ENTITIES = "COUNT_ENTITIES" # Conteo genérico
    GENERIC = "GENERIC"


class InterpretedRequest(BaseModel):
    """Rich analytical intent and scope extraction from natural language."""
    intent: Intent
    goal: str = Field(description="Clear single-sentence analytical objective")
    analytical_pattern: AnalyticalPattern = Field(
        default=AnalyticalPattern.CATEGORICAL_BREAKDOWN,
        description="Analytical archetype extracted from user intent"
    )
    time_granularity: TimeGranularity = Field(
        default=TimeGranularity.NONE,
        description="Temporal granularity (weekly, monthly, etc.) if applicable"
    )
    metric_target: MetricTarget = Field(
        default=MetricTarget.REVENUE,
        description="Primary business metric targeted"
    )
    dimensions: list[str] = Field(
        default_factory=list,
        description="Extracted dimensions e.g. ['semana', 'categoria', 'pais']"
    )
    metrics: list[str] = Field(
        default_factory=list,
        description="Extracted target metric aliases e.g. ['Ventas_USD']"
    )
    needs_investigation: bool = Field(
        default=True,
        description="False if the schema/profile metadata alone is sufficient"
    )
    required_evidence: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    clarification_needed: str | None = None


class DataTask(BaseModel):
    """Structured, immutable contract dispatched to the Investigator Agent."""
    intent: Intent
    engine_id: str = Field(description="Target analytical database engine ID")
    goal: str = Field(description="Precise analytical objective")
    analytical_pattern: AnalyticalPattern = Field(
        default=AnalyticalPattern.CATEGORICAL_BREAKDOWN,
        description="Analytical archetype (TIME_SERIES, RANKING_TOP_N, etc.)"
    )
    time_granularity: TimeGranularity = Field(
        default=TimeGranularity.NONE,
        description="Temporal frequency extracted from the user inquiry"
    )
    metric_target: MetricTarget = Field(
        default=MetricTarget.REVENUE,
        description="Primary metric to compute"
    )
    dimensions: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    prior_context: str = ""


class ExecutedQuery(BaseModel):
    """Record of a safe query execution."""
    sql: str
    engine_id: str
    row_count: int = 0
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    execution_ms: float = 0.0
    truncated: bool = False
    error: str | None = None


class DataEvidence(BaseModel):
    """Synthesized facts returned by the Investigator Agent."""
    engine_id: str
    observations: list[str] = Field(
        default_factory=list,
        description="Factual numerical observations derived strictly from data"
    )
    queries: list[ExecutedQuery] = Field(default_factory=list)
    tables_used: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    incomplete: bool = Field(default=False)


class ExecutiveStorytelling(BaseModel):
    """Executive decision framework summary."""
    key_takeaway: str = Field(description="One-sentence direct conclusion with precise metric unit")
    quantitative_findings: list[str] = Field(description="Key metrics with units ($, %, days, orders, units)")
    strategic_recommendations: list[str] = Field(description="1-2 actionable decisions based on the data")


class FinalAnswer(BaseModel):
    """Complete client-facing response payload."""
    storytelling: ExecutiveStorytelling
    evidence: DataEvidence
    visualization: dict[str, Any] | None = None
    suggested_questions: list[str] = Field(default_factory=list)
