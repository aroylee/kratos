"""Archify ERD & Query Relational Visualizer for Kratos.

Generates validated interactive Entity-Relationship & Lineage diagrams
using the Archify compiler (tools/archify/bin/archify.mjs).
"""

from pathlib import Path
import json
import os
import subprocess
import tempfile
from typing import Any
import sqlglot
from sqlglot import exp

from kratos.semantics.mdl import SemanticCatalog, SemanticModelMDL


ARCHIFY_CLI = Path(__file__).resolve().parent.parent.parent / "tools" / "archify" / "bin" / "archify.mjs"
CATALOG = SemanticCatalog()


def extract_tables_and_joins_from_sql(sql_text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Extracts participating tables and JOIN conditions from SQL query using sqlglot AST."""
    tables_found: list[str] = []
    joins_found: list[dict[str, str]] = []

    try:
        parsed = sqlglot.parse_one(sql_text)
    except Exception:
        # Fallback heuristic if AST fails
        lowered = sql_text.lower()
        for candidate in ["customers", "orders", "order_details", "products", "categories", "employees", "invoiceline", "invoice", "track", "album", "artist", "film", "actor", "rental", "payment"]:
            if candidate in lowered and candidate not in tables_found:
                tables_found.append(candidate)
        return tables_found, []

    # Extract tables from FROM and JOINs
    for table_node in parsed.find_all(exp.Table):
        t_name = table_node.name
        if t_name and t_name.lower() not in [t.lower() for t in tables_found]:
            # Filter out CTE aliases if any
            tables_found.append(t_name)

    # Extract explicit JOINs and their ON clauses
    for join_node in parsed.find_all(exp.Join):
        to_table = join_node.this.name if hasattr(join_node.this, "name") else str(join_node.this)
        on_clause = ""
        if join_node.args.get("on"):
            on_clause = join_node.args["on"].sql()
        joins_found.append({
            "to_table": to_table,
            "on_clause": on_clause
        })

    return tables_found, joins_found


def generate_archify_erd_spec(
    sql_text: str,
    engine_id: str,
    goal: str = "Consulta Analítica",
    engine_schema: dict[str, list[dict[str, Any]]] | None = None
) -> dict[str, Any]:
    """Builds a compliant Archify ERD specification JSON for the executed SQL query."""
    tables_in_query, joins = extract_tables_and_joins_from_sql(sql_text)
    mdl: SemanticModelMDL | None = CATALOG.get_model(engine_id)

    # If no tables found in query, use top tables from MDL
    if not tables_in_query and mdl and mdl.entities:
        tables_in_query = [e.name for e in mdl.entities[:3]]

    # Normalized lookup of available tables in this diagram
    diagram_tables = {t.lower(): t for t in tables_in_query}

    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []

    # Map MDL relationships for fast lookup
    mdl_rels_by_pair: dict[tuple[str, str], Any] = {}
    if mdl:
        for r in mdl.relationships:
            mdl_rels_by_pair[(r.from_table.lower(), r.to_table.lower())] = r
            mdl_rels_by_pair[(r.to_table.lower(), r.from_table.lower())] = r

    # Determine tags and roles
    metric_tables = {m.table.lower() for m in (mdl.metrics if mdl else [])}
    dim_tables = {d.table.lower() for d in (mdl.dimensions if mdl else [])}

    for idx, table_name in enumerate(tables_in_query):
        t_lower = table_name.lower()
        tag = "transacción"
        if t_lower in metric_tables:
            tag = "métricas"
        elif t_lower in dim_tables:
            tag = "dimensión"
        elif "detail" in t_lower or "line" in t_lower or "item" in t_lower:
            tag = "hechos"

        # Grid positioning: 2 per row if 4 tables, otherwise 3 per row
        cols_per_row = 2 if len(tables_in_query) == 4 else 3
        row = idx // cols_per_row
        col = idx % cols_per_row

        # Collect columns from engine_schema or MDL entity
        attributes: list[dict[str, Any]] = []
        raw_cols = []
        if engine_schema and table_name in engine_schema:
            raw_cols = engine_schema[table_name]
        elif engine_schema and t_lower in engine_schema:
            raw_cols = engine_schema[t_lower]

        # Collect primary key from MDL
        pk_cols = []
        if mdl:
            ent = mdl.get_entity(table_name)
            if ent:
                pk_cols = [p.lower() for p in ent.primary_key]

        if raw_cols:
            for c in raw_cols:  # Include ALL attributes for complete schema transparency
                if isinstance(c, dict):
                    c_name = c.get("name", "")
                    c_type = str(c.get("type", "TEXT")).upper()
                    is_pk = c.get("primary_key", False) or c_name.lower() in pk_cols
                else:
                    c_name = str(c)
                    c_lower = c_name.lower()
                    if c_lower.endswith("id") or "count" in c_lower or "quantity" in c_lower or c_lower == "id":
                        c_type = "INTEGER"
                    elif any(k in c_lower for k in ["price", "amount", "discount", "total", "freight", "rate", "cost", "salary", "balance"]):
                        c_type = "REAL"
                    elif any(k in c_lower for k in ["date", "time", "year"]):
                        c_type = "DATETIME"
                    else:
                        c_type = "TEXT"
                    t_stem = t_lower[:-1] if t_lower.endswith('s') else t_lower
                    is_pk = c_lower in pk_cols or c_lower == f"{t_lower}id" or c_lower == f"{t_stem}id" or c_lower == "id"

                attr_item: dict[str, Any] = {
                    "name": c_name,
                    "type": c_type
                }
                if is_pk:
                    attr_item["key"] = "pk"

                # Check if this column is an explicit FK referencing another table IN THE DIAGRAM
                # Archify requires: if key == "fk", references MUST point to an entity in entities[]!
                ref_target = None
                if mdl:
                    for rel in mdl.relationships:
                        if rel.from_table.lower() == t_lower and rel.to_table.lower() in diagram_tables:
                            if c_name.lower() in rel.on_clause.lower():
                                target_actual_name = diagram_tables[rel.to_table.lower()]
                                target_pk = "id"
                                target_ent = mdl.get_entity(target_actual_name)
                                if target_ent and target_ent.primary_key:
                                    target_pk = target_ent.primary_key[0]
                                ref_target = f"{target_actual_name}.{target_pk}"
                                break

                if ref_target and not is_pk:
                    attr_item["key"] = "fk"
                    attr_item["references"] = ref_target

                attributes.append(attr_item)
        else:
            # Synthetic clean schema when introspect is minimal
            attributes = [
                {"name": f"{table_name}ID", "type": "INTEGER", "key": "pk"},
                {"name": "nombre", "type": "TEXT"},
                {"name": "descripcion", "type": "TEXT"}
            ]

        # Ensure at least one primary key exists
        if not any(a.get("key") == "pk" for a in attributes) and attributes:
            attributes[0]["key"] = "pk"

        entities.append({
            "id": table_name,
            "label": table_name,
            "sublabel": f"{len(attributes)} atributos",
            "tag": tag,
            "row": row,
            "col": col,
            "attributes": attributes
        })

    # Build relationships from query joins or MDL
    added_rel_pairs = set()

    for j in joins:
        to_tbl = j["to_table"]
        if to_tbl.lower() not in diagram_tables:
            continue
        to_canonical = diagram_tables[to_tbl.lower()]

        # Try to find which other table in diagram it connects to
        on_clause = j.get("on_clause", "")
        connected_from = None
        for other_t in tables_in_query:
            if other_t.lower() != to_canonical.lower() and other_t.lower() in on_clause.lower():
                connected_from = other_t
                break

        if connected_from:
            pair_key = tuple(sorted([connected_from.lower(), to_canonical.lower()]))
            if pair_key not in added_rel_pairs:
                added_rel_pairs.add(pair_key)
                relationships.append({
                    "id": f"rel_{connected_from}_{to_canonical}".replace(" ", "_"),
                    "from": connected_from,
                    "to": to_canonical,
                    "label": on_clause if len(on_clause) < 45 else f"{connected_from} ⇄ {to_canonical}",
                    "fromCardinality": "many",
                    "toCardinality": "one"
                })

    # If no joins found from AST but multiple tables in query, connect them via MDL
    if len(relationships) < len(tables_in_query) - 1 and mdl:
        for i in range(len(tables_in_query)):
            for k in range(i + 1, len(tables_in_query)):
                t1 = tables_in_query[i]
                t2 = tables_in_query[k]
                pair_key = tuple(sorted([t1.lower(), t2.lower()]))
                if pair_key in added_rel_pairs:
                    continue
                if (t1.lower(), t2.lower()) in mdl_rels_by_pair:
                    m_rel = mdl_rels_by_pair[(t1.lower(), t2.lower())]
                    added_rel_pairs.add(pair_key)
                    relationships.append({
                        "id": f"rel_{t1}_{t2}".replace(" ", "_"),
                        "from": t1,
                        "to": t2,
                        "label": m_rel.on_clause,
                        "fromCardinality": "many" if "many" in m_rel.cardinality else "one",
                        "toCardinality": "one"
                    })

    erd_spec: dict[str, Any] = {
        "schema_version": 1,
        "diagram_type": "erd",
        "meta": {
            "title": f"Relaciones: {goal}",
            "subtitle": f"Motor: {engine_id.upper()} • {len(entities)} tablas enlazadas en la consulta",
            "quality_profile": "standard"
        },
        "layout": {
            "mode": "grid",
            "gapY": 40,
            "gapX": 60
        },
        "entities": entities,
        "relationships": relationships
    }

    return erd_spec


def generate_full_database_archify_erd_spec(
    engine_id: str,
    db_path: Path
) -> dict[str, Any]:
    """Generates an exhaustive, 100% grounded Archify ERD specification for the entire database."""
    import sqlite3
    db_path = Path(db_path).resolve()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cursor.fetchall()]

        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        seen_rels = set()
        diag_tables = {t.lower(): t for t in tables}

        cols_per_row = 3
        for idx, t in enumerate(tables):
            cursor.execute(f"PRAGMA table_info('{t}');")
            cols = cursor.fetchall()
            cursor.execute(f"PRAGMA foreign_key_list('{t}');")
            fks = cursor.fetchall()
            fk_map = {fk[3]: (fk[2], fk[4]) for fk in fks if fk[2].lower() in diag_tables}

            attrs = []
            max_len = max(len(c[1]) for c in cols) if cols else 10
            for c in cols:
                cname = c[1]
                ctype = (c[2] or "TEXT").upper()
                is_pk = c[5] > 0
                is_fk = cname in fk_map
                item = {"name": cname, "type": ctype}
                if is_pk and is_fk:
                    item["key"] = ["pk", "fk"]
                    target_t, target_c = fk_map[cname]
                    item["references"] = f"{diag_tables[target_t.lower()]}.{target_c}"
                elif is_pk:
                    item["key"] = "pk"
                elif is_fk:
                    item["key"] = "fk"
                    target_t, target_c = fk_map[cname]
                    item["references"] = f"{diag_tables[target_t.lower()]}.{target_c}"
                attrs.append(item)

            calculated_width = max(360, max_len * 15 + 100)
            entities.append({
                "id": t,
                "label": t,
                "sublabel": f"{len(attrs)} atributos",
                "width": calculated_width,
                "row": idx // cols_per_row,
                "col": idx % cols_per_row,
                "attributes": attrs
            })

            for fk in fks:
                target_t = fk[2]
                if target_t.lower() in diag_tables:
                    actual_target = diag_tables[target_t.lower()]
                    if t.lower() == actual_target.lower():
                        continue
                    rel_key = (t, actual_target, fk[3], fk[4])
                    if rel_key not in seen_rels:
                        seen_rels.add(rel_key)
                        relationships.append({
                            "id": f"rel_{t}_{actual_target}_{fk[3]}".replace(" ", "_"),
                            "from": t,
                            "to": actual_target,
                            "fromCardinality": "many",
                            "toCardinality": "one"
                        })

        return {
            "schema_version": 1,
            "diagram_type": "erd",
            "meta": {
                "title": f"Modelo Entidad-Relación Completo: {engine_id.upper()}",
                "subtitle": f"{len(entities)} tablas físicas • {sum(len(e['attributes']) for e in entities)} atributos totales • {len(relationships)} relaciones",
                "quality_profile": "standard"
            },
            "layout": {
                "mode": "grid",
                "gapY": 50,
                "gapX": 80
            },
            "entities": entities,
            "relationships": relationships
        }
    finally:
        conn.close()


def compile_archify_diagram(erd_spec: dict[str, Any]) -> str:
    """Invokes Archify Node.js compiler to generate standalone HTML."""
    if not ARCHIFY_CLI.exists():
        raise FileNotFoundError(f"Archify CLI not found at {ARCHIFY_CLI}")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_in:
        json.dump(erd_spec, f_in)
        in_path = f_in.name

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f_out:
        out_path = f_out.name

    try:
        cmd = ["node", str(ARCHIFY_CLI), "render", "erd", in_path, out_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            raise RuntimeError(f"Archify compilation failed:\n{res.stderr or res.stdout}")

        with open(out_path, "r", encoding="utf-8") as f:
            html_output = f.read()

        return html_output
    finally:
        if os.path.exists(in_path):
            os.remove(in_path)
        if os.path.exists(out_path):
            os.remove(out_path)


def enrich_entities_for_ui(entities: list[dict[str, Any]], engine_id: str) -> list[dict[str, Any]]:
    """Enriches entities for the UI attribute inspector, adding external FK detection and column counts."""
    mdl = CATALOG.get_model(engine_id)
    enriched: list[dict[str, Any]] = []

    for ent in entities:
        t_lower = ent["id"].lower()
        ent_data = {
            "id": ent["id"],
            "label": ent.get("label", ent["id"]),
            "tag": ent.get("tag", "entidad"),
            "sublabel": ent.get("sublabel", f"{len(ent.get('attributes', []))} atributos"),
            "total_columns": len(ent.get("attributes", [])),
            "attributes": []
        }

        for attr in ent.get("attributes", []):
            attr_item = {
                "name": attr["name"],
                "type": attr.get("type", "TEXT"),
                "key": attr.get("key"),
                "references": attr.get("references")
            }

            # Check if this attribute is an external foreign key not linked in the diagram
            if not attr_item.get("key") and mdl:
                for rel in mdl.relationships:
                    if rel.from_table.lower() == t_lower and attr["name"].lower() in rel.on_clause.lower():
                        target_ent = mdl.get_entity(rel.to_table)
                        target_pk = target_ent.primary_key[0] if (target_ent and target_ent.primary_key) else "id"
                        attr_item["external_fk"] = f"{rel.to_table}.{target_pk}"
                        break

            ent_data["attributes"].append(attr_item)

        enriched.append(ent_data)

    return enriched
