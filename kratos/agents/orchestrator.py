"""Kratos Two-Agent System: Interpreter & Investigator with Auto-Reflection."""

import os
from kratos.contracts.schemas import (
    Intent,
    InterpretedRequest,
    DataTask,
    ExecutedQuery,
    DataEvidence,
    ExecutiveStorytelling,
    FinalAnswer,
)
from kratos.security.sql_guard import validate_sql, RejectReason
from kratos.engines.registry import EngineRegistry, DatabaseEngine
from kratos.semantics.bi_engine import compile_echarts
from kratos.semantics.unit_utils import infer_column_unit, format_metric_value
from kratos.inference.schema_pruner import SchemaPruner
from kratos.inference.client import LLMClient


class InterpreterAgent:
    """Agent A: Intent classification, DataTask generation, and executive storytelling."""

    def interpret(self, query: str, active_engine_id: str) -> InterpretedRequest:
        lowered = query.lower()
        intent = Intent.QUERY_DATA

        if any(w in lowered for w in ["esquema", "tablas", "estructura", "schema", "columnas"]):
            intent = Intent.EXPLORE_SCHEMA
        elif any(w in lowered for w in ["que contiene", "de que trata", "describe", "resumen de base"]):
            intent = Intent.DESCRIBE_DATABASE

        return InterpretedRequest(
            intent=intent,
            goal=query,
            needs_investigation=True,
            constraints=[],
            required_evidence=["Datos numéricos agregados", "Dimensiones analíticas"],
        )

    def formulate_storytelling(self, task: DataTask, evidence: DataEvidence) -> ExecutiveStorytelling:
        if not evidence.observations:
            return ExecutiveStorytelling(
                key_takeaway=f"No se registraron datos en el motor '{task.engine_id}' para la consulta solicitada.",
                quantitative_findings=["Registros encontrados: 0"],
                strategic_recommendations=["Verificar filtros o explorar tablas disponibles en el esquema."],
            )

        top_obs = evidence.observations[0]
        return ExecutiveStorytelling(
            key_takeaway=f"Análisis completado: {top_obs}.",
            quantitative_findings=evidence.observations[:4],
            strategic_recommendations=[
                "Monitorear las categorías y entidades líderes observadas en la distribución.",
                "Profundizar el análisis cruzando con períodos o dimensiones adicionales.",
            ],
        )


class InvestigatorAgent:
    """Agent B: Investigates database schemas, executes safe queries, and collects facts with AST auto-reflection."""

    def __init__(self, registry: EngineRegistry):
        self.registry = registry
        self.pruner = SchemaPruner()
        self.llm = LLMClient()
        self.max_reflections = 3

    def execute_task(self, task: DataTask) -> DataEvidence:
        engine = self.registry.engines.get(task.engine_id)
        if not engine:
            return DataEvidence(
                engine_id=task.engine_id,
                observations=["Motor no encontrado"],
                confidence=0.0,
                warnings=[f"Motor '{task.engine_id}' no disponible"],
            )

        full_schema = engine.introspect()
        allowed_tables = set(full_schema.keys())

        # Step 1: Schema Pruning & Business Rule Injection
        pruned_schema, rules = self.pruner.prune(task.goal, task.engine_id, full_schema)

        # Step 2: Investigation & Auto-Reflection Loop
        executed_query = None
        warnings = []
        last_rejection_detail = None

        for attempt in range(1, self.max_reflections + 1):
            sql = None
            if attempt == 1:
                sql = self.llm.generate_sql(task.goal, task.engine_id, pruned_schema, rules)

            if not sql:
                sql = self._generate_fallback_sql(task, engine, full_schema, last_rejection_detail)

            # Layer 3 Security Check: AST validation with sqlglot
            guard_res = validate_sql(sql, allowed_tables=allowed_tables, dialect="sqlite")

            if guard_res.allowed:
                try:
                    # Layer 1, 2, 4 Execution with runtime fetch bounding
                    cols, rows, duration_ms, truncated = engine.execute_readonly(guard_res.sanitized_sql)
                    executed_query = ExecutedQuery(
                        sql=guard_res.sanitized_sql,
                        engine_id=task.engine_id,
                        row_count=len(rows),
                        columns=cols,
                        rows=rows,
                        execution_ms=round(duration_ms, 2),
                        truncated=truncated,
                    )
                    break
                except Exception as exc:
                    last_rejection_detail = str(exc)
                    warnings.append(f"Intento {attempt} falló en ejecución ({str(exc)})")
            else:
                last_rejection_detail = f"{guard_res.reason}: {guard_res.detail}"
                warnings.append(f"Intento {attempt} rechazado por Security Guard ({last_rejection_detail})")

        if not executed_query:
            return DataEvidence(
                engine_id=task.engine_id,
                observations=[],
                confidence=0.0,
                warnings=warnings or ["No fue posible validar una consulta segura."],
            )

        # Synthesize factual observations
        rows = executed_query.rows
        observations = []
        if rows:
            first_row = rows[0]
            for col, val in first_row.items():
                unit = infer_column_unit(col)
                formatted = format_metric_value(val, unit)
                observations.append(f"{col}: {formatted}")

            if len(rows) > 1:
                observations.append(f"Total de entidades o filas devueltas: {len(rows):,}")

        return DataEvidence(
            engine_id=task.engine_id,
            observations=observations,
            queries=[executed_query],
            tables_used=guard_res.tables if guard_res.allowed else [],
            confidence=0.95 if rows else 0.5,
            warnings=warnings,
        )

    def _generate_fallback_sql(
        self,
        task: DataTask,
        engine: DatabaseEngine,
        schema: dict,
        rejection_detail: str | None = None
    ) -> str:
        lowered = task.goal.lower()

        # Northwind
        if engine.engine_id == "northwind":
            if "empleado" in lowered or "ventas por empleado" in lowered:
                return (
                    'SELECT e.lastName || ", " || e.firstName AS Empleado, '
                    'ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD '
                    'FROM orders o '
                    'JOIN employees e ON o.employeeID = e.employeeID '
                    'JOIN order_details od ON o.orderID = od.orderID '
                    'GROUP BY Empleado ORDER BY Ventas_USD DESC LIMIT 10;'
                )
            if "cliente" in lowered or "clientes" in lowered:
                return "SELECT country AS Pais, COUNT(customerID) AS Clientes FROM customers GROUP BY country ORDER BY Clientes DESC LIMIT 10;"
            return (
                'SELECT c.categoryName AS Categoria, ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD '
                'FROM categories c '
                'JOIN products p ON c.categoryID = p.categoryID '
                'JOIN order_details od ON p.productID = od.productID '
                'GROUP BY Categoria ORDER BY Ventas_USD DESC LIMIT 10;'
            )

        # Chinook
        if engine.engine_id == "chinook":
            if "artista" in lowered or "cancion" in lowered or "track" in lowered:
                return (
                    "SELECT ar.Name AS Artista, COUNT(t.TrackId) AS Canciones "
                    "FROM Artist ar "
                    "JOIN Album al ON ar.ArtistId = al.ArtistId "
                    "JOIN Track t ON al.AlbumId = t.AlbumId "
                    "GROUP BY Artista ORDER BY Canciones DESC LIMIT 10;"
                )
            if "genero" in lowered or "genre" in lowered:
                return (
                    "SELECT g.Name AS Genero, COUNT(t.TrackId) AS Canciones "
                    "FROM Genre g "
                    "JOIN Track t ON g.GenreId = t.GenreId "
                    "GROUP BY Genero ORDER BY Canciones DESC LIMIT 10;"
                )
            return (
                "SELECT c.Country AS Pais, ROUND(SUM(i.Total), 2) AS Facturacion_USD "
                "FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId "
                "GROUP BY Pais ORDER BY Facturacion_USD DESC LIMIT 10;"
            )

        # Sakila
        if engine.engine_id == "sakila":
            if "actor" in lowered or "actores" in lowered:
                return (
                    "SELECT a.first_name || ' ' || a.last_name AS Actor, COUNT(fa.film_id) AS Peliculas "
                    "FROM actor a JOIN film_actor fa ON a.actor_id = fa.actor_id "
                    "GROUP BY Actor ORDER BY Peliculas DESC LIMIT 10;"
                )
            return (
                "SELECT c.name AS Categoria, COUNT(fc.film_id) AS Peliculas "
                "FROM category c JOIN film_category fc ON c.category_id = fc.category_id "
                "GROUP BY Categoria ORDER BY Peliculas DESC LIMIT 10;"
            )

        # TPC-H
        if engine.engine_id == "tpch":
            return (
                "SELECT n.n_name AS Pais, COUNT(c.c_custkey) AS Clientes "
                "FROM customer c JOIN nation n ON c.c_nationkey = n.n_nationkey "
                "GROUP BY Pais ORDER BY Clientes DESC LIMIT 10;"
            )

        # AdventureWorks / Generic fallback
        first_table = list(schema.keys())[0] if schema else "sqlite_master"
        return f"SELECT * FROM {first_table} LIMIT 10;"
