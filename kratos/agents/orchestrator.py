"""Kratos Two-Agent System: Interpreter & Investigator with Auto-Reflection."""

import os
import re
from collections import Counter
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
from kratos.analytics.statistics import analyze_distribution, analyze_time_series, analyze_partitioned_ranking
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

        # 2. Time-series & Temporal Grain Detection (word-boundary safe)
        is_time_series = bool(re.search(
            r"\b(tendencia|tiempo|semanal|semanales|semana|semanas|mensual|mensuales|mes|meses|trimestral|trimestrales|trimestre|trimestres|quarter|quarterly|anual|anuales|año|ano|años|anos|year|yearly|diario|diarios|dia|día|dias|días|diaria|diarias|evolucion|evolución|historico|histórico|a través del tiempo|traves del tiempo)\b",
            lowered
        ))

        time_granularity = TimeGranularity.NONE
        time_dimension = None

        # Temporal Year Filter Detection (e.g. "en 1997", "del 1998", "año 2012")
        year_match = re.search(r"\b(?:en\s+(?:el\s+)?(?:año\s+)?|del\s+(?:año\s+)?|año\s+)?(19\d\d|20\d\d)\b", lowered)
        filter_year = int(year_match.group(1)) if year_match else None

        if is_time_series:
            if re.search(r"\b(diario|diarios|diaria|diarias|dia|día|dias|días|daily)\b", lowered):
                time_granularity = TimeGranularity.DAILY
                time_dimension = "Fecha"
            elif re.search(r"\b(semanal|semanales|semana|semanas|week|weekly)\b", lowered):
                time_granularity = TimeGranularity.WEEKLY
                time_dimension = "Semana"
            elif re.search(r"\b(trimestral|trimestrales|trimestre|trimestres|quarter|quarterly|q1|q2|q3|q4)\b", lowered):
                time_granularity = TimeGranularity.QUARTERLY
                time_dimension = "Trimestre"
            elif re.search(r"\b(anual|anuales|año|ano|años|anos|year|yearly|anualmente)\b", lowered):
                time_granularity = TimeGranularity.YEARLY
                time_dimension = "Ano"
            elif re.search(r"\b(mensual|mensuales|mes|meses|month|monthly|mensualmente)\b", lowered):
                time_granularity = TimeGranularity.MONTHLY
                time_dimension = "Mes"
            else:
                time_granularity = TimeGranularity.DAILY if "diar" in lowered else TimeGranularity.MONTHLY
                time_dimension = "Fecha" if time_granularity == TimeGranularity.DAILY else "Mes"

        # 3. Model-Driven Semantic Dimension Detection (Multi-dimensional aware)
        model = self.semantic_catalog.get_model(active_engine_id)
        ontology_constraints: list[str] = []
        if model:
            from kratos.ontology.grounder import AutoOntologyGrounder
            ans_check = AutoOntologyGrounder.check_answerable(query, model)
            if not ans_check.is_answerable:
                ontology_constraints.append(f"OUT_OF_SCOPE: {ans_check.reason}")

        matched_dims = model.find_all_non_temporal_dimensions(query) if model else []

        geo_dim = next((d for d in matched_dims if d.type == "geo" or d.id in ["Pais", "Region"]), None)
        cat_dim = next((d for d in matched_dims if d.type != "geo" and d.id not in ["Pais", "Region"]), None)

        # Fallback keyword matching across standard entities if not found in model
        if not cat_dim:
            if any(w in lowered for w in ["categoria", "categoría", "categorias", "categorías", "lineas", "líneas"]):
                cat_dim = model.get_dimension("Categoria") if model else None
            elif any(w in lowered for w in ["producto", "productos", "articulo", "artículos", "articulos", "item", "items", "mercancía"]):
                cat_dim = model.get_dimension("Producto") if model else None
            elif any(w in lowered for w in ["album", "álbum", "albumes", "álbumes", "disco", "discos"]):
                cat_dim = model.get_dimension("Album") if model else None
            elif any(w in lowered for w in ["cancion", "canción", "canciones", "track", "tracks"]):
                cat_dim = model.get_dimension("Cancion") if model else None
            elif any(w in lowered for w in ["empleado", "empleados", "vendedor", "vendedores"]):
                cat_dim = model.get_dimension("Empleado") if model else None
            elif any(w in lowered for w in ["cliente", "clientes", "comprador", "compradores"]):
                cat_dim = model.get_dimension("Cliente") if model else None
            elif any(w in lowered for w in ["genero", "género", "generos", "géneros"]):
                cat_dim = model.get_dimension("Genero") if model else None
            elif any(w in lowered for w in ["artista", "artistas", "banda", "bandas"]):
                cat_dim = model.get_dimension("Artista") if model else None

        if not geo_dim:
            if any(w in lowered for w in ["pais", "país", "paises", "países", "region", "región", "regiones", "territorios", "territorio", "destino"]):
                geo_dim = (model.get_dimension("Pais") if model else None) or (model.get_dimension("Region") if model else None)

        series_dimension = cat_dim.id if cat_dim else (geo_dim.id if geo_dim else None)

        # 4. Top-N and Ranking Extraction
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

        if any(w in lowered for w in ["mejor desempeño", "mejores desempeños", "mejor rendimiento", "más ventas", "mas ventas", "mayores ventas", "mas vendidos", "más vendidos", "mejores", "mejor"]):
            ranking_criterion = "mejor desempeño"
        elif any(w in lowered for w in ["peor desempeño", "menos ventas", "menores ventas", "menos vendidos", "peores", "peor"]):
            ranking_criterion = "menor desempeño"

        # Check for Geographic Partitioned Ranking (e.g. "géneros más vendidos por país", "top productos por región")
        is_geo_partition = bool(
            geo_dim and cat_dim and any(w in lowered for w in [
                "por pais", "por país", "por region", "por región", "por territorio", "en cada pais", "en cada país",
                "en cada region", "en cada región", "cada pais", "cada país", "más vendidos por", "mas vendidos por",
                "más vendido por", "mas vendido por", "se venden mas por", "se venden más por", "líder por", "lider por", "dominante por"
            ])
        )

        # 5. Analytical Pattern Detection
        if is_geo_partition:
            analytical_pattern = AnalyticalPattern.GEO_PARTITIONED_RANKING
            top_n = top_n or 1 # Default to dominant category per territory
        elif is_time_series and series_dimension and top_n:
            is_cohort_trend = any(w in lowered for w in [
                "a través del tiempo", "traves del tiempo", "tendencia", "historico", "histórico", "comportamiento", "evolución", "evolucion"
            ])
            if is_cohort_trend:
                analytical_pattern = AnalyticalPattern.MULTI_SERIES_TIME_SERIES
            else:
                analytical_pattern = AnalyticalPattern.PARTITIONED_RANKING
        elif is_time_series and series_dimension:
            analytical_pattern = AnalyticalPattern.MULTI_SERIES_TIME_SERIES
        elif is_time_series:
            analytical_pattern = AnalyticalPattern.TIME_SERIES
        elif top_n is not None or any(w in lowered for w in ["top", "mejores", "mejor", "primeros", "primeras", "ranking", "lideres", "líderes", "lider", "líder", "mas", "más", "peor", "peores"]):
            analytical_pattern = AnalyticalPattern.RANKING_TOP_N
        elif geo_dim or any(w in lowered for w in ["pais", "país", "paises", "países", "ciudad", "ciudades", "region", "región"]):
            analytical_pattern = AnalyticalPattern.GEO_DISTRIBUTION
        else:
            analytical_pattern = AnalyticalPattern.CATEGORICAL_BREAKDOWN

        # 6. Metric Target Detection
        metric_target = MetricTarget.REVENUE
        if any(w in lowered for w in ["pedido", "pedidos", "orden", "ordenes", "órdenes", "orders", "envio", "envíos", "envios", "envío"]):
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

        if analytical_pattern == AnalyticalPattern.GEO_PARTITIONED_RANKING:
            if geo_dim:
                dimensions.append(geo_dim.id)
            if cat_dim:
                dimensions.append(cat_dim.id)
        elif analytical_pattern in [AnalyticalPattern.MULTI_SERIES_TIME_SERIES, AnalyticalPattern.PARTITIONED_RANKING]:
            if time_dimension:
                dimensions.append(time_dimension)
            if series_dimension:
                dimensions.append(series_dimension)
        elif analytical_pattern == AnalyticalPattern.GEO_DISTRIBUTION:
            if geo_dim:
                dimensions.append(geo_dim.id)
            elif series_dimension:
                dimensions.append(series_dimension)
        elif analytical_pattern == AnalyticalPattern.TIME_SERIES:
            if time_dimension:
                dimensions.append(time_dimension)
        else:
            if series_dimension:
                dimensions.append(series_dimension)
            else:
                matched_dim = model.find_dimension_by_synonym(query) if model else None
                if matched_dim:
                    dimensions.append(matched_dim.id)
                elif analytical_pattern == AnalyticalPattern.GEO_DISTRIBUTION or any(w in lowered for w in ["pais", "país", "paises", "países"]):
                    dimensions.append("Pais")
                elif model and model.dimensions:
                    first_dim = next((d.id for d in model.dimensions if d.type != "temporal"), model.dimensions[0].id)
                    dimensions.append(first_dim)
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
            filter_year=filter_year,
            dimensions=dimensions,
            metrics=metrics,
            needs_investigation=len(ontology_constraints) == 0,
            constraints=ontology_constraints,
            required_evidence=["Datos numéricos agregados", "Dimensiones analíticas"],
        )

    def formulate_storytelling(self, task: DataTask, evidence: DataEvidence) -> ExecutiveStorytelling:
        if task.constraints and any(c.startswith("OUT_OF_SCOPE:") for c in task.constraints):
            detail = next(c.replace("OUT_OF_SCOPE: ", "") for c in task.constraints if c.startswith("OUT_OF_SCOPE:"))
            return ExecutiveStorytelling(
                key_takeaway=f"Consulta fuera del alcance ontológico del motor '{task.engine_id}'.",
                diagnostic_metrics={"status": "unanswerable", "engine": task.engine_id},
                quantitative_findings=[detail],
                risk_alerts=["Intento de consulta sobre conceptos no definidos ni soportados en el catálogo ontológico."],
                strategic_recommendations=[
                    "Reformular la consulta utilizando las dimensiones y métricas certificadas disponibles en el catálogo ontológico.",
                    f"Explorar las entidades y métricas del motor '{task.engine_id}' mediante el endpoint /api/ontology/{task.engine_id}."
                ],
            )

        if not evidence.observations:
            return ExecutiveStorytelling(
                key_takeaway=f"No se registraron datos en el motor '{task.engine_id}' para la consulta solicitada.",
                diagnostic_metrics={},
                quantitative_findings=["Registros encontrados: 0"],
                risk_alerts=["Sin datos suficientes para emitir alertas de concentración o riesgo."],
                strategic_recommendations=["Verificar filtros o explorar tablas disponibles en el esquema."],
            )

        rows = evidence.queries[0].rows if evidence.queries else []
        dim_hint = task.dimensions[0] if task.dimensions else None
        met_hint = task.metrics[0] if task.metrics else None

        # -------------------------------------------------------------------------
        # CASE 0: PARTITIONED RANKING (Top N por período temporal con Window Function)
        # -------------------------------------------------------------------------
        if task.analytical_pattern == AnalyticalPattern.PARTITIONED_RANKING and rows:
            part_diag = analyze_partitioned_ranking(
                rows,
                time_hint=task.time_dimension,
                dim_hint=task.series_dimension,
                met_hint=met_hint
            )
            if part_diag and part_diag.partition_leaders:
                time_lbl = part_diag.time_col
                dim_lbl = part_diag.dimension_col
                limit_n = task.top_n or 10
                cohort_prefix = "Bottom" if task.ranking_criterion == "menor desempeño" else "Top"

                leaders_summary = ", ".join([f"{p['period']}: '{p['leader']}' ({format_metric_value(p['value'], part_diag.unit)})" for p in part_diag.partition_leaders[:4]])
                period_leaders_str = ", ".join([f"{p['period']} → {p['leader']}" for p in part_diag.partition_leaders])

                key_takeaway = (
                    f"Ranking Particionado ({cohort_prefix} {limit_n} {dim_lbl} por {time_lbl}): Dinámica competitiva en {part_diag.partitions_count} períodos evaluados. "
                    f"Líderes destacados: {leaders_summary}."
                )

                findings = [
                    f"Volumen acumulado evaluado: {format_metric_value(part_diag.total_volume, part_diag.unit)} a lo largo de {part_diag.partitions_count} cortes temporales de {time_lbl}.",
                    f"Distribución de líderes por período: {period_leaders_str}.",
                ]

                if part_diag.persistent_leaders:
                    findings.append(
                        f"Liderazgo recurrente / Dominancia: {', '.join(part_diag.persistent_leaders)} se mantuvieron en el #1 en múltiples particiones temporales."
                    )
                else:
                    findings.append(
                        f"Alta alternancia competitiva: Ninguna entidad monopolizó el primer puesto en períodos consecutivos, denotando rotación orgánica de demanda."
                    )

                risk_alerts = []
                if part_diag.persistent_leaders:
                    risk_alerts.append(f"Riesgo de Concentración de Catálogo: '{part_diag.persistent_leaders[0]}' acapara la cima recurrente; evaluar si existe saturación de oferta o canibalización de nuevos lanzamientos.")
                else:
                    risk_alerts.append("Volatilidad de Preferencias del Consumidor: La rotación continua de líderes en cada período requiere reposición ágil y flexibilidad de catálogo.")

                recommendations = [
                    f"Focalizar estrategias de fidelización en los líderes recurrentes ({', '.join([p['leader'] for p in part_diag.partition_leaders[:2]])}).",
                    f"Adaptar el aprovisionamiento de {dim_lbl} anticipando los ciclos de alternancia detectados por {time_lbl}.",
                ]

                return ExecutiveStorytelling(
                    key_takeaway=key_takeaway,
                    diagnostic_metrics=part_diag.model_dump(),
                    quantitative_findings=findings,
                    risk_alerts=risk_alerts,
                    strategic_recommendations=recommendations,
                )

        # -------------------------------------------------------------------------
        # CASE 0.2: GEO PARTITIONED RANKING (Dominancia territorial y categorías líderes por país)
        # -------------------------------------------------------------------------
        if task.analytical_pattern == AnalyticalPattern.GEO_PARTITIONED_RANKING and rows:
            cols = list(rows[0].keys())
            geo_col = next((c for c in cols if any(w in c.lower() for w in ["pais", "país", "country", "nation", "region", "región"])), cols[0])
            met_col = next((c for c in cols if isinstance(rows[0][c], (int, float)) or c in (task.metrics or [])), cols[-1])
            cat_col = next((c for c in cols if c != geo_col and c != met_col), cols[1] if len(cols) > 1 else cols[0])

            total_territories = len(rows)
            total_vol = sum(float(r.get(met_col, 0) or 0) for r in rows)
            primary_unit = infer_column_unit(met_col)

            cat_counter = Counter(r.get(cat_col) for r in rows if r.get(cat_col))
            if cat_counter:
                dom_cat, dom_cnt = cat_counter.most_common(1)[0]
                pct_countries = round((dom_cnt / total_territories) * 100, 1) if total_territories > 0 else 0
                exceptions = [(str(r.get(geo_col)), str(r.get(cat_col)), float(r.get(met_col, 0) or 0)) for r in rows if r.get(cat_col) != dom_cat]

                # Top 3 markets by volume
                sorted_by_vol = sorted(rows, key=lambda r: float(r.get(met_col, 0) or 0), reverse=True)
                top_3 = sorted_by_vol[:3]
                top_3_vol = sum(float(r.get(met_col, 0) or 0) for r in top_3)
                top_3_pct = round((top_3_vol / total_vol) * 100, 1) if total_vol > 0 else 0
                top_markets_str = ", ".join([f"{r.get(geo_col)} ({format_metric_value(r.get(met_col, 0), primary_unit)})" for r in top_3])

                key_takeaway = (
                    f"Hegemonía Territorial de '{dom_cat}': Lidera indiscutiblemente en {dom_cnt} de los {total_territories} países analizados "
                    f"({pct_countries}% de penetración geográfica), sumando {format_metric_value(total_vol, primary_unit)} de demanda total."
                )

                findings = [
                    f"Volumen y Cobertura: {total_territories} mercados geográficos consolidados con un volumen global de {format_metric_value(total_vol, primary_unit)}.",
                    f"Top 3 Territorios en Demanda: {top_markets_str}, concentrando el {top_3_pct}% del volumen mundial de ventas analizado.",
                ]

                if exceptions:
                    exc_summary = ", ".join([f"{e[0]} → '{e[1]}' ({format_metric_value(e[2], primary_unit)})" for e in exceptions[:4]])
                    findings.append(f"Excepciones y Preferencias Regionales: Se identificaron {len(exceptions)} mercados con preferencias alternativas frente a la norma global: {exc_summary}.")
                else:
                    findings.append(f"Monopolio Geográfico Total: '{dom_cat}' domina el 100% de los países evaluados sin excepciones regionales.")

                risk_alerts = []
                if pct_countries >= 70:
                    risk_alerts.append(
                        f"Riesgo de Monocultivo de Catálogo: La alta concentración en '{dom_cat}' ({pct_countries}% de los países) genera vulnerabilidad si cambian las tendencias del mercado; diversificar la promoción de categorías secundarias."
                    )
                if exceptions:
                    risk_alerts.append(
                        f"Riesgo de Estandarización Forzada: Imponer una oferta global sin considerar divergencias culturales locales (ej. {exceptions[0][0]} prefiriendo '{exceptions[0][1]}') debilitará la cuota de mercado en esas regiones."
                    )
                else:
                    risk_alerts.append("Falta de Diferenciación Regional: La uniformidad de demanda sugiere poca exploración de catálogos alternativos en mercados periféricos.")

                recommendations = [
                    f"Focalizar campañas de escala global en '{dom_cat}' para los mercados hegemónicos ({', '.join([str(r.get(geo_col)) for r in top_3])}).",
                ]
                if exceptions:
                    recommendations.append(
                        f"Desplegar estrategias de hiper-localización y catálogos dedicados en los territorios divergentes ({', '.join([e[0] for e in exceptions[:3]])}) para maximizar la conversión local."
                    )
                recommendations.append(
                    f"Implementar bundles cruzados combinando '{dom_cat}' con opciones emergentes para estimular el ticket promedio en mercados secundarios."
                )

                return ExecutiveStorytelling(
                    key_takeaway=key_takeaway,
                    diagnostic_metrics={
                        "total_territories": total_territories,
                        "dominant_category": dom_cat,
                        "dominant_territories_count": dom_cnt,
                        "global_penetration_pct": pct_countries,
                        "total_volume": round(total_vol, 2),
                        "unit": primary_unit,
                        "exceptions_count": len(exceptions),
                    },
                    quantitative_findings=findings,
                    risk_alerts=risk_alerts,
                    strategic_recommendations=recommendations,
                )

        # -------------------------------------------------------------------------
        # CASE 1: TIME SERIES (Mono o Multi-serie)
        # -------------------------------------------------------------------------
        if task.analytical_pattern in [AnalyticalPattern.TIME_SERIES, AnalyticalPattern.MULTI_SERIES_TIME_SERIES] and rows:
            ts_diag = analyze_time_series(rows, time_hint=task.time_dimension or "Fecha", met_hint=met_hint)
            if ts_diag:
                g_str = task.time_granularity.value.lower()
                s_name = task.series_dimension or "Categoria"
                distinct_series = []
                if task.series_dimension:
                    distinct_series = list(dict.fromkeys(r[s_name] for r in rows if s_name in r))

                if task.top_n and distinct_series:
                    cohort_prefix = "Bottom" if task.ranking_criterion == "menor desempeño" else "Top"
                    cohort_str = f" para las {cohort_prefix} {task.top_n} {s_name} ({', '.join(distinct_series[:task.top_n])})"
                else:
                    cohort_str = ""

                key_takeaway = (
                    f"Evolución temporal ({g_str}){cohort_str}: Trayectoria {ts_diag.trend_direction.lower()} "
                    f"con pico histórico el {ts_diag.peak_date} ({format_metric_value(ts_diag.peak_val, ts_diag.unit)})."
                )

                findings = [
                    f"Volumen acumulado del período: {format_metric_value(ts_diag.total_volume, ts_diag.unit)} a lo largo de {ts_diag.period_count} intervalos {g_str}s.",
                    f"Media por intervalo: {format_metric_value(ts_diag.mean_val, ts_diag.unit)} (Rango: {format_metric_value(ts_diag.trough_val, ts_diag.unit)} el {ts_diag.trough_date} a {format_metric_value(ts_diag.peak_val, ts_diag.unit)} el {ts_diag.peak_date}).",
                    f"Volatilidad de la demanda: Clasificada como {ts_diag.volatility_level} (Coeficiente de variación CV: {ts_diag.coefficient_of_variation}, Desviación estándar σ: {format_metric_value(ts_diag.std_dev, ts_diag.unit)}).",
                ]

                if ts_diag.period_change_pct is not None:
                    cagr_str = f" (CAGR anualizado: {ts_diag.cagr_pct:+.1f}%)" if ts_diag.cagr_pct is not None else ""
                    findings.append(f"Variación neta en la ventana temporal: {ts_diag.period_change_pct:+.1f}%{cagr_str}.")

                if ts_diag.anomalies:
                    anom_desc = ", ".join([f"{a['date']} ({format_metric_value(a['value'], ts_diag.unit)}, {a['type']})" for a in ts_diag.anomalies])
                    findings.append(f"Puntos anómalos (|z| > 2σ): {anom_desc}.")

                risk_alerts = []
                if ts_diag.volatility_level == "Alta":
                    risk_alerts.append(f"Alta Volatilidad Estacional: El coeficiente de variación de {ts_diag.coefficient_of_variation} indica picos y valles impredecibles; riesgo de rotura de stock en picos o sobrecosto de almacenamiento en valles.")
                if ts_diag.anomalies:
                    risk_alerts.append(f"Anomalías fuera de rango: Se detectaron {len(ts_diag.anomalies)} eventos atípicos con desviación mayor a 2 sigma del promedio histórico.")
                if not risk_alerts:
                    risk_alerts.append("Estabilidad Operativa: Variación temporal moderada sin disrupciones estadísticas atípicas.")

                recommendations = [
                    f"Alinear buffers de seguridad operativa con los períodos de alta demanda detectados alrededor de {ts_diag.peak_date}.",
                    "Investigar los factores causales de las anomalías estadísticas para anticipar futuras fluctuaciones de volumen.",
                ]

                return ExecutiveStorytelling(
                    key_takeaway=key_takeaway,
                    diagnostic_metrics=ts_diag.model_dump(),
                    quantitative_findings=findings,
                    risk_alerts=risk_alerts,
                    strategic_recommendations=recommendations,
                )

        # -------------------------------------------------------------------------
        # CASE 2: RANKINGS, CATEGORICAL BREAKDOWNS & GEO DISTRIBUTIONS
        # -------------------------------------------------------------------------
        dist_diag = analyze_distribution(rows, dim_hint=dim_hint, met_hint=met_hint)
        if dist_diag and dist_diag.top_1_label:
            dim_lbl = dist_diag.dimension_col
            unit = dist_diag.unit

            cohort_prefix = "Bottom" if task.ranking_criterion == "menor desempeño" else "Top"
            n_prefix = f"{cohort_prefix} {task.top_n} {dim_lbl} - " if task.top_n else f"Distribución de {dim_lbl} - "
            # Key Takeaway with Gap Context
            if dist_diag.dominance_gap_pct is not None and dist_diag.dominance_gap_pct > 25.0:
                key_takeaway = (
                    f"{n_prefix}Liderazgo consolidado: '{dist_diag.top_1_label}' encabeza con "
                    f"{format_metric_value(dist_diag.top_1_val, unit)} ({dist_diag.top_1_share_pct}% de cuota del segmento), "
                    f"superando al 2º lugar ('{dist_diag.top_2_label}') por un margen de +{dist_diag.dominance_gap_pct}%."
                )
            elif dist_diag.top_2_label:
                key_takeaway = (
                    f"{n_prefix}Competencia reñida: '{dist_diag.top_1_label}' lidera con "
                    f"{format_metric_value(dist_diag.top_1_val, unit)} ({dist_diag.top_1_share_pct}% de cuota), "
                    f"seguido de cerca por '{dist_diag.top_2_label}' ({format_metric_value(dist_diag.top_2_val, unit)})."
                )
            else:
                key_takeaway = f"{n_prefix}Líder identificado: '{dist_diag.top_1_label}' con {format_metric_value(dist_diag.top_1_val, unit)}."

            findings = []
            # Rank items with individual shares
            for idx, r in enumerate(rows[:5], 1):
                lbl = r.get(dist_diag.dimension_col, f"Item {idx}")
                v = float(r.get(dist_diag.metric_col, 0) or 0)
                share = (v / dist_diag.total_volume * 100) if dist_diag.total_volume > 0 else 0.0
                findings.append(f"#{idx} {lbl}: {format_metric_value(v, unit)} ({share:.1f}% del volumen analizado)")

            findings.append(
                f"Concentración Pareto: Los 3 primeros puestos absorben el {dist_diag.top_3_share_pct}% "
                f"del volumen total ({format_metric_value(dist_diag.total_volume, unit)} acumulado)."
            )
            if dist_diag.hhi_index is not None:
                findings.append(
                    f"Índice Herfindahl-Hirschman (HHI): {dist_diag.hhi_index} pts — Clasificación: {dist_diag.hhi_classification}."
                )
            findings.append(
                f"Métricas de dispersión: Promedio de {format_metric_value(dist_diag.mean_val, unit)} "
                f"y mediana de {format_metric_value(dist_diag.median_val, unit)}."
            )

            risk_alerts = []
            if dist_diag.is_concentrated:
                risk_alerts.append(
                    f"Alerta de Riesgo de Concentración: El Top 1 ('{dist_diag.top_1_label}') representa el {dist_diag.top_1_share_pct}% de la muestra. "
                    f"Cualquier fallo de cadena de suministro o caída de demanda en esta entidad comprometería el resultado global."
                )
            if dist_diag.hhi_index and dist_diag.hhi_index > 2500:
                risk_alerts.append(
                    f"Riesgo Estructural Severo (HHI {dist_diag.hhi_index}): Alta vulnerabilidad ante fluctuaciones de los líderes consolidados."
                )
            if dist_diag.dominance_gap_pct and dist_diag.dominance_gap_pct > 50.0:
                risk_alerts.append(
                    f"Brecha Competitiva Extrema: Margen del +{dist_diag.dominance_gap_pct}% sobre el segundo competidor denota falta de balance en el portafolio secundario."
                )
            if not risk_alerts:
                risk_alerts.append("Diversificación Saludable: No se observan monopolios individuales en la muestra analizada.")

            recommendations = [
                f"Blindar contratos y asegurar disponibilidad de stock crítico para '{dist_diag.top_1_label}' como motor principal de ingresos.",
                f"Implementar promociones cruzadas o incentivos para impulsar a '{dist_diag.top_2_label or 'los siguientes segmentos'}' y mitigar la dependencia única.",
            ]

            return ExecutiveStorytelling(
                key_takeaway=key_takeaway,
                diagnostic_metrics=dist_diag.model_dump(),
                quantitative_findings=findings,
                risk_alerts=risk_alerts,
                strategic_recommendations=recommendations,
            )

        # Fallback basic storytelling if no diagnostic could be calculated
        return ExecutiveStorytelling(
            key_takeaway=f"Análisis completado: {evidence.observations[0] if evidence.observations else 'Sin datos'}.",
            diagnostic_metrics={},
            quantitative_findings=evidence.observations[:5],
            risk_alerts=["Distribución observada dentro de rangos operativos normales."],
            strategic_recommendations=[
                "Monitorear las entidades líderes observadas.",
                "Profundizar cruzando con períodos temporales adicionales.",
            ],
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
        # Step 0: Epistemological check via Auto-Ontology (prevent hallucinating on out-of-scope concepts)
        out_of_scope = next((c for c in (task.constraints or []) if c.startswith("OUT_OF_SCOPE:")), None)
        if out_of_scope:
            reason_text = out_of_scope.replace("OUT_OF_SCOPE: ", "")
            return DataEvidence(
                engine_id=task.engine_id,
                observations=[reason_text],
                confidence=0.2,
                warnings=[reason_text],
            )

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

            # Semantic Guardrail: Ensure required dimension tables are present in AST
            if guard_res.allowed and (task.series_dimension or task.dimensions):
                model = self.semantic_catalog.get_model(task.engine_id)
                if model:
                    dims_to_check = [task.series_dimension] if task.series_dimension else task.dimensions
                    for dim_name in dims_to_check:
                        target_dim = model.get_dimension(dim_name)
                        if target_dim and target_dim.type != "temporal":
                            if target_dim.table.lower() not in [t.lower() for t in guard_res.tables]:
                                guard_res.allowed = False
                                guard_res.detail = f"Semantic Guardrail: Table '{target_dim.table}' for dimension '{dim_name}' is missing from query AST."
                                warnings.append(f"Intento {attempt}: Guardarraíl Semántico detectó omisión de '{target_dim.table}'. Auto-reflejando...")
                                last_rejection_detail = guard_res.detail
                                break

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
