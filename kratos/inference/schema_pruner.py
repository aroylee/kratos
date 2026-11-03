"""Kratos Schema Pruning & In-Process Context Optimization.

Selects the 2-4 most relevant tables based on the user's inquiry, reducing prompt
context by up to 75% and injecting domain-specific calculation rules.
"""

import re
from typing import Dict, List, Set, Tuple


class SchemaPruner:
    """In-process heuristic schema pruning and business rules engine."""

    CALCULATION_RULES: Dict[str, List[str]] = {
        "northwind": [
            'Total Ventas Netas: SUM(Quantity * UnitPrice * (1 - Discount))',
            'Relación Órdenes a Clientes: Orders.CustomerID = Customers.CustomerID',
            'Relación Empleados: Orders.EmployeeID = Employees.EmployeeID',
        ],
        "chinook": [
            'Facturación Total: SUM(Invoice.Total)',
            'Relación Canciones a Artistas: Track -> Album -> Artist',
            'Relación Clientes a Facturas: Customer.CustomerId = Invoice.CustomerId',
        ],
        "sakila": [
            'Relación Actores a Películas: actor -> film_actor -> film',
            'Relación Películas a Categorías: film -> film_category -> category',
            'Ingresos por Alquiler: SUM(payment.amount)',
        ],
        "tpch": [
            'Relación Clientes a Países: customer.c_nationkey = nation.n_nationkey',
            'Relación Proveedores a Países: supplier.s_nationkey = nation.n_nationkey',
        ],
    }

    SYNONYMS: Dict[str, List[str]] = {
        "empleado": ["employee", "employees"],
        "empleados": ["employee", "employees"],
        "orden": ["order", "orders", "order_details"],
        "ordenes": ["order", "orders", "order_details"],
        "pedidos": ["order", "orders", "order_details"],
        "pedido": ["order", "orders", "order_details"],
        "cliente": ["customer", "customers"],
        "clientes": ["customer", "customers"],
        "producto": ["product", "products"],
        "productos": ["product", "products"],
        "categoria": ["category", "categories"],
        "categorias": ["category", "categories"],
        "venta": ["order_details", "sales", "invoice", "payment"],
        "ventas": ["order_details", "sales", "invoice", "payment"],
        "cancion": ["track", "tracks"],
        "canciones": ["track", "tracks"],
        "artista": ["artist", "album"],
        "artistas": ["artist", "album"],
        "actor": ["actor", "film_actor"],
        "actores": ["actor", "film_actor"],
        "pelicula": ["film", "film_category"],
        "peliculas": ["film", "film_category"],
    }

    def prune(
        self,
        query: str,
        engine_id: str,
        full_schema: Dict[str, List[str]],
        max_tables: int = 4
    ) -> Tuple[Dict[str, List[str]], List[str]]:
        """Extracts candidate tables based on lexical and synonym matching."""
        raw_tokens = set(re.findall(r"\w+", query.lower()))
        tokens = set(raw_tokens)
        for tok in raw_tokens:
            if tok in self.SYNONYMS:
                tokens.update(self.SYNONYMS[tok])

        scores: Dict[str, int] = {}

        for table, columns in full_schema.items():
            score = 0
            t_low = table.lower()

            # Direct table name or synonym mention
            if t_low in tokens or any(tok in t_low for tok in tokens if len(tok) > 3):
                score += 5

            # Column name mentions
            for col in columns:
                c_low = col.lower()
                if c_low in tokens or any(tok in c_low for tok in tokens if len(tok) > 3):
                    score += 2

            scores[table] = score

        # Sort tables by relevance score
        sorted_tables = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        relevant_tables = [t for t, score in sorted_tables if score > 0][:max_tables]

        # Fallback if no specific table tokens matched
        if not relevant_tables:
            relevant_tables = list(full_schema.keys())[:max_tables]

        pruned_schema = {t: full_schema[t] for t in relevant_tables if t in full_schema}
        rules = self.CALCULATION_RULES.get(engine_id, [])

        return pruned_schema, rules
