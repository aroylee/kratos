"""Kratos Two-Agent System: Interpreter & Investigator with Auto-Reflection."""

import os
import re
from kratos.contracts.schemas import (
    Intent,
    InterpretedRequest,
    DataTask,
    ExecutedQuery,
    DataEvidence,
    ExecutiveStorytelling,
    FinalAnswer,
    AnalyticalPattern,
    TimeGranularity,
    MetricTarget,
)
from kratos.security.sql_guard import validate_sql, RejectReason
from kratos.engines.registry import EngineRegistry, DatabaseEngine
from kratos.semantics.bi_engine import compile_echarts
from kratos.semantics.unit_utils import infer_column_unit, format_metric_value
from kratos.semantics.mdl import SemanticCatalog
from kratos.semantics.compiler import SemanticCompiler
from kratos.inference.schema_pruner import SchemaPruner
from kratos.inference.client import LLMClient


class InterpreterAgent:
    """Agent A: Intent classification, DataTask generation, and executive storytelling."""

    def __init__(self):
        self.semantic_catalog = SemanticCatalog()

    def interpret(self, query: str, active_engine_id: str) -> InterpretedRequest:
        lowered = query.lower()
        intent = Intent.QUERY_DATA

        # 1. Intent Detection
        if any(w in lowered for w in ["esquema", "tablas", "estructura", "schema", "columnas"]):
            intent = Intent.EXPLORE_SCHEMA
        elif any(w in lowered for w in ["que contiene", "de que trata", "describe", "resumen de base"]):
            intent = Intent.DESCRIBE_DATABASE
        elif any(w in lowered for w in ["tendencia", "tiempo", "evolucion", "evolución", "comparar", "analiza", "analizar"]):
            intent = Intent.ANALYZE_DATA

        # 2. Time-series & Temporal Grain Detection
        is_time_series = any(w in lowered for w in [
            "tendencia", "tiempo", "semanal", "semana", "mensual", "mes",
            "anual", "año", "ano", "diario", "dia", "día", "diaria", "evolucion", "evolución",
            "historico", "histórico", "a través del tiempo", "traves del tiempo"
        ])

        time_granularity = TimeGranularity.NONE
        time_dimension = None

        if is_time_series:
            if any(w in lowered for w in ["diario", "diaria", "dia", "día", "dias", "días", "daily"]):
                time_granularity = TimeGranularity.DAILY
                time_dimension = "Fecha"
            elif any(w in lowered for w in ["semanal", "semana", "semanas", "week", "weekly"]):
                time_granularity = TimeGranularity.WEEKLY
                time_dimension = "Semana"
            elif any(w in lowered for w in ["mensual", "mes", "meses", "month", "monthly"]):
                time_granularity = TimeGranularity.MONTHLY
                time_dimension = "Mes"
            elif any(w in lowered for w in ["anual", "año", "ano", "años", "anos", "year", "yearly"]):
                time_granularity = TimeGranularity.YEARLY
                time_dimension = "Ano"
            else:
                time_granularity = TimeGranularity.DAILY if "diar" in lowered else TimeGranularity.MONTHLY
                time_dimension = "Fecha" if time_granularity == TimeGranularity.DAILY else "Mes"

        # 3. Multi-Series Breakdown Detection
        has_category = any(w in lowered for w in ["categoria", "categoría", "categorias", "categorías", "lineas", "líneas"])
        has_employee = any(w in lowered for w in ["empleado", "empleados", "vendedor", "vendedores"])
        has_country = any(w in lowered for w in ["pais", "país", "paises", "países"])
        has_genre = any(w in lowered for w in ["genero", "género", "generos", "géneros"])

        series_dimension = None

        # 4. Top-N and Ranking Extraction (Extract before Pattern to ground correctly)
        top_n = None
        ranking_criterion = None

        top_match = re.search(r"(?:top|primeras?|primeros?|las?|los?)\s*(\d+)", lowered)
        if top_match:
            top_n = int(top_match.group(1))
        else:
            word_to_num = {"dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "diez": 10}
            for w, n in word_to_num.items():
                if re.search(rf"(?:top|primeras?|primeros?|las?|los?)\s+{w}", lowered):
                    top_n = n
                    break

        if any(w in lowered for w in ["mejor desempeño", "mejores desempeños", "mejor rendimiento", "más ventas", "mas ventas", "mayores ventas", "mejores", "mejor"]):
            ranking_criterion = "mejor desempeño"
        elif any(w in lowered for w in ["peor desempeño", "menos ventas", "menores ventas", "peores", "peor"]):
            ranking_criterion = "menor desempeño"

        # 5. Analytical Pattern Detection
        if is_time_series and (has_category or has_employee or has_country or has_genre):
            analytical_pattern = AnalyticalPattern.MULTI_SERIES_TIME_SERIES
            if has_category:
                series_dimension = "Categoria"
            elif has_employee:
                series_dimension = "Empleado"
            elif has_genre:
                series_dimension = "Genero"
            elif has_country:
                series_dimension = "Pais"
        elif is_time_series:
            analytical_pattern = AnalyticalPattern.TIME_SERIES
        elif top_n is not None or any(w in lowered for w in ["top", "mejores", "mejor", "primeros", "primeras", "ranking", "lideres", "líderes", "lider", "líder", "mas", "más", "peor", "peores"]):
            analytical_pattern = AnalyticalPattern.RANKING_TOP_N
        elif any(w in lowered for w in ["pais", "país", "paises", "países", "ciudad", "ciudades", "region", "región"]):
            analytical_pattern = AnalyticalPattern.GEO_DISTRIBUTION
        else:
            analytical_pattern = AnalyticalPattern.CATEGORICAL_BREAKDOWN

        # 6. Metric Target Detection
        metric_target = MetricTarget.REVENUE
        if any(w in lowered for w in ["pedido", "pedidos", "orden", "ordenes", "órdenes", "orders"]):
            metric_target = MetricTarget.ORDERS
        elif any(w in lowered for w in ["cliente", "clientes", "customers"]):
            metric_target = MetricTarget.CUSTOMERS
        elif any(w in lowered for w in ["unidad", "unidades", "stock", "cantidad", "piezas"]):
            metric_target = MetricTarget.QUANTITY
        elif any(w in lowered for w in ["cancion", "canciones", "track", "pelicula", "peliculas", "películas"]):
            metric_target = MetricTarget.COUNT_ENTITIES

        # 7. Dimensions & Metrics Aliases using Wren MDL Semantic Catalog
        dimensions: list[str] = []
        metrics: list[str] = []

        model = self.semantic_catalog.get_model(active_engine_id)

        if analytical_pattern == AnalyticalPattern.MULTI_SERIES_TIME_SERIES:
            if time_dimension:
                dimensions.append(time_dimension)
            if series_dimension:
                dimensions.append(series_dimension)
        elif analytical_pattern == AnalyticalPattern.TIME_SERIES:
            if time_dimension:
                dimensions.append(time_dimension)
        else:
            matched_dim = model.find_dimension_by_synonym(query) if model else None
            if matched_dim:
                dimensions.append(matched_dim.id)
            elif analytical_pattern == AnalyticalPattern.GEO_DISTRIBUTION or any(w in lowered for w in ["pais", "país", "paises", "países"]):
                dimensions.append("Pais")
            elif any(w in lowered for w in ["producto", "productos", "articulo", "artículo", "articulos", "artículos", "item", "items"]):
                dimensions.append("Producto")
            elif any(w in lowered for w in ["empleado", "empleados", "vendedor", "vendedores"]):
                dimensions.append("Empleado")
            elif any(w in lowered for w in ["cliente", "clientes", "comprador", "compradores"]):
                dimensions.append("Cliente")
            elif any(w in lowered for w in ["proveedor", "proveedores", "supplier", "suppliers"]):
                dimensions.append("Proveedor")
            elif any(w in lowered for w in ["artista", "artistas"]):
                dimensions.append("Artista")
            elif any(w in lowered for w in ["actor", "actores", "actriz", "actrices"]):
                dimensions.append("Actor")
            elif any(w in lowered for w in ["genero", "género", "generos", "géneros"]):
                dimensions.append("Genero")
            else:
                dimensions.append("Categoria")

        matched_met = model.find_metric_by_synonym(query) if model else None
        if matched_met:
            metrics.append(matched_met.id)
        elif metric_target == MetricTarget.REVENUE:
            metrics.append("Ventas_USD" if active_engine_id in ["northwind", "adventureworks_dw"] else "Facturacion_USD")
        elif metric_target == MetricTarget.ORDERS:
            metrics.append("Pedidos" if active_engine_id in ["northwind", "tpch"] else "Facturas")
        elif metric_target == MetricTarget.CUSTOMERS:
            metrics.append("Clientes")
        else:
            metrics.append("Total")

        return InterpretedRequest(
            intent=intent,
            goal=query,
            analytical_pattern=analytical_pattern,
            time_granularity=time_granularity,
            time_dimension=time_dimension,
            series_dimension=series_dimension,
            metric_target=metric_target,
            top_n=top_n,
            ranking_criterion=ranking_criterion,
            dimensions=dimensions,
            metrics=metrics,
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

        if task.analytical_pattern == AnalyticalPattern.MULTI_SERIES_TIME_SERIES:
            s_name = task.series_dimension or "segmento"
            g_name = task.time_granularity.value.lower()
            distinct_series = []
            if evidence.queries and evidence.queries[0].rows and task.series_dimension:
                s_col = task.series_dimension
                distinct_series = list(dict.fromkeys(r[s_col] for r in evidence.queries[0].rows if s_col in r))

            if task.top_n and distinct_series:
                series_str = ", ".join(distinct_series[:task.top_n])
                key_takeaway = f"Tendencia multi-serie ({g_name}) para las Top {task.top_n} {s_name} de {task.ranking_criterion or 'mejor desempeño'} ({series_str}): {top_obs}."
            else:
                key_takeaway = f"Tendencia multi-serie identificada ({g_name} por {s_name}): {top_obs}."

            recommendations = [
                f"Comparar la evolución temporal relativa entre las diferentes líneas de {s_name}.",
                "Monitorear los segmentos con mayor dinamismo para anticipar patrones de demanda o abastecimiento.",
            ]
        elif task.analytical_pattern == AnalyticalPattern.TIME_SERIES:
            key_takeaway = f"Tendencia temporal identificada ({task.time_granularity.value.lower()}): {top_obs}."
            recommendations = [
                "Evaluar la estacionalidad y puntos de inflexión a lo largo del tiempo.",
                "Comparar con períodos homólogos anteriores para detectar patrones de crecimiento o desaceleración.",
            ]
        elif task.analytical_pattern == AnalyticalPattern.RANKING_TOP_N or task.top_n is not None:
            dim_label = task.dimensions[0] if task.dimensions else "entidades"
            n_str = f"Top {task.top_n}" if task.top_n else "Ranking de"
            crit = task.ranking_criterion or "mejor desempeño"
            key_takeaway = f"{n_str} {dim_label} con {crit}: {top_obs}."
            recommendations = [
                f"Focalizar estrategias comerciales y de inventario en los {dim_label} líderes.",
                f"Identificar factores clave de éxito de los líderes para potenciar el resto de {dim_label}.",
            ]
        else:
            key_takeaway = f"Análisis completado: {top_obs}."
            recommendations = [
                "Monitorear las categorías y entidades líderes observadas en la distribución.",
                "Profundizar el análisis cruzando con períodos o dimensiones adicionales.",
            ]

        return ExecutiveStorytelling(
            key_takeaway=key_takeaway,
            quantitative_findings=evidence.observations[:4],
            strategic_recommendations=recommendations,
        )


class InvestigatorAgent:
    """Agent B: Investigates database schemas, executes safe queries, and collects facts with AST auto-reflection."""

    def __init__(self, registry: EngineRegistry):
        self.registry = registry
        self.pruner = SchemaPruner()
        self.llm = LLMClient()
        self.semantic_catalog = SemanticCatalog()
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
            if task.top_n and len(rows) <= 10:
                dim_col = task.dimensions[0] if (task.dimensions and task.dimensions[0] in rows[0]) else list(rows[0].keys())[0]
                val_col = task.metrics[0] if (task.metrics and task.metrics[0] in rows[0]) else (list(rows[0].keys())[1] if len(rows[0]) > 1 else list(rows[0].keys())[0])
                val_unit = infer_column_unit(val_col)
                for idx, r in enumerate(rows, 1):
                    dim_val = r.get(dim_col, f"Item {idx}")
                    val_formatted = format_metric_value(r.get(val_col, 0), val_unit)
                    observations.append(f"#{idx} {dim_val}: {val_formatted}")
            else:
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
        eid = engine.engine_id
        pattern = task.analytical_pattern
        grain = task.time_granularity

        # Step 0: Wren AI MDL Semantic Compiler (Deterministic & Graph-Resolved)
        model = self.semantic_catalog.get_model(eid)
        if model:
            try:
                compiled = SemanticCompiler.compile(task, model)
                if compiled:
                    return compiled
            except Exception as exc:
                print(f"[WARN] Wren SemanticCompiler failed for {eid}: {exc}")

        # --- MULTI-SERIES TIME SERIES PATTERN ---
        if pattern == AnalyticalPattern.MULTI_SERIES_TIME_SERIES:
            time_expr = "DATE(o.orderDate)" if grain == TimeGranularity.DAILY else (
                "strftime('%Y-W%W', o.orderDate)" if grain == TimeGranularity.WEEKLY else "strftime('%Y-%m', o.orderDate)"
            )
            time_alias = task.time_dimension or ("Fecha" if grain == TimeGranularity.DAILY else ("Semana" if grain == TimeGranularity.WEEKLY else "Mes"))
            series_dim = task.series_dimension or "Categoria"

            if eid == "northwind":
                if task.top_n:
                    top_limit = task.top_n
                    if series_dim == "Empleado":
                        return (
                            f"WITH top_employees AS (\n"
                            f"    SELECT e.employeeID, e.lastName || ', ' || e.firstName AS Empleado\n"
                            f"    FROM employees e\n"
                            f"    JOIN orders o ON e.employeeID = o.employeeID\n"
                            f"    JOIN order_details od ON o.orderID = od.orderID\n"
                            f"    GROUP BY e.employeeID, Empleado\n"
                            f"    ORDER BY SUM(od.unitPrice * od.quantity * (1 - od.discount)) DESC\n"
                            f"    LIMIT {top_limit}\n"
                            f")\n"
                            f"SELECT {time_expr} AS {time_alias}, "
                            f"te.Empleado AS Empleado, "
                            f"ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD "
                            f"FROM orders o "
                            f"JOIN order_details od ON o.orderID = od.orderID "
                            f"JOIN top_employees te ON o.employeeID = te.employeeID "
                            f"GROUP BY {time_alias}, Empleado "
                            f"ORDER BY {time_alias} ASC, Ventas_USD DESC;"
                        )
                    else:
                        return (
                            f"WITH top_categories AS (\n"
                            f"    SELECT c.categoryID, c.categoryName\n"
                            f"    FROM categories c\n"
                            f"    JOIN products p ON c.categoryID = p.categoryID\n"
                            f"    JOIN order_details od ON p.productID = od.productID\n"
                            f"    GROUP BY c.categoryID, c.categoryName\n"
                            f"    ORDER BY SUM(od.unitPrice * od.quantity * (1 - od.discount)) DESC\n"
                            f"    LIMIT {top_limit}\n"
                            f")\n"
                            f"SELECT {time_expr} AS {time_alias}, "
                            f"tc.categoryName AS Categoria, "
                            f"ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD "
                            f"FROM orders o "
                            f"JOIN order_details od ON o.orderID = od.orderID "
                            f"JOIN products p ON od.productID = p.productID "
                            f"JOIN top_categories tc ON p.categoryID = tc.categoryID "
                            f"GROUP BY {time_alias}, Categoria "
                            f"ORDER BY {time_alias} ASC, Ventas_USD DESC;"
                        )
                if series_dim == "Empleado":
                    return (
                        f"SELECT {time_expr} AS {time_alias}, "
                        f"e.lastName || ', ' || e.firstName AS Empleado, "
                        f"ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD "
                        f"FROM orders o "
                        f"JOIN order_details od ON o.orderID = od.orderID "
                        f"JOIN employees e ON o.employeeID = e.employeeID "
                        f"GROUP BY {time_alias}, Empleado "
                        f"ORDER BY {time_alias} ASC, Ventas_USD DESC "
                        f"LIMIT 100;"
                    )
                else:
                    return (
                        f"SELECT {time_expr} AS {time_alias}, "
                        f"c.categoryName AS Categoria, "
                        f"ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD "
                        f"FROM orders o "
                        f"JOIN order_details od ON o.orderID = od.orderID "
                        f"JOIN products p ON od.productID = p.productID "
                        f"JOIN categories c ON p.categoryID = c.categoryID "
                        f"GROUP BY {time_alias}, Categoria "
                        f"ORDER BY {time_alias} ASC, Ventas_USD DESC "
                        f"LIMIT 100;"
                    )

            elif eid == "chinook":
                time_expr_ch = "DATE(i.InvoiceDate)" if grain == TimeGranularity.DAILY else (
                    "strftime('%Y-W%W', i.InvoiceDate)" if grain == TimeGranularity.WEEKLY else "strftime('%Y-%m', i.InvoiceDate)"
                )
                time_alias_ch = task.time_dimension or ("Fecha" if grain == TimeGranularity.DAILY else ("Semana" if grain == TimeGranularity.WEEKLY else "Mes"))
                if task.top_n:
                    top_limit = task.top_n
                    return (
                        f"WITH top_genres AS (\n"
                        f"    SELECT g.GenreId, g.Name AS Genero\n"
                        f"    FROM Genre g\n"
                        f"    JOIN Track t ON g.GenreId = t.GenreId\n"
                        f"    JOIN InvoiceLine il ON t.TrackId = il.TrackId\n"
                        f"    GROUP BY g.GenreId, Genero\n"
                        f"    ORDER BY SUM(il.UnitPrice * il.Quantity) DESC\n"
                        f"    LIMIT {top_limit}\n"
                        f")\n"
                        f"SELECT {time_expr_ch} AS {time_alias_ch}, "
                        f"tg.Genero AS Genero, "
                        f"ROUND(SUM(il.UnitPrice * il.Quantity), 2) AS Facturacion_USD "
                        f"FROM Invoice i "
                        f"JOIN InvoiceLine il ON i.InvoiceId = il.InvoiceId "
                        f"JOIN Track t ON il.TrackId = t.TrackId "
                        f"JOIN top_genres tg ON t.GenreId = tg.GenreId "
                        f"GROUP BY {time_alias_ch}, Genero "
                        f"ORDER BY {time_alias_ch} ASC, Facturacion_USD DESC;"
                    )
                return (
                    f"SELECT {time_expr_ch} AS {time_alias_ch}, "
                    f"g.Name AS Genero, "
                    f"ROUND(SUM(il.UnitPrice * il.Quantity), 2) AS Facturacion_USD "
                    f"FROM Invoice i "
                    f"JOIN InvoiceLine il ON i.InvoiceId = il.InvoiceId "
                    f"JOIN Track t ON il.TrackId = t.TrackId "
                    f"JOIN Genre g ON t.GenreId = g.GenreId "
                    f"GROUP BY {time_alias_ch}, Genero "
                    f"ORDER BY {time_alias_ch} ASC, Facturacion_USD DESC "
                    f"LIMIT 100;"
                )

        # --- TIME SERIES (MONO-SERIE) PATTERN ---
        if pattern == AnalyticalPattern.TIME_SERIES:
            if eid == "northwind":
                if grain == TimeGranularity.DAILY:
                    return (
                        "SELECT DATE(o.orderDate) AS Fecha, "
                        "ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD "
                        "FROM orders o "
                        "JOIN order_details od ON o.orderID = od.orderID "
                        "GROUP BY Fecha "
                        "ORDER BY Fecha ASC "
                        "LIMIT 30;"
                    )
                elif grain == TimeGranularity.WEEKLY:
                    return (
                        "SELECT strftime('%Y-W%W', o.orderDate) AS Semana, "
                        "ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD "
                        "FROM orders o "
                        "JOIN order_details od ON o.orderID = od.orderID "
                        "GROUP BY Semana "
                        "ORDER BY Semana ASC "
                        "LIMIT 20;"
                    )
                return (
                    "SELECT strftime('%Y-%m', o.orderDate) AS Mes, "
                    "ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD "
                    "FROM orders o "
                    "JOIN order_details od ON o.orderID = od.orderID "
                    "GROUP BY Mes "
                    "ORDER BY Mes ASC "
                    "LIMIT 24;"
                )
            elif eid == "chinook":
                if grain == TimeGranularity.WEEKLY:
                    return (
                        "SELECT strftime('%Y-W%W', i.InvoiceDate) AS Semana, "
                        "ROUND(SUM(i.Total), 2) AS Facturacion_USD "
                        "FROM Invoice i "
                        "GROUP BY Semana "
                        "ORDER BY Semana ASC "
                        "LIMIT 20;"
                    )
                return (
                    "SELECT strftime('%Y-%m', i.InvoiceDate) AS Mes, "
                    "ROUND(SUM(i.Total), 2) AS Facturacion_USD "
                    "FROM Invoice i "
                    "GROUP BY Mes "
                    "ORDER BY Mes ASC "
                    "LIMIT 24;"
                )
            elif eid == "sakila":
                return (
                    "SELECT strftime('%Y-%m', p.payment_date) AS Mes, "
                    "ROUND(SUM(p.amount), 2) AS Ingresos_USD "
                    "FROM payment p "
                    "GROUP BY Mes "
                    "ORDER BY Mes ASC "
                    "LIMIT 24;"
                )
            elif eid == "tpch":
                return (
                    "SELECT strftime('%Y-%m', o.o_orderdate) AS Mes, "
                    "ROUND(SUM(o.o_totalprice), 2) AS Monto_USD "
                    "FROM orders o "
                    "GROUP BY Mes "
                    "ORDER BY Mes ASC "
                    "LIMIT 24;"
                )

        # --- GEO DISTRIBUTION PATTERN ---
        if pattern == AnalyticalPattern.GEO_DISTRIBUTION:
            limit_geo = task.top_n if task.top_n else 10
            if eid == "northwind":
                return f"SELECT country AS Pais, COUNT(customerID) AS Clientes FROM customers GROUP BY country ORDER BY Clientes DESC LIMIT {limit_geo};"
            elif eid == "chinook":
                return f"SELECT BillingCountry AS Pais, ROUND(SUM(Total), 2) AS Facturacion_USD FROM Invoice GROUP BY BillingCountry ORDER BY Facturacion_USD DESC LIMIT {limit_geo};"
            elif eid == "tpch":
                return f"SELECT n.n_name AS Pais, COUNT(c.c_custkey) AS Clientes FROM customer c JOIN nation n ON c.c_nationkey = n.n_nationkey GROUP BY Pais ORDER BY Clientes DESC LIMIT {limit_geo};"

        # --- RANKINGS & CATEGORIES ---
        lowered = task.goal.lower()
        limit_val = task.top_n if task.top_n else 10
        order_dir = "ASC" if task.ranking_criterion == "menor desempeño" else "DESC"

        if eid == "northwind":
            if "empleado" in lowered or "Empleado" in task.dimensions:
                return (
                    'SELECT e.lastName || ", " || e.firstName AS Empleado, '
                    'ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD '
                    'FROM orders o '
                    'JOIN employees e ON o.employeeID = e.employeeID '
                    'JOIN order_details od ON o.orderID = od.orderID '
                    f'GROUP BY Empleado ORDER BY Ventas_USD {order_dir} LIMIT {limit_val};'
                )
            if "cliente" in lowered or "Cliente" in task.dimensions:
                return f"SELECT country AS Pais, COUNT(customerID) AS Clientes FROM customers GROUP BY country ORDER BY Clientes {order_dir} LIMIT {limit_val};"
            if "producto" in lowered or "Producto" in task.dimensions:
                return (
                    'SELECT p.productName AS Producto, ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD '
                    'FROM products p '
                    'JOIN order_details od ON p.productID = od.productID '
                    f'GROUP BY Producto ORDER BY Ventas_USD {order_dir} LIMIT {limit_val};'
                )
            return (
                'SELECT c.categoryName AS Categoria, ROUND(SUM(od.unitPrice * od.quantity * (1 - od.discount)), 2) AS Ventas_USD '
                'FROM categories c '
                'JOIN products p ON c.categoryID = p.categoryID '
                'JOIN order_details od ON p.productID = od.productID '
                f'GROUP BY Categoria ORDER BY Ventas_USD {order_dir} LIMIT {limit_val};'
            )

        if eid == "chinook":
            if "artista" in lowered or "cancion" in lowered or "track" in lowered or "Artista" in task.dimensions:
                return (
                    "SELECT ar.Name AS Artista, COUNT(t.TrackId) AS Canciones "
                    "FROM Artist ar "
                    "JOIN Album al ON ar.ArtistId = al.ArtistId "
                    "JOIN Track t ON al.AlbumId = t.AlbumId "
                    f"GROUP BY Artista ORDER BY Canciones {order_dir} LIMIT {limit_val};"
                )
            if "genero" in lowered or "genre" in lowered or "Genero" in task.dimensions:
                return (
                    "SELECT g.Name AS Genero, COUNT(t.TrackId) AS Canciones "
                    "FROM Genre g "
                    "JOIN Track t ON g.GenreId = t.GenreId "
                    f"GROUP BY Genero ORDER BY Canciones {order_dir} LIMIT {limit_val};"
                )
            return (
                f"SELECT c.Country AS Pais, ROUND(SUM(i.Total), 2) AS Facturacion_USD "
                f"FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId "
                f"GROUP BY Pais ORDER BY Facturacion_USD {order_dir} LIMIT {limit_val};"
            )

        if eid == "sakila":
            if "actor" in lowered or "actores" in lowered or "Actor" in task.dimensions:
                return (
                    "SELECT a.first_name || ' ' || a.last_name AS Actor, COUNT(fa.film_id) AS Peliculas "
                    "FROM actor a JOIN film_actor fa ON a.actor_id = fa.actor_id "
                    f"GROUP BY Actor ORDER BY Peliculas {order_dir} LIMIT {limit_val};"
                )
            return (
                "SELECT c.name AS Categoria, COUNT(fc.film_id) AS Peliculas "
                "FROM category c JOIN film_category fc ON c.category_id = fc.category_id "
                f"GROUP BY Categoria ORDER BY Peliculas {order_dir} LIMIT {limit_val};"
            )

        if eid == "tpch":
            return (
                f"SELECT n.n_name AS Pais, COUNT(c.c_custkey) AS Clientes "
                f"FROM customer c JOIN nation n ON c.c_nationkey = n.n_nationkey "
                f"GROUP BY Pais ORDER BY Clientes {order_dir} LIMIT {limit_val};"
            )

        first_table = list(schema.keys())[0] if schema else "sqlite_master"
        return f"SELECT * FROM {first_table} LIMIT 10;"
