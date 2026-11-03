"""Kratos Command Line Interface (CLI)."""

import argparse
import sys
import uvicorn
from pathlib import Path
from kratos.engines.registry import EngineRegistry
from kratos.agents.orchestrator import InterpreterAgent, InvestigatorAgent
from kratos.contracts.schemas import DataTask


def main():
    parser = argparse.ArgumentParser(
        prog="kratos",
        description="Kratos Sovereign Data Intelligence & Governance Platform"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Server subcommand
    serve_parser = subparsers.add_parser("serve", help="Launch Kratos API and interactive web console")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable code hot reloading")

    # Ask subcommand
    ask_parser = subparsers.add_parser("ask", help="Query a database engine using natural language")
    ask_parser.add_argument("query", help="Natural language question to ask")
    ask_parser.add_argument("--engine", default="northwind", help="Database engine ID (default: northwind)")

    # Harness subcommand
    harness_parser = subparsers.add_parser("harness", help="Execute Harness² recursive evaluation benchmark")
    harness_parser.add_argument("--audit-only", action="store_true", help="Only audit the 8 harness components")

    args = parser.parse_args()

    if args.command == "serve":
        print(f"🚀 Launching Kratos Web Console on http://{args.host}:{args.port}")
        uvicorn.run("kratos.api.main:app", host=args.host, port=args.port, reload=args.reload)

    elif args.command == "ask":
        base_dir = Path(__file__).resolve().parent.parent
        data_dir = base_dir / "data"

        registry = EngineRegistry(data_dir)
        interpreter = InterpreterAgent()
        investigator = InvestigatorAgent(registry)

        interpreted = interpreter.interpret(args.query, args.engine)
        task = DataTask(
            intent=interpreted.intent,
            engine_id=args.engine,
            goal=interpreted.goal,
            constraints=interpreted.constraints,
            required_evidence=interpreted.required_evidence,
        )

        evidence = investigator.execute_task(task)
        story = interpreter.formulate_storytelling(task, evidence)

        print("\n" + "=" * 60)
        print(f"🛡️  KRATOS INTELLIGENCE REPORT [{args.engine.upper()}]")
        print("=" * 60)
        print(f"\n📌 CONCLUSIÓN EJECUTIVA:\n{story.key_takeaway}\n")
        print("📊 HALLAZGOS CUANTITATIVOS:")
        for f in story.quantitative_findings:
            print(f"  • {f}")
        print("\n💡 RECOMENDACIONES ESTRATÉGICAS:")
        for r in story.strategic_recommendations:
            print(f"  • {r}")

        if evidence.queries:
            q = evidence.queries[0]
            print(f"\n🔍 SQL EJECUTADO (AST VALIDADO):\n{q.sql}")
            print(f"⚡ Latencia: {q.execution_ms} ms | Filas: {q.row_count}\n")
        print("=" * 60 + "\n")

    elif args.command == "harness":
        from kratos.harness.agent import KratosHarness2Agent

        agent = KratosHarness2Agent()
        print("\n" + "=" * 65)
        print("🚀 KRATOS HARNESS² RECURSIVE BENCHMARK & EVOLUTION SUBSTRATE")
        print("=" * 65)

        if args.audit_only:
            audit = agent.audit_components()
            print("\n📋 AUDITORÍA DE COMPONENTES DE ARNÉS:")
            for cid, meta in audit.items():
                icon = "✅" if meta["status"] == "HEALTHY_PRESENT" else "❌"
                print(f"  {icon} {meta['name']} [{meta['path']}]: {meta['status']} ({meta['size_bytes']} bytes)")
            print("=" * 65 + "\n")
            return

        report = agent.generate_report()
        eval_data = report["benchmark_evaluation"]
        print(f"\n🎯 PUNTUACIÓN GENERAL: {report['score']}% [{report['status']}]")
        print(f"⏱️  Latencia Promedio: {eval_data['average_latency_ms']} ms")
        print(f"📊 Tareas Exitosas: {eval_data['passed_tasks']} / {eval_data['total_tasks']}\n")

        print("📋 DETALLE DE TAREAS:")
        for t in eval_data["tasks"]:
            icon = "✅" if t["passed"] else "❌"
            print(f"  {icon} [{t['engine'].upper()}] {t['query']} ({t['latency_ms']} ms, {t['rows_returned']} filas)")

        print(f"\n💾 Reporte completo guardado en: runs/harness2/report.json")
        print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
