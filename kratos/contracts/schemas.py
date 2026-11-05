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
    TIME_SERIES = "TIME_SERIES"                     # Tendencias temporales mono-serie
    MULTI_SERIES_TIME_SERIES = "MULTI_SERIES_TIME_SERIES" # Tendencias temporales multi-serie (desglose por categoría/grupo)
    PARTITIONED_RANKING = "PARTITIONED_RANKING"     # Rankings particionados por período (Window Function ROW_NUMBER() OVER PARTITION BY)
    CATEGORICAL_BREAKDOWN = "CATEGORICAL_BREAKDOWN" # Distribución por categorías o grupos
    RANKING_TOP_N = "RANKING_TOP_N"                 # Rankings líderes (Top 5, Top 10)
    GEO_DISTRIBUTION = "GEO_DISTRIBUTION"           # Distribución por país, región o ciudad
    GEO_PARTITIONED_RANKING = "GEO_PARTITIONED_RANKING" # Categoría dominante o ranking particionado por geografía (Window Function)
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
        description="Temporal granularity (weekly, monthly, daily) if applicable"
    )
    time_dimension: str | None = Field(
        default=None,
        description="Primary chronological dimension for X-Axis (e.g. 'Fecha', 'Semana')"
    )
    series_dimension: str | None = Field(
        default=None,
        description="Breakdown/Pivot dimension generating multiple lines (e.g. 'Categoria', 'Empleado')"
    )
    metric_target: MetricTarget = Field(
        default=MetricTarget.REVENUE,
        description="Primary business metric targeted"
    )
    top_n: int | None = Field(
        default=None,
        description="Top N entities limit extracted from query (e.g. Top 3, Top 5)"
    )
    ranking_criterion: str | None = Field(
        default=None,
        description="Criterion for ranking (e.g. 'desempeño', 'ventas', 'pedidos')"
    )
    dimensions: list[str] = Field(
        default_factory=list,
        description="Extracted dimensions e.g. ['Fecha', 'Categoria']"
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
        description="Analytical archetype (TIME_SERIES, MULTI_SERIES_TIME_SERIES, etc.)"
    )
    time_granularity: TimeGranularity = Field(
        default=TimeGranularity.NONE,
        description="Temporal frequency extracted from the user inquiry"
    )
    time_dimension: str | None = Field(
        default=None,
        description="Primary chronological dimension for X-Axis"
    )
    series_dimension: str | None = Field(
        default=None,
        description="Breakdown/Pivot dimension generating multiple series lines"
    )
    metric_target: MetricTarget = Field(
        default=MetricTarget.REVENUE,
        description="Primary metric to compute"
    )
    top_n: int | None = Field(
        default=None,
        description="Top N cohort limit (e.g. 3 for '3 mejores')"
    )
    ranking_criterion: str | None = Field(
        default=None,
        description="Ranking metric criterion (e.g. 'desempeño', 'volumen')"
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
    """Executive decision framework summary with diagnostic intelligence."""
    key_takeaway: str = Field(description="One-sentence direct conclusion with precise metric unit")
    diagnostic_metrics: dict[str, Any] = Field(default_factory=dict, description="Calculated statistical diagnostic metrics")
    quantitative_findings: list[str] = Field(description="Key metrics with units ($, %, days, orders, units)")
    risk_alerts: list[str] = Field(default_factory=list, description="Business risk, concentration, or volatility alerts")
    strategic_recommendations: list[str] = Field(description="1-2 actionable decisions based on the data")


class FinalAnswer(BaseModel):
    """Complete client-facing response payload."""
    storytelling: ExecutiveStorytelling
    evidence: DataEvidence
    visualization: dict[str, Any] | None = None
    task: DataTask | None = None
    suggested_questions: list[str] = Field(default_factory=list)
    has_archify: bool = False
    archify_url: str | None = None
    archify_entities: list[dict[str, Any]] = Field(default_factory=list)
