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
    serve_parser.add_argument("--port", type=int, default=8888, help="Port to listen on (default: 8888)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable code hot reloading")

    # Ask subcommand
    ask_parser = subparsers.add_parser("ask", help="Query a database engine using natural language")
    ask_parser.add_argument("query", help="Natural language question to ask")
    ask_parser.add_argument("--engine", default="northwind", help="Database engine ID (default: northwind)")

    # Harness subcommand
    harness_parser = subparsers.add_parser("harness", help="Execute Harness² recursive evaluation benchmark")
    harness_parser.add_argument("--audit-only", action="store_true", help="Only audit the 8 harness components")

    # Info subcommand
    info_parser = subparsers.add_parser("info", help="Display discovered analytical database engines and tables")

    # Ontology subcommand
    ontology_parser = subparsers.add_parser("ontology", help="Inspect or generate Auto-Ontology for a database engine")
    ontology_parser.add_argument("engine", help="Database engine ID (e.g. northwind, chinook, sakila)")
    ontology_parser.add_argument("--export", help="Export auto-generated Wren MDL YAML to specified file path")

    # Check Answerability subcommand
    check_parser = subparsers.add_parser("check", help="Verify if a natural language query is answerable by the ontology")
    check_parser.add_argument("query", help="Natural language query to test")
    check_parser.add_argument("--engine", default="northwind", help="Database engine ID (default: northwind)")

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
            analytical_pattern=interpreted.analytical_pattern,
            time_granularity=interpreted.time_granularity,
            time_dimension=interpreted.time_dimension,
            series_dimension=interpreted.series_dimension,
            metric_target=interpreted.metric_target,
            dimensions=interpreted.dimensions,
            metrics=interpreted.metrics,
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

    elif args.command == "info":
        base_dir = Path(__file__).resolve().parent.parent
        data_dir = base_dir / "data"
        registry = EngineRegistry(data_dir)
        registry.discover()

        print("\n" + "=" * 65)
        print("🛡️  KRATOS MULTI-ENGINE DATABASE INVENTORY")
        print("=" * 65)
        print(f"Directorio de datos: {data_dir}")
        print(f"Motor activo por defecto: {registry.active_engine_id}\n")

        for eid, eng in registry.engines.items():
            tables = eng.get_tables()
            active_marker = "🌟 [ACTIVO]" if eid == registry.active_engine_id else ""
            print(f"📁 Motor: {eid.upper()} ({len(tables)} tablas) {active_marker}")
            print(f"   Tablas: {', '.join(tables[:8])}{'...' if len(tables) > 8 else ''}")
        print("=" * 65 + "\n")

    elif args.command == "ontology":
        base_dir = Path(__file__).resolve().parent.parent
        data_dir = base_dir / "data"
        registry = EngineRegistry(data_dir)
        eng = registry.engines.get(args.engine)
        if not eng:
            print(f"❌ Error: Motor '{args.engine}' no encontrado en {data_dir}.")
            sys.exit(1)

        from kratos.ontology.auto_ontology import AutoOntologyService
        print(f"\n🧠 Introspeccionando y Extrayendo Auto-Ontología para '{args.engine}'...")
        model = AutoOntologyService.generate_for_engine(eng)

        print("=" * 65)
        print(f"🌐 AUTO-ONTOLOGY: {model.name}")
        print(f"📝 {model.description}")
        print("=" * 65)
        print(f"📊 Entidades ({len(model.entities)}): {', '.join([e.name for e in model.entities[:8]])}")
        print(f"🔗 Relaciones FK ({len(model.relationships)} rutas de JOIN)")
        print(f"📐 Dimensiones ({len(model.dimensions)} analíticas): {', '.join([d.id for d in model.dimensions[:6]])}")
        print(f"📈 Métricas ({len(model.metrics)} medidas de negocio): {', '.join([m.id for m in model.metrics])}")

        if args.export:
            export_path = Path(args.export)
            AutoOntologyService.export_to_yaml(model, export_path)
            print(f"\n💾 Ontología exportada exitosamente a: {export_path}")
        print("=" * 65 + "\n")

    elif args.command == "check":
        base_dir = Path(__file__).resolve().parent.parent
        data_dir = base_dir / "data"
        registry = EngineRegistry(data_dir)
        eng = registry.engines.get(args.engine)
        if not eng:
            print(f"❌ Error: Motor '{args.engine}' no encontrado.")
            sys.exit(1)

        from kratos.semantics.mdl import SemanticCatalog
        from kratos.ontology.grounder import AutoOntologyGrounder
        catalog = SemanticCatalog()
        model = catalog.get_model(args.engine)
        if not model:
            from kratos.ontology.auto_ontology import AutoOntologyService
            model = AutoOntologyService.generate_for_engine(eng)

        res = AutoOntologyGrounder.check_answerable(args.query, model)
        print("\n" + "=" * 65)
        print(f"🔍 AUTO-ONTOLOGY ANSWERABILITY CHECK // Motor: {args.engine}")
        print(f"❓ Consulta: '{args.query}'")
        print("=" * 65)
        icon = "✅ RESPONDIBLE" if res.is_answerable else "❌ NO RESPONDIBLE (FUERA DE ALCANCE)"
        print(f"Estado: {icon} (Confianza: {int(res.confidence * 100)}%)")
        print(f"Explicación: {res.reason}")
        if res.missing_concepts:
            print(f"⚠️  Conceptos Faltantes en el Esquema: {', '.join(res.missing_concepts)}")
        if res.matched_dimensions:
            print(f"📐 Dimensiones Identificadas: {', '.join(res.matched_dimensions)}")
        if res.matched_metrics:
            print(f"📈 Métricas Identificadas: {', '.join(res.matched_metrics)}")
        print("=" * 65 + "\n")



if __name__ == "__main__":
    main()
