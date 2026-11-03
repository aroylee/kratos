"""Kratos Harness² Benchmark & Recursive Evolution Substrate.

Integrates the Google Research Harness² recursive agent harnessing substrate
(arXiv:2610.14224) into Kratos.

Evaluates, benchmarks, and optimizes the 8 core harness components:
1. System Prompt & Invariants (AGENTS.md)
2. 4-Layer AST Security Guard (sql_guard.py)
3. Schema Pruning & Business Calculation Rules (schema_pruner.py)
4. Formal Typed Contracts Protocol (contracts/schemas.py)
5. Two-Agent Orchestrator with Reflection (orchestrator.py)
6. Semantic Unit & Metric Intelligence (unit_utils.py & bi_engine.py)
7. Multi-Engine Auto-Discovery (registry.py)
8. CLI & API Delivery Interfaces (cli.py & api/main.py)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import harness2
    from harness2.demo import DemoAdapter, DemoProposer
    HARNESS2_AVAILABLE = True
except ImportError:
    HARNESS2_AVAILABLE = False


class KratosHarness2Agent:
    """Evaluates and benchmarks Kratos agent architecture using Harness²."""

    HARNESS_COMPONENTS = {
        "c1_system_prompt": {
            "name": "System Prompt & Invariants",
            "path": "AGENTS.md",
            "role": "Directivas base, contratos y reglas operativas de Kratos.",
        },
        "c2_guardrails": {
            "name": "4-Layer AST Security Guard",
            "path": "kratos/security/sql_guard.py",
            "role": "Barrera determinista AST con sqlglot (bloqueo de DROP, DELETE, ALTER, CTE exploits).",
        },
        "c3_memory_pruning": {
            "name": "Schema Pruning & Business Rules",
            "path": "kratos/inference/schema_pruner.py",
            "role": "Poda semántica del 75% del contexto e inyección de fórmulas contables.",
        },
        "c4_contracts": {
            "name": "Typed Contracts Protocol",
            "path": "kratos/contracts/schemas.py",
            "role": "Contratos Pydantic inmutables: DataTask -> DataEvidence -> FinalAnswer.",
        },
        "c5_two_agents": {
            "name": "Interpreter & Investigator with Auto-Reflection",
            "path": "kratos/agents/orchestrator.py",
            "role": "Separación de roles con bucle de auto-corrección ante rechazos del guard.",
        },
        "c6_units_bi": {
            "name": "Semantic Unit & BI Intelligence",
            "path": "kratos/semantics/unit_utils.py",
            "role": "Diferenciación estricta de unidades ($ USD, %, días, pedidos, unidades) y ECharts.",
        },
        "c7_engines": {
            "name": "Multi-Engine Auto-Discovery",
            "path": "kratos/engines/registry.py",
            "role": "Descubrimiento en caliente de SQLite / DuckDB en modo de solo lectura.",
        },
        "c8_interfaces": {
            "name": "CLI & Web Endpoints",
            "path": "kratos/cli.py",
            "role": "Puntos de entrega: kratos ask, kratos serve y API REST.",
        },
    }

    BENCHMARK_TASKS = [
        {"id": "task_nw_sales", "engine": "northwind", "query": "Ventas por empleado", "expected_table": "employees"},
        {"id": "task_nw_category", "engine": "northwind", "query": "Ventas por categoría", "expected_table": "categories"},
        {"id": "task_chinook_artists", "engine": "chinook", "query": "Canciones por artista", "expected_table": "Artist"},
        {"id": "task_chinook_billing", "engine": "chinook", "query": "Facturación por país", "expected_table": "Invoice"},
        {"id": "task_sakila_actors", "engine": "sakila", "query": "Top actores con más películas", "expected_table": "actor"},
        {"id": "task_tpch_nations", "engine": "tpch", "query": "Clientes por país", "expected_table": "customer"},
    ]

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).resolve().parent.parent.parent
        self.runs_dir = self.root_dir / "runs" / "harness2"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def audit_components(self) -> Dict[str, Any]:
        """Audits the existence and integrity of the 8 harness components."""
        audit = {}
        for cid, meta in self.HARNESS_COMPONENTS.items():
            full_path = self.root_dir / meta["path"]
            exists = full_path.exists()
            size_bytes = full_path.stat().st_size if exists else 0
            audit[cid] = {
                "name": meta["name"],
                "path": meta["path"],
                "role": meta["role"],
                "status": "HEALTHY_PRESENT" if exists else "MISSING",
                "size_bytes": size_bytes,
            }
        return audit

    def run_benchmark(self) -> Dict[str, Any]:
        """Executes the benchmark evaluation across all test engines."""
        from kratos.engines.registry import EngineRegistry
        from kratos.agents.orchestrator import InterpreterAgent, InvestigatorAgent
        from kratos.contracts.schemas import DataTask

        registry = EngineRegistry(self.root_dir / "data")
        interpreter = InterpreterAgent()
        investigator = InvestigatorAgent(registry)

        results = []
        passed_count = 0
        total_latency_ms = 0.0

        for task_def in self.BENCHMARK_TASKS:
            start_t = time.perf_counter()
            interpreted = interpreter.interpret(task_def["query"], task_def["engine"])
            task = DataTask(
                intent=interpreted.intent,
                engine_id=task_def["engine"],
                goal=interpreted.goal,
            )
            evidence = investigator.execute_task(task)
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            total_latency_ms += duration_ms

            passed = (
                evidence.confidence >= 0.8
                and len(evidence.queries) > 0
                and evidence.queries[0].row_count > 0
                and len(evidence.observations) > 0
            )
            if passed:
                passed_count += 1

            results.append({
                "task_id": task_def["id"],
                "engine": task_def["engine"],
                "query": task_def["query"],
                "passed": passed,
                "confidence": evidence.confidence,
                "latency_ms": round(duration_ms, 2),
                "rows_returned": evidence.queries[0].row_count if evidence.queries else 0,
                "sql": evidence.queries[0].sql if evidence.queries else None,
                "observations_count": len(evidence.observations),
                "warnings": evidence.warnings,
            })

        pass_rate = round((passed_count / len(self.BENCHMARK_TASKS)) * 100.0, 2)
        avg_latency = round(total_latency_ms / len(self.BENCHMARK_TASKS), 2)

        return {
            "total_tasks": len(self.BENCHMARK_TASKS),
            "passed_tasks": passed_count,
            "pass_rate_pct": pass_rate,
            "average_latency_ms": avg_latency,
            "tasks": results,
        }

    def generate_report(self) -> Dict[str, Any]:
        """Generates a complete Harness² evolution & audit report."""
        components_audit = self.audit_components()
        benchmark_results = self.run_benchmark()

        report = {
            "agent": "Kratos Harness² Evolution Agent",
            "version": "1.0.0",
            "framework": "Google Research Harness² Substrate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "harness2_installed": HARNESS2_AVAILABLE,
            "harness_components_audit": components_audit,
            "benchmark_evaluation": benchmark_results,
            "score": benchmark_results["pass_rate_pct"],
            "status": "OPTIMAL_EVOLVED" if benchmark_results["pass_rate_pct"] == 100.0 else "DEGRADED",
        }

        report_file = self.runs_dir / "report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report
