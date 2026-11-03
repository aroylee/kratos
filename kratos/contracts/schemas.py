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


class InterpretedRequest(BaseModel):
    """Intent and scope extraction from raw natural language."""
    intent: Intent
    goal: str = Field(description="Clear single-sentence analytical objective")
    needs_investigation: bool = Field(
        default=True,
        description="False if the schema/profile metadata alone is sufficient"
    )
    required_evidence: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    clarification_needed: str | None = None


class DataTask(BaseModel):
    """Structured contract dispatched to the Investigator Agent."""
    intent: Intent
    engine_id: str = Field(description="Target analytical database engine ID")
    goal: str = Field(description="Precise analytical objective")
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
