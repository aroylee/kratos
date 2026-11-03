"""Test suite for Kratos Security Guard and Contracts."""

import pytest
from kratos.security.sql_guard import validate_sql, RejectReason
from kratos.contracts.schemas import DataTask, Intent


def test_guard_blocks_drop_table():
    res = validate_sql("DROP TABLE customers;")
    assert not res.allowed
    assert res.reason == RejectReason.NOT_READ_ONLY


def test_guard_blocks_delete_in_cte():
    res = validate_sql("WITH poisoned AS (DELETE FROM customers RETURNING *) SELECT * FROM poisoned;")
    assert not res.allowed
    assert res.reason == RejectReason.NOT_READ_ONLY


def test_guard_blocks_forbidden_functions():
    res = validate_sql("SELECT pg_read_file('/etc/passwd');")
    assert not res.allowed
    assert res.reason == RejectReason.FORBIDDEN_FUNCTION


def test_guard_blocks_unknown_tables():
    res = validate_sql("SELECT * FROM hack_table;", allowed_tables={"customers", "orders"})
    assert not res.allowed
    assert res.reason == RejectReason.TABLE_NOT_ALLOWED


def test_guard_allows_safe_select_and_injects_limit():
    res = validate_sql("SELECT id, name FROM customers;", allowed_tables={"customers"})
    assert res.allowed
    assert "LIMIT 500" in res.sanitized_sql.upper()


def test_data_task_contract():
    task = DataTask(
        intent=Intent.QUERY_DATA,
        engine_id="northwind",
        goal="Obtener ventas por categoría",
    )
    assert task.engine_id == "northwind"
    assert task.intent == Intent.QUERY_DATA
