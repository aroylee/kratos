"""Kratos Auto-Ontology Generator & Extraction Substrate.

Inspired by NVIDIA Auto-Ontology and Wren AI MDL:
Automates schema introspection, foreign key relationship discovery,
semantic classification (temporal, geo, categorical, measures),
and taxonomy/synonym generation for deterministic Text-to-SQL.
"""

from __future__ import annotations
import re
import sqlite3
from pathlib import Path
from typing import Any
import yaml

from kratos.engines.registry import DatabaseEngine
from kratos.semantics.mdl import (
    SemanticModelMDL,
    EntityMDL,
    DimensionMDL,
    MeasureMDL,
    MetricMDL,
    RelationshipMDL,
)


# Standard canonical synonym dictionary across enterprise and relational domains
CANONICAL_SYNONYM_RULES: dict[str, list[str]] = {
    # Geographic
    "country": ["país", "pais", "paises", "países", "nación", "nacion", "mercado", "destino", "destinos"],
    "pais": ["país", "pais", "paises", "países", "nación", "nacion", "mercado", "destino", "destinos"],
    "city": ["ciudad", "ciudades", "localidad", "municipio"],
    "ciudad": ["ciudad", "ciudades", "localidad", "municipio"],
    "state": ["estado", "estados", "provincia", "provincias", "departamento"],
    "region": ["región", "region", "regiones", "zona", "zonas", "territorio", "departamento", "provincia"],

    # Temporal
    "date": ["fecha", "día", "dia", "tiempo", "histórico", "mes", "semana", "ano", "año", "trimestre"],
    "fecha": ["fecha", "día", "dia", "tiempo", "histórico", "mes", "semana", "ano", "año", "trimestre"],
    "year": ["año", "ano", "anual", "ejercicio"],
    "month": ["mes", "mensual"],

    # Categorical
    "category": ["categoría", "categoria", "categorías", "tipo", "segmento", "departamento", "familia"],
    "categoria": ["categoría", "categoria", "categorías", "tipo", "segmento", "departamento", "familia"],
    "product": ["producto", "productos", "artículo", "articulos", "item", "items", "mercancía", "mercancia"],
    "producto": ["producto", "productos", "artículo", "articulos", "item", "items", "mercancía", "mercancia"],
    "customer": ["cliente", "clientes", "comprador", "compradores", "usuario", "usuarios"],
    "cliente": ["cliente", "clientes", "comprador", "compradores", "usuario", "usuarios"],
    "employee": ["empleado", "empleados", "vendedor", "vendedores", "personal", "asesor", "colaborador"],
    "empleado": ["empleado", "empleados", "vendedor", "vendedores", "personal", "asesor", "colaborador"],
    "genre": ["género", "genero", "géneros", "generos", "estilo", "categoría musical"],
    "genero": ["género", "genero", "géneros", "generos", "estilo", "categoría musical"],
    "artist": ["artista", "artistas", "músico", "músicos", "banda", "bandas", "autor", "intérprete"],
    "artista": ["artista", "artistas", "músico", "músicos", "banda", "bandas", "autor", "intérprete"],
    "album": ["álbum", "album", "álbumes", "albumes", "disco", "discos"],
    "track": ["canción", "cancion", "canciones", "track", "tracks", "tema", "temas", "pista"],
    "cancion": ["canción", "cancion", "canciones", "track", "tracks", "tema", "temas", "pista"],

    # Quantitative & Financial Measures
    "revenue": ["ventas", "venta", "facturación", "facturacion", "ingresos", "recaudación", "recaudo", "monto", "dinero"],
    "sales": ["ventas", "venta", "facturación", "facturacion", "ingresos", "recaudación", "recaudo", "monto", "dinero"],
    "facturacion": ["ventas", "venta", "facturación", "facturacion", "ingresos", "recaudación", "recaudo", "monto", "dinero"],
    "ventas": ["ventas", "venta", "facturación", "facturacion", "ingresos", "recaudación", "recaudo", "monto", "dinero"],
    "total": ["total", "monto", "volumen", "acumulado"],
    "orders": ["pedidos", "pedido", "órdenes", "ordenes", "compras", "transacciones", "envíos", "despachos"],
    "pedidos": ["pedidos", "pedido", "órdenes", "ordenes", "compras", "transacciones", "envíos", "despachos"],
    "quantity": ["cantidad", "unidades", "volumen", "piezas", "stock"],
    "cantidad": ["cantidad", "unidades", "volumen", "piezas", "stock"],
}


class AutoOntologyExtractor:
    """Introspects raw database schemas and discovers entities, relationships, dimensions, and measures."""

    def __init__(self, engine: DatabaseEngine):
        self.engine = engine
        self.db_path = engine.db_path

    def extract(self) -> SemanticModelMDL:
        """Runs full schema introspection, FK graph extraction, and semantic classification."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [r[0] for r in cursor.fetchall()]

            entities: list[EntityMDL] = []
            relationships: list[RelationshipMDL] = []
            dimensions: list[DimensionMDL] = []
            measures: list[MeasureMDL] = []
            metrics: list[MetricMDL] = []

            seen_rels: set[tuple[str, str, str]] = set()

            for t in tables:
                cursor.execute(f"PRAGMA table_info('{t}');")
                col_info = cursor.fetchall()
                # col_info: (cid, name, type, notnull, dflt_value, pk)
                pk_cols = [c[1] for c in col_info if c[5] > 0]

                # 1. Entity Definition
                entity = EntityMDL(
                    name=t,
                    primary_key=pk_cols or ([col_info[0][1]] if col_info else ["id"]),
                    description=f"Entidad relacional de la tabla {t}",
                    grain=f"Una fila por registro de {t}"
                )
                entities.append(entity)

                # 2. Foreign Keys / Relationships
                cursor.execute(f"PRAGMA foreign_key_list('{t}');")
                fk_info = cursor.fetchall()
                # fk_info: (id, seq, table, from, to, on_update, on_delete, match)
                for fk in fk_info:
                    to_tbl = fk[2]
                    from_col = fk[3]
                    to_col = fk[4]
                    on_clause = f"{t}.{from_col} = {to_tbl}.{to_col}"
                    rel_key = (t, to_tbl, on_clause)
                    if rel_key not in seen_rels:
                        relationships.append(RelationshipMDL(
                            from_table=t,
                            to_table=to_tbl,
                            on_clause=on_clause,
                            cardinality="many_to_one"
                        ))
                        seen_rels.add(rel_key)

                    # Also add inverse relationship
                    inv_rel_key = (to_tbl, t, on_clause)
                    if inv_rel_key not in seen_rels:
                        relationships.append(RelationshipMDL(
                            from_table=to_tbl,
                            to_table=t,
                            on_clause=on_clause,
                            cardinality="one_to_many"
                        ))
                        seen_rels.add(inv_rel_key)

                # 3. Column-level Semantic Classification (Dimensions & Measures)
                for col in col_info:
                    col_name = col[1]
                    col_type = (col[2] or "TEXT").upper()
                    is_pk = col[5] > 0
                    is_fk = any(fk[3] == col_name for fk in fk_info)

                    low_name = col_name.lower()

                    # Classify Temporal Dimension
                    if any(w in low_name for w in ["date", "fecha", "time", "timestamp", "year", "ano", "mes"]) or \
                       any(w in col_type for w in ["DATE", "TIME", "DATETIME", "TIMESTAMP"]):
                        dim_id = self._canonical_name(col_name, "Fecha")
                        synonyms = self._resolve_synonyms(low_name, "date")
                        dimensions.append(DimensionMDL(
                            id=dim_id,
                            table=t,
                            column=col_name,
                            synonyms=synonyms,
                            type="temporal",
                            allowed_grains=["day", "week", "month", "quarter", "year"],
                            description=f"Dimensión temporal derivada de {t}.{col_name}"
                        ))

                    # Classify Geographic Dimension
                    elif any(w in low_name for w in ["country", "pais", "nation", "nacion", "state", "city", "ciudad", "region"]):
                        dim_id = self._canonical_name(col_name, "Pais")
                        synonyms = self._resolve_synonyms(low_name, "country")
                        dimensions.append(DimensionMDL(
                            id=dim_id,
                            table=t,
                            column=col_name,
                            synonyms=synonyms,
                            type="geo",
                            description=f"Dimensión geográfica derivada de {t}.{col_name}"
                        ))

                    # Classify Descriptive Categorical Dimension
                    elif (not is_pk and not is_fk) and (
                        any(w in col_type for w in ["TEXT", "VARCHAR", "NVARCHAR", "CHAR", "STRING"]) or
                        any(w in low_name for w in ["name", "title", "category", "type", "desc", "status", "nombre", "titulo", "tipo", "estado"])
                    ):
                        dim_id = self._canonical_name(col_name, t)
                        synonyms = self._resolve_synonyms(low_name, low_name)
                        dimensions.append(DimensionMDL(
                            id=dim_id,
                            table=t,
                            column=col_name,
                            synonyms=synonyms,
                            type="categorical",
                            description=f"Dimensión categórica derivada de {t}.{col_name}"
                        ))

                    # Classify Numeric Measures & Metrics
                    elif any(w in col_type for w in ["INT", "FLOAT", "NUMERIC", "REAL", "DECIMAL", "DOUBLE"]) and not is_pk and not is_fk:
                        if any(w in low_name for w in ["price", "amount", "total", "sales", "revenue", "cost", "monto", "precio", "subtotal"]):
                            measure_id = f"{t}_{col_name}_sum"
                            metric_id = "Ventas_USD" if "price" in low_name or "amount" in low_name or "total" in low_name else self._canonical_name(col_name, "Monto_USD")
                            synonyms = self._resolve_synonyms(low_name, "revenue")
                            measures.append(MeasureMDL(
                                id=measure_id,
                                table=t,
                                column=col_name,
                                agg_type="sum",
                                expression=f"ROUND(SUM({t}.{col_name}), 2)",
                                unit="USD",
                                is_currency=True,
                                synonyms=synonyms,
                                description=f"Suma acumulada de {t}.{col_name}"
                            ))
                            metrics.append(MetricMDL(
                                id=metric_id,
                                table=t,
                                expression=f"ROUND(SUM({t}.{col_name}), 2)",
                                metric_type="atomic",
                                unit="USD",
                                is_currency=True,
                                synonyms=synonyms,
                                description=f"Métrica monetaria calculada de {t}.{col_name}"
                            ))

            # Add default COUNT metric if none found
            if not metrics and entities:
                main_table = entities[0].name
                metrics.append(MetricMDL(
                    id="Total_Registros",
                    table=main_table,
                    expression=f"COUNT(*)",
                    metric_type="atomic",
                    unit="registros",
                    is_currency=False,
                    synonyms=["total", "conteo", "cantidad", "registros", "volumen"],
                    description=f"Conteo de registros de {main_table}"
                ))

            model_name = f"Auto-Ontology {self.engine.engine_id.capitalize()}"
            desc = f"Ontología semántica auto-generada por Kratos Auto-Ontology Engine para el motor {self.engine.engine_id}."

            return SemanticModelMDL(
                engine_id=self.engine.engine_id,
                name=model_name,
                description=desc,
                entities=entities,
                dimensions=dimensions,
                measures=measures,
                metrics=metrics,
                relationships=relationships,
            )
        finally:
            conn.close()

    @staticmethod
    def _canonical_name(col_name: str, fallback: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]", "", col_name)
        if clean.lower() in ["billingcountry", "shipcountry", "country"]:
            return "Pais"
        if clean.lower() in ["orderdate", "invoicedate", "rentaldate", "date"]:
            return "Fecha"
        if clean.lower() in ["productname", "title"]:
            return "Producto"
        if clean.lower() in ["categoryname"]:
            return "Categoria"
        if clean.lower() in ["companyname", "firstname", "customername"]:
            return "Cliente"
        return clean or fallback

    @staticmethod
    def _resolve_synonyms(term: str, context: str) -> list[str]:
        synonyms = set([term.lower()])
        for key, syn_list in CANONICAL_SYNONYM_RULES.items():
            if key in term.lower() or key in context.lower():
                synonyms.update(syn_list)
        return list(synonyms)


class AutoOntologyService:
    """Manages automatic ontology generation, YAML compilation, and dynamic hot-loading."""

    @classmethod
    def generate_for_engine(cls, engine: DatabaseEngine) -> SemanticModelMDL:
        """Extracts and builds a complete SemanticModelMDL for any SQLite/DuckDB engine."""
        extractor = AutoOntologyExtractor(engine)
        return extractor.extract()

    @classmethod
    def export_to_yaml(cls, model: SemanticModelMDL, dest_path: Path) -> str:
        """Serializes SemanticModelMDL into standardized Wren AI MDL YAML specification."""
        data = model.model_dump()
        yaml_str = yaml.dump(data, sort_keys=False, allow_unicode=True)
        dest_path.write_text(yaml_str, encoding="utf-8")
        return yaml_str
