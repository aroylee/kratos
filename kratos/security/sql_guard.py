"""Kratos SQL Security Guard (4-Layer AST Defense).

Layer 1: Database Engine Permissions (Read-Only Connection)
Layer 2: Protocol / Session Constraints (Read-only transaction & statement timeout)
Layer 3: AST Deterministic Validation via sqlglot
Layer 4: Runtime Fetch Bounding (max_rows cutoff & truncation flag)
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
import sqlglot
from sqlglot import exp


class RejectReason(StrEnum):
    PARSE_ERROR = "parse_error"
    EMPTY_STATEMENT = "empty_statement"
    MULTIPLE_STATEMENTS = "multiple_statements"
    NOT_READ_ONLY = "not_read_only"
    FORBIDDEN_FUNCTION = "forbidden_function"
    TABLE_NOT_ALLOWED = "table_not_allowed"
    SCHEMA_NOT_ALLOWED = "schema_not_allowed"
    TOO_COMPLEX = "too_complex"


# Nodes that alter schema, state, permissions, or records
WRITE_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Grant,
    exp.Merge,
    exp.Copy,
    exp.Set,
    exp.Attach,
    exp.Detach,
    exp.Pragma,
    exp.LoadData,
    exp.Install,
    exp.Use,
    exp.Command,
)

# Functions that perform file I/O, execute host commands, or sleep
FORBIDDEN_FUNCTIONS: frozenset[str] = frozenset({
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "pg_sleep", "pg_sleep_for", "pg_sleep_until", "pg_terminate_backend",
    "dblink", "dblink_connect", "dblink_exec", "lo_import", "lo_export",
    "read_csv", "read_csv_auto", "read_parquet", "parquet_scan", "read_text",
    "read_blob", "glob", "sqlite_scan", "postgres_scan"
})

FORBIDDEN_TABLES: frozenset[str] = frozenset({
    "pg_shadow", "pg_authid", "pg_user_mapping", "pg_largeobject", "sqlite_master"
})

SYSTEM_SCHEMAS: frozenset[str] = frozenset({
    "pg_catalog", "information_schema", "pg_toast"
})


@dataclass
class GuardLimits:
    max_rows: int = 500
    max_joins: int = 10
    max_subqueries: int = 10
    max_union_branches: int = 5
    max_depth: int = 15


@dataclass
class GuardResult:
    allowed: bool
    reason: RejectReason | None = None
    detail: str | None = None
    sanitized_sql: str | None = None
    tables: list[str] = field(default_factory=list)
    limit_applied: int | None = None
    warnings: list[str] = field(default_factory=list)


def _reject(reason: RejectReason, detail: str) -> GuardResult:
    return GuardResult(allowed=False, reason=reason, detail=detail)


def _collect_tables(tree: exp.Expression) -> tuple[list[str], set[str]]:
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    tables: list[str] = []
    schemas: set[str] = set()

    for table in tree.find_all(exp.Table):
        name = table.name
        if not name or name.lower() in cte_names:
            continue
        full_name = f"{table.db}.{name}" if table.db else name
        tables.append(full_name)
        if table.db:
            schemas.add(table.db.lower())

    return tables, schemas


def _check_complexity(tree: exp.Expression, limits: GuardLimits) -> GuardResult | None:
    joins = len(list(tree.find_all(exp.Join)))
    if joins > limits.max_joins:
        return _reject(RejectReason.TOO_COMPLEX, f"Query join count ({joins}) exceeds limit ({limits.max_joins}).")

    subqueries = len(list(tree.find_all(exp.Subquery)))
    if subqueries > limits.max_subqueries:
        return _reject(RejectReason.TOO_COMPLEX, f"Subquery count ({subqueries}) exceeds limit ({limits.max_subqueries}).")

    unions = len(list(tree.find_all(exp.Union)))
    if unions >= limits.max_union_branches:
        return _reject(RejectReason.TOO_COMPLEX, f"Union branches ({unions + 1}) exceed limit ({limits.max_union_branches}).")

    return None


def _apply_limit(tree: exp.Expression, max_rows: int) -> tuple[exp.Expression, int]:
    if not isinstance(tree, exp.Select | exp.Union):
        return tree, max_rows

    existing = tree.args.get("limit")
    if existing is None:
        return tree.limit(max_rows), max_rows

    try:
        current = int(existing.expression.name)
    except (AttributeError, ValueError):
        return tree.limit(max_rows), max_rows

    if current > max_rows:
        return tree.limit(max_rows), max_rows

    return tree, current


def validate_sql(
    sql: str,
    *,
    allowed_tables: set[str] | None = None,
    allowed_schemas: set[str] | None = None,
    limits: GuardLimits | None = None,
    apply_limit: bool = True,
    dialect: str = "sqlite",
) -> GuardResult:
    """Deterministic AST-based SQL validation."""
    limits = limits or GuardLimits()

    if not sql or not sql.strip():
        return _reject(RejectReason.EMPTY_STATEMENT, "Query is empty.")

    try:
        statements = sqlglot.parse(sql, dialect=dialect)
    except Exception as exc:
        return _reject(RejectReason.PARSE_ERROR, f"SQL syntax parsing failed: {exc}")

    statements = [s for s in statements if s is not None]
    if not statements:
        return _reject(RejectReason.EMPTY_STATEMENT, "Query is empty.")

    if len(statements) > 1:
        return _reject(RejectReason.MULTIPLE_STATEMENTS, f"Multiple statements ({len(statements)}) detected. Only single queries allowed.")

    tree = statements[0]

    # Root statement must be read-only query
    if not isinstance(tree, exp.Select | exp.Union | exp.Subquery):
        return _reject(RejectReason.NOT_READ_ONLY, f"Only read queries permitted. Received: {type(tree).__name__.upper()}.")

    # Deep scan for write / mutation nodes
    for node_type in WRITE_NODES:
        if tree.find(node_type) is not None:
            return _reject(RejectReason.NOT_READ_ONLY, f"Prohibited operation '{node_type.__name__.upper()}' detected.")

    # Block transaction row locks
    if tree.find(exp.Lock) is not None:
        return _reject(RejectReason.NOT_READ_ONLY, "Row lock directives (FOR UPDATE / FOR SHARE) are prohibited.")

    # Block SELECT ... INTO
    if tree.args.get("into") is not None:
        return _reject(RejectReason.NOT_READ_ONLY, "SELECT ... INTO is prohibited.")

    # Prohibited function scan
    for func in tree.find_all(exp.Anonymous):
        name = (func.this or "").lower() if isinstance(func.this, str) else ""
        if name in FORBIDDEN_FUNCTIONS:
            return _reject(RejectReason.FORBIDDEN_FUNCTION, f"Function '{name}()' is prohibited.")

    lowered = sql.lower().replace(" ", "")
    for name in FORBIDDEN_FUNCTIONS:
        if f"{name}(" in lowered:
            return _reject(RejectReason.FORBIDDEN_FUNCTION, f"Function '{name}()' is prohibited.")

    # Table & schema allowlist check
    tables, schemas = _collect_tables(tree)
    for t in tables:
        bare = t.split(".")[-1].lower()
        if bare in FORBIDDEN_TABLES:
            return _reject(RejectReason.TABLE_NOT_ALLOWED, f"System table '{t}' is protected.")

    for s in schemas:
        if s in SYSTEM_SCHEMAS:
            return _reject(RejectReason.SCHEMA_NOT_ALLOWED, f"System schema '{s}' is protected.")
        if allowed_schemas is not None and s not in allowed_schemas:
            return _reject(RejectReason.SCHEMA_NOT_ALLOWED, f"Schema '{s}' is not allowed in this engine.")

    if allowed_tables is not None:
        normalized_allowed = {t.lower() for t in allowed_tables}
        for t in tables:
            bare = t.split(".")[-1].lower()
            if bare not in normalized_allowed:
                return _reject(RejectReason.TABLE_NOT_ALLOWED, f"Table '{t}' is not present in target engine schema.")

    # Complexity checks
    comp = _check_complexity(tree, limits)
    if comp is not None:
        return comp

    if tree.depth > limits.max_depth:
        return _reject(RejectReason.TOO_COMPLEX, f"Query depth ({tree.depth}) exceeds limit ({limits.max_depth}).")

    limit_applied = None
    if apply_limit:
        tree, limit_applied = _apply_limit(tree, limits.max_rows)

    return GuardResult(
        allowed=True,
        sanitized_sql=tree.sql(dialect=dialect),
        tables=sorted(set(tables)),
        limit_applied=limit_applied,
    )
