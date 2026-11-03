"""Kratos Semantic Unit & Metric Intelligence.

Guarantees accurate formatting for:
  - Currency: $ USD
  - Percentages: %
  - Discrete Counts: pedidos, órdenes, transacciones (NEVER prefixed with $)
  - Inventory / Physical Stock: unidades, piezas, stock, uds (NEVER prefixed with $)
  - Duration & Transit: días, horas, minutos
"""

import re
from typing import Any, Tuple

MONEY_KEYWORDS = [
    "total", "subtotal", "price", "unitprice", "cost", "revenue", "sales",
    "ingreso", "precio", "monto", "importe", "venta", "ventas", "costo",
    "valor", "tarifa", "freight", "flete", "facturacion", "totalamount", "amount"
]

PERCENTAGE_KEYWORDS = [
    "discount", "descuento", "margin", "margen", "rate", "tasa",
    "porcentaje", "pct", "ratio", "porc", "share", "participacion"
]

DURATION_KEYWORDS = [
    "dias", "days", "tiempo", "demora", "duracion", "transit", "plazo",
    "lead_time", "horas", "hours", "minutos"
]

ORDER_COUNT_KEYWORDS = [
    "pedidos", "ordenes", "orders", "orders_count", "transacciones", "num_orders"
]

STOCK_KEYWORDS = [
    "unitsinstock", "stock", "unidades", "cantidad", "quantity", "piezas",
    "inventory", "existencias", "uds"
]


def infer_column_unit(column_name: str) -> str:
    """Infers the precise business semantic unit for any column."""
    clean = re.sub(r"[_\-\s]+", "", column_name.lower())

    if any(k in clean for k in PERCENTAGE_KEYWORDS):
        return "%"
    if any(k in clean for k in DURATION_KEYWORDS):
        return "días"
    if any(k in clean for k in ORDER_COUNT_KEYWORDS):
        return "pedidos"
    if any(k in clean for k in STOCK_KEYWORDS):
        return "unidades"
    if any(k in clean for k in MONEY_KEYWORDS):
        return "$ USD"

    return ""


def format_metric_value(val: Any, unit: str) -> str:
    """Formats numeric values according to semantic unit constraints."""
    if val is None:
        return "N/A"

    try:
        num = float(val)
    except (ValueError, TypeError):
        return str(val)

    if unit == "$ USD":
        if abs(num) >= 1_000_000:
            return f"${num / 1_000_000:.2f}M"
        if abs(num) >= 1_000:
            return f"${num / 1_000:.2f}K"
        return f"${num:,.2f}"

    if unit == "%":
        val_pct = num * 100 if abs(num) <= 1.0 and num != 0 else num
        return f"{val_pct:.1f}%"

    if unit in ("días", "horas"):
        return f"{num:.1f} {unit}"

    if unit in ("pedidos", "unidades"):
        return f"{int(round(num)):,} {unit}"

    if num.is_integer():
        return f"{int(num):,}"
    return f"{num:,.2f}"
