"""Kratos Wren-Style Semantic Compiler.

Compiles high-level DataTask contracts into deterministic, schema-grounded SQL
using the SemanticModelMDL relationship graph and pre-approved metric definitions.
"""

from kratos.contracts.schemas import DataTask, AnalyticalPattern, TimeGranularity
from kratos.semantics.mdl import SemanticModelMDL, DimensionMDL, MetricMDL


class SemanticCompiler:
    """Compiles DataTask contracts into mathematically sound SQL using MDL models."""

    @classmethod
    def compile(cls, task: DataTask, model: SemanticModelMDL) -> str:
        """Main entry point: compiles a DataTask into SQL for the specified model."""
        pattern = task.analytical_pattern
        grain = task.time_granularity
        top_n = task.top_n
        order_dir = "ASC" if task.ranking_criterion == "menor desempeño" else "DESC"
        limit_val = top_n if top_n else 10

        # 1. Resolve Primary Metric
        metric = None
        if task.metrics:
            metric = model.get_metric(task.metrics[0])
        if not metric:
            metric = model.find_metric_by_synonym(task.goal)
        if not metric and model.metrics:
            metric = model.metrics[0]

        # 2. Resolve Primary Dimension(s)
        primary_dim = None
        if task.dimensions:
            for d_name in task.dimensions:
                d_cand = model.get_dimension(d_name)
                if d_cand and d_cand.type != "temporal":
                    primary_dim = d_cand
                    break
        if not primary_dim:
            primary_dim = model.find_dimension_by_synonym(task.goal)
        if not primary_dim and model.dimensions:
            primary_dim = model.dimensions[0]

        # 3. Resolve Temporal Dimension
        time_dim = model.get_dimension("Fecha")
        if not time_dim:
            for d in model.dimensions:
                if d.type == "temporal":
                    time_dim = d
                    break

        # 4. Resolve Temporal Year Filter Clause (e.g. "en 1997")
        year_filter_clause = None
        if time_dim and task.filter_year:
            time_col_ref = f"{time_dim.table}.{time_dim.column or 'orderDate'}"
            year_filter_clause = f"strftime('%Y', {time_col_ref}) = '{task.filter_year}'"

        # =========================================================================
        # PATTERN A: MULTI-SERIES TIME SERIES (with or without Top-N CTE)
        # =========================================================================
        if pattern == AnalyticalPattern.MULTI_SERIES_TIME_SERIES and time_dim and primary_dim and metric:
            time_expr, time_alias = cls._build_time_expr(time_dim, grain, task.time_dimension)
            s_alias = primary_dim.id
            s_expr = primary_dim.select_expression

            # Case A1: Multi-series with Top N / Bottom N Cohort CTE
            if top_n:
                cohort_tables = {primary_dim.table, metric.table}
                if metric.required_tables:
                    cohort_tables.update(metric.required_tables)
                if year_filter_clause:
                    cohort_tables.add(time_dim.table)
                cohort_joins = cls._build_joins(cohort_tables, model, base_table=primary_dim.table)
                cohort_join_sql = " ".join([f"JOIN {r.to_table} ON {r.on_clause}" for r in cohort_joins])
                from_cohort = f"FROM {primary_dim.table} {cohort_join_sql}".strip()
                where_cohort = f"WHERE {year_filter_clause}" if year_filter_clause else ""

                # Must include primary_dim.table so fact table traversal path (e.g. orders -> order_details -> products -> categories) is complete
                fact_tables = {time_dim.table, metric.table, primary_dim.table}
                if metric.required_tables:
                    fact_tables.update(metric.required_tables)
                fact_joins = cls._build_joins(fact_tables, model, base_table=time_dim.table)
                fact_join_sql = " ".join([f"JOIN {r.to_table} ON {r.on_clause}" for r in fact_joins])
                from_fact = f"FROM {time_dim.table} {fact_join_sql}".strip()
                where_fact = f"WHERE {year_filter_clause}" if year_filter_clause else ""

                is_lowest = order_dir == "ASC"
                cohort_label = f"Bottom {top_n} (menor desempeño)" if is_lowest else f"Top {top_n} (mejor desempeño)"
                cte_table_name = f"{'bottom' if is_lowest else 'top'}_{primary_dim.table}"

                return (
                    f"/* =========================================================================\n"
                    f"   KRATOS ANALYTICAL QUERY // Motor: {model.engine_id}\n"
                    f"   Objetivo: {task.goal}\n"
                    f"   Patrón: Multi-Series Time Series con Cohorte {cohort_label}\n"
                    f"   Capa Semántica: Wren AI MDL ({model.name})\n"
                    f"   ========================================================================= */\n"
                    f"-- Paso 1: Filtrar la cohorte {cohort_label} por volumen histórico total ({order_dir})\n"
                    f"WITH {cte_table_name} AS (\n"
                    f"    SELECT {s_expr} AS {s_alias} -- Entidad líder/segmento\n"
                    f"    {from_cohort}\n"
                    f"    {where_cohort}\n"
                    f"    GROUP BY {s_alias}\n"
                    f"    ORDER BY {metric.expression} {order_dir}\n"
                    f"    LIMIT {top_n}\n"
                    f")\n"
                    f"-- Paso 2: Desglose cronológico ({grain.value}) únicamente para la cohorte seleccionada\n"
                    f"SELECT {time_expr} AS {time_alias}, -- Eje temporal\n"
                    f"       tc.{s_alias} AS {s_alias}, -- Segmento de la cohorte {cohort_label}\n"
                    f"       {metric.expression} AS {metric.id} -- Métrica analítica calculada ({metric.unit})\n"
                    f"{from_fact}\n"
                    f"JOIN {cte_table_name} tc ON {s_expr} = tc.{s_alias}\n"
                    f"{where_fact}\n"
                    f"GROUP BY {time_alias}, {s_alias}\n"
                    f"ORDER BY {time_alias} ASC, {metric.id} DESC\n"
                    f"LIMIT 500;"
                )

            # Case A2: Standard Multi-series
            req_tables = {time_dim.table, primary_dim.table, metric.table}
            if metric.required_tables:
                req_tables.update(metric.required_tables)
            joins = cls._build_joins(req_tables, model, base_table=time_dim.table)
            join_sql = " ".join([f"JOIN {r.to_table} ON {r.on_clause}" for r in joins])
            where_fact = f"WHERE {year_filter_clause}" if year_filter_clause else ""
            return (
                f"/* =========================================================================\n"
                f"   KRATOS ANALYTICAL QUERY // Motor: {model.engine_id}\n"
                f"   Objetivo: {task.goal}\n"
                f"   Patrón: Multi-Series Time Series ({grain.value})\n"
                f"   Capa Semántica: Wren AI MDL ({model.name})\n"
                f"   ========================================================================= */\n"
                f"SELECT {time_expr} AS {time_alias}, -- Dimensión temporal ({grain.value})\n"
                f"       {s_expr} AS {s_alias}, -- Segmento analítico\n"
                f"       {metric.expression} AS {metric.id} -- Métrica calculada ({metric.unit})\n"
                f"FROM {time_dim.table} {join_sql}\n"
                f"{where_fact}\n"
                f"GROUP BY {time_alias}, {s_alias}\n"
                f"ORDER BY {time_alias} ASC, {metric.id} DESC\n"
                f"LIMIT 500;"
            )

        # =========================================================================
        # PATTERN A3: PARTITIONED RANKING (Top N per time partition via Window Function)
        # =========================================================================
        if pattern == AnalyticalPattern.PARTITIONED_RANKING and time_dim and primary_dim and metric:
            time_expr, time_alias = cls._build_time_expr(time_dim, grain, task.time_dimension)
            s_alias = primary_dim.id
            s_expr = primary_dim.select_expression
            limit_n = top_n or 10

            fact_tables = {time_dim.table, metric.table, primary_dim.table}
            if metric.required_tables:
                fact_tables.update(metric.required_tables)
            fact_joins = cls._build_joins(fact_tables, model, base_table=time_dim.table)
            fact_join_sql = " ".join([f"JOIN {r.to_table} ON {r.on_clause}" for r in fact_joins])
            from_fact = f"FROM {time_dim.table} {fact_join_sql}".strip()
            where_fact = f"WHERE {year_filter_clause}" if year_filter_clause else ""

            is_lowest = order_dir == "ASC"
            rank_label = f"Bottom {limit_n} por período ({time_alias})" if is_lowest else f"Top {limit_n} por período ({time_alias})"

            return (
                f"/* =========================================================================\n"
                f"   KRATOS ANALYTICAL QUERY // Motor: {model.engine_id}\n"
                f"   Objetivo: {task.goal}\n"
                f"   Patrón: Ranking Particionado con Window Function ({rank_label})\n"
                f"   Capa Semántica: Wren AI MDL ({model.name})\n"
                f"   ========================================================================= */\n"
                f"-- Paso 1: Particionar y clasificar filas por {time_alias} usando ROW_NUMBER()\n"
                f"WITH RankedPartition AS (\n"
                f"    SELECT {time_expr} AS {time_alias}, -- Eje de partición temporal\n"
                f"           {s_expr} AS {s_alias}, -- Entidad analítica clasificada\n"
                f"           {metric.expression} AS {metric.id}, -- Métrica de rendimiento ({metric.unit})\n"
                f"           ROW_NUMBER() OVER (\n"
                f"               PARTITION BY {time_expr}\n"
                f"               ORDER BY {metric.expression} {order_dir}\n"
                f"           ) AS rnk\n"
                f"    {from_fact}\n"
                f"    {where_fact}\n"
                f"    GROUP BY {time_alias}, {s_alias}\n"
                f")\n"
                f"-- Paso 2: Filtrar la élite de cada partición ({rank_label})\n"
                f"SELECT {time_alias},\n"
                f"       {s_alias},\n"
                f"       {metric.id}\n"
                f"FROM RankedPartition\n"
                f"WHERE rnk <= {limit_n}\n"
                f"ORDER BY {time_alias} ASC, {metric.id} DESC\n"
                f"LIMIT 500;"
            )

        # =========================================================================
        # PATTERN A4: GEO PARTITIONED RANKING (Top N per geographic partition via Window Function)
        # =========================================================================
        if pattern == AnalyticalPattern.GEO_PARTITIONED_RANKING and metric:
            geo_dim = None
            cat_dim = None
            for d_name in (task.dimensions or []):
                d = model.get_dimension(d_name)
                if not d:
                    continue
                if d.type == "geo" or any(w in d.id.lower() for w in ["pais", "país", "country", "nation", "nacion", "nación", "region", "región"]) or \
                   any(w in (d.column or "").lower() for w in ["country", "nation", "pais", "region"]):
                    geo_dim = d
                else:
                    cat_dim = d

            if not geo_dim:
                for d in model.dimensions:
                    if d.type == "geo" or any(w in d.id.lower() for w in ["pais", "país", "country", "nation"]):
                        geo_dim = d
                        break

            if not cat_dim:
                for d in model.dimensions:
                    if d.type != "temporal" and d != geo_dim:
                        cat_dim = d
                        break

            if geo_dim and cat_dim:
                geo_alias = geo_dim.id
                geo_expr = geo_dim.select_expression
                cat_alias = cat_dim.id
                cat_expr = cat_dim.select_expression
                limit_n = top_n or 1

                fact_tables = {geo_dim.table, cat_dim.table, metric.table}
                if metric.required_tables:
                    fact_tables.update(metric.required_tables)
                if year_filter_clause and time_dim:
                    fact_tables.add(time_dim.table)
                fact_joins = cls._build_joins(fact_tables, model, base_table=geo_dim.table)
                fact_join_sql = " ".join([f"JOIN {r.to_table} ON {r.on_clause}" for r in fact_joins])
                from_fact = f"FROM {geo_dim.table} {fact_join_sql}".strip()
                where_fact = f"WHERE {year_filter_clause}" if year_filter_clause else ""

                is_lowest = order_dir == "ASC"
                rank_label = f"Bottom {limit_n} {cat_alias} por {geo_alias}" if is_lowest else f"Top {limit_n} {cat_alias} por {geo_alias}"

                return (
                    f"/* =========================================================================\n"
                    f"   KRATOS ANALYTICAL QUERY // Motor: {model.engine_id}\n"
                    f"   Objetivo: {task.goal}\n"
                    f"   Patrón: Ranking Geo-Particionado con Window Function ({rank_label})\n"
                    f"   Capa Semántica: Wren AI MDL ({model.name})\n"
                    f"   ========================================================================= */\n"
                    f"-- Paso 1: Particionar métricas por {geo_alias} y clasificar {cat_alias} con ROW_NUMBER()\n"
                    f"WITH RankedGeoPartition AS (\n"
                    f"    SELECT {geo_expr} AS {geo_alias}, -- Dimensión geográfica\n"
                    f"           {cat_expr} AS {cat_alias}, -- Dimensión categórica clasificada\n"
                    f"           {metric.expression} AS {metric.id}, -- Métrica de volumen ({metric.unit})\n"
                    f"           ROW_NUMBER() OVER (\n"
                    f"               PARTITION BY {geo_expr}\n"
                    f"               ORDER BY {metric.expression} {order_dir}\n"
                    f"           ) AS rnk\n"
                    f"    {from_fact}\n"
                    f"    {where_fact}\n"
                    f"    GROUP BY {geo_alias}, {cat_alias}\n"
                    f")\n"
                    f"-- Paso 2: Filtrar la categoría líder de cada territorio ({rank_label})\n"
                    f"SELECT {geo_alias},\n"
                    f"       {cat_alias},\n"
                    f"       {metric.id}\n"
                    f"FROM RankedGeoPartition\n"
                    f"WHERE rnk <= {limit_n}\n"
                    f"ORDER BY {metric.id} DESC\n"
                    f"LIMIT 500;"
                )

        # =========================================================================
        # PATTERN B: TIME SERIES (Mono-serie)
        # =========================================================================
        if pattern == AnalyticalPattern.TIME_SERIES and time_dim and metric:
            time_expr, time_alias = cls._build_time_expr(time_dim, grain, task.time_dimension)
            req_tables = {time_dim.table, metric.table}
            if metric.required_tables:
                req_tables.update(metric.required_tables)
            joins = cls._build_joins(req_tables, model, base_table=time_dim.table)
            join_sql = " ".join([f"JOIN {r.to_table} ON {r.on_clause}" for r in joins])
            from_clause = f"FROM {time_dim.table} {join_sql}".strip()
            where_clause = f"WHERE {year_filter_clause}" if year_filter_clause else ""

            return (
                f"/* =========================================================================\n"
                f"   KRATOS ANALYTICAL QUERY // Motor: {model.engine_id}\n"
                f"   Objetivo: {task.goal}\n"
                f"   Patrón: Time Series Mono-serie ({grain.value})\n"
                f"   Capa Semántica: Wren AI MDL ({model.name})\n"
                f"   ========================================================================= */\n"
                f"SELECT {time_expr} AS {time_alias}, -- Eje cronológico\n"
                f"       {metric.expression} AS {metric.id} -- Métrica acumulada ({metric.unit})\n"
                f"{from_clause}\n"
                f"{where_clause}\n"
                f"GROUP BY {time_alias}\n"
                f"ORDER BY {time_alias} ASC\n"
                f"LIMIT 30;"
            )

        # =========================================================================
        # PATTERN C: RANKING TOP N or CATEGORICAL BREAKDOWN or GEO
        # =========================================================================
        if primary_dim and metric:
            req_tables = {primary_dim.table, metric.table}
            if metric.required_tables:
                req_tables.update(metric.required_tables)
            if year_filter_clause and time_dim:
                req_tables.add(time_dim.table)
            joins = cls._build_joins(req_tables, model, base_table=primary_dim.table)
            join_sql = " ".join([f"JOIN {r.to_table} ON {r.on_clause}" for r in joins])
            from_clause = f"FROM {primary_dim.table} {join_sql}".strip()

            where_conditions = []
            if year_filter_clause:
                where_conditions.append(year_filter_clause)
            if primary_dim.column and primary_dim.column.lower() in ["region", "shipregion", "billingstate"]:
                where_conditions.append(f"{primary_dim.table}.{primary_dim.column} IS NOT NULL")

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            rank_title = f"Top {limit_val}" if top_n else "Distribución Categórica"
            return (
                f"/* =========================================================================\n"
                f"   KRATOS ANALYTICAL QUERY // Motor: {model.engine_id}\n"
                f"   Objetivo: {task.goal}\n"
                f"   Patrón: {rank_title} ({order_dir})\n"
                f"   Capa Semántica: Wren AI MDL ({model.name})\n"
                f"   ========================================================================= */\n"
                f"SELECT {primary_dim.select_expression} AS {primary_dim.id}, -- Dimensión analítica canónica\n"
                f"       {metric.expression} AS {metric.id} -- Métrica formal de negocio ({metric.unit})\n"
                f"{from_clause}\n"
                f"{where_clause}\n"
                f"GROUP BY {primary_dim.id}\n"
                f"ORDER BY {metric.id} {order_dir}\n"
                f"LIMIT {limit_val};"
            )

        # Fallback safe select
        first_table = model.dimensions[0].table if model.dimensions else "sqlite_master"
        return f"SELECT * FROM {first_table} LIMIT 10;"

    @classmethod
    def _build_time_expr(cls, time_dim: DimensionMDL, grain: TimeGranularity, alias_override: str | None) -> tuple[str, str]:
        col_ref = f"{time_dim.table}.{time_dim.column or 'orderDate'}"
        if grain == TimeGranularity.DAILY:
            return f"DATE({col_ref})", alias_override or "Fecha"
        elif grain == TimeGranularity.WEEKLY:
            return f"strftime('%Y-W%W', {col_ref})", alias_override or "Semana"
        elif grain == TimeGranularity.QUARTERLY:
            return f"(strftime('%Y', {col_ref}) || '-Q' || ((CAST(strftime('%m', {col_ref}) AS INTEGER) + 2) / 3))", alias_override or "Trimestre"
        elif grain == TimeGranularity.YEARLY:
            return f"strftime('%Y', {col_ref})", alias_override or "Ano"
        else:
            return f"strftime('%Y-%m', {col_ref})", alias_override or "Mes"

    @classmethod
    def _build_joins(cls, req_tables: set[str], model: SemanticModelMDL, base_table: str) -> list[Any]:
        return model.resolve_join_tree(req_tables, primary_table=base_table)
