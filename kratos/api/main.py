"""Kratos FastAPI Web Application & Sovereign API Endpoints."""

from pathlib import Path
import json
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from kratos.engines.registry import EngineRegistry
from kratos.agents.orchestrator import InterpreterAgent, InvestigatorAgent
from kratos.contracts.schemas import DataTask, FinalAnswer
from kratos.semantics.bi_engine import compile_echarts
from kratos.semantics.archify_generator import generate_archify_erd_spec, compile_archify_diagram, enrich_entities_for_ui
from kratos.web.docs_page import get_documentation_html
from kratos.web.database_docs import DATABASE_CATALOG, get_database_doc, get_all_database_docs

app = FastAPI(title="Kratos Intelligence", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

registry = EngineRegistry(DATA_DIR)
interpreter = InterpreterAgent()
investigator = InvestigatorAgent(registry)

latest_archify_diagram: dict[str, str] = {"html": ""}


class QueryRequest(BaseModel):
    query: str
    engine_id: str | None = None


class AnswerabilityRequest(BaseModel):
    query: str
    engine_id: str


@app.get("/api/ontology/{engine_id}")
def get_engine_ontology(engine_id: str):
    """Returns the full semantic ontology graph for the specified engine."""
    model = interpreter.semantic_catalog.get_model(engine_id)
    if not model:
        eng = registry.engines.get(engine_id)
        if eng:
            from kratos.ontology.auto_ontology import AutoOntologyService
            model = AutoOntologyService.generate_for_engine(eng)
    if not model:
        raise HTTPException(status_code=404, detail=f"Ontología no disponible para '{engine_id}'")
    return {
        "engine_id": model.engine_id,
        "name": model.name,
        "description": model.description,
        "entities_count": len(model.entities),
        "relationships_count": len(model.relationships),
        "dimensions_count": len(model.dimensions),
        "metrics_count": len(model.metrics),
        "entities": [e.model_dump() for e in model.entities],
        "relationships": [r.model_dump() for r in model.relationships],
        "dimensions": [d.model_dump() for d in model.dimensions],
        "metrics": [m.model_dump() for m in model.metrics],
    }


@app.post("/api/ontology/check-answerable")
def check_query_answerability(req: AnswerabilityRequest):
    """Evaluates whether a natural language question can be answered by the certified ontology."""
    model = interpreter.semantic_catalog.get_model(req.engine_id)
    if not model:
        eng = registry.engines.get(req.engine_id)
        if eng:
            from kratos.ontology.auto_ontology import AutoOntologyService
            model = AutoOntologyService.generate_for_engine(eng)
    if not model:
        raise HTTPException(status_code=404, detail=f"Motor '{req.engine_id}' no encontrado.")

    from kratos.ontology.grounder import AutoOntologyGrounder
    result = AutoOntologyGrounder.check_answerable(req.query, model)
    return result.model_dump()


@app.get("/api/health")
@app.get("/health")
def health():
    return {"status": "ok", "project": "kratos", "engines_available": list(registry.engines.keys())}


@app.get("/api/engines")
def list_engines():
    registry.discover()
    return {
        "active": registry.active_engine_id,
        "engines": [
            {
                "id": eid,
                "tables_count": len(eng.get_tables()),
                "tables": eng.get_tables()[:8],
                "is_active": (eid == registry.active_engine_id),
            }
            for eid, eng in registry.engines.items()
        ]
    }


@app.post("/api/engines/select")
def select_engine(payload: dict):
    engine_id = payload.get("engine_id")
    if not engine_id:
        raise HTTPException(status_code=400, detail="Debe especificar el campo 'engine_id'")
    try:
        registry.set_active(engine_id)
        return {"ok": True, "active": registry.active_engine_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/schema")
def get_schema():
    active = registry.get_active()
    return {"engine_id": active.engine_id, "schema": active.introspect()}


@app.get("/api/databases/catalog")
def api_database_catalog():
    return {"catalog": get_all_database_docs()}


@app.get("/api/databases/{engine_id}/docs")
def api_database_docs(engine_id: str):
    doc = get_database_doc(engine_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Base de datos '{engine_id}' no encontrada en el catálogo")
    return doc


@app.post("/api/query")
def run_query(req: QueryRequest):
    engine_id = req.engine_id or registry.active_engine_id
    if engine_id not in registry.engines:
        registry.discover()
    if engine_id not in registry.engines:
        raise HTTPException(
            status_code=404,
            detail=f"El motor '{engine_id}' no está registrado en Kratos. Motores disponibles: {list(registry.engines.keys())}"
        )

    # Step 1: Interpreter parses request
    interpreted = interpreter.interpret(req.query, engine_id)

    # Step 2: Formal DataTask creation
    task = DataTask(
        intent=interpreted.intent,
        engine_id=engine_id,
        goal=interpreted.goal,
        analytical_pattern=interpreted.analytical_pattern,
        time_granularity=interpreted.time_granularity,
        time_dimension=interpreted.time_dimension,
        series_dimension=interpreted.series_dimension,
        metric_target=interpreted.metric_target,
        top_n=interpreted.top_n,
        ranking_criterion=interpreted.ranking_criterion,
        filter_year=interpreted.filter_year,
        dimensions=interpreted.dimensions,
        metrics=interpreted.metrics,
        constraints=interpreted.constraints,
        required_evidence=interpreted.required_evidence,
    )

    # Step 3: Investigator executes task with 4-layer security
    evidence = investigator.execute_task(task)

    # Step 4: Storytelling & Visualization
    storytelling = interpreter.formulate_storytelling(task, evidence)
    rows = evidence.queries[0].rows if evidence.queries else []
    echarts = compile_echarts(rows, title=task.goal)

    # Step 5: Archify Relational Lineage & ERD Compilation
    has_archify = False
    archify_url = None
    archify_entities = []
    if evidence.queries:
        try:
            primary_sql = evidence.queries[0].sql
            engine_schema = registry.engines[task.engine_id].introspect()
            spec = generate_archify_erd_spec(primary_sql, task.engine_id, task.goal, engine_schema)
            compiled_html = compile_archify_diagram(spec)
            latest_archify_diagram["html"] = compiled_html
            has_archify = True
            archify_url = "/api/archify/latest.html"
            archify_entities = enrich_entities_for_ui(spec.get("entities", []), task.engine_id)
        except Exception as exc:
            print(f"[WARN] Archify diagram generation skipped: {exc}")

    return FinalAnswer(
        storytelling=storytelling,
        evidence=evidence,
        visualization=echarts,
        task=task,
        suggested_questions=[
            "Ver distribución por país",
            "Consultar top 5 entidades líderes",
            "Explorar resumen del esquema",
        ],
        has_archify=has_archify,
        archify_url=archify_url,
        archify_entities=archify_entities,
    )


@app.api_route("/api/archify/latest.html", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_latest_archify_html():
    content = latest_archify_diagram.get("html", "")
    if not content:
        content = "<html><body style='background:#0b0f19;color:#94a3b8;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'><p>Sin relaciones generadas para la consulta actual.</p></body></html>"
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


@app.api_route("/api/archify/engine/{engine_id}.html", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_engine_archify_html(engine_id: str):
    eid = engine_id.lower().strip()
    static_file = Path(__file__).resolve().parent.parent / "web" / "static" / "archify" / f"{eid}.html"
    if static_file.exists():
        content = static_file.read_text(encoding="utf-8")
        return HTMLResponse(content=content)

    # Dynamic generation fallback
    db_file = Path(__file__).resolve().parent.parent.parent / "data" / f"{eid}.db"
    if not db_file.exists():
        raise HTTPException(status_code=404, detail=f"Motor de base de datos '{engine_id}' no encontrado.")

    from kratos.semantics.archify_generator import generate_full_database_archify_erd_spec, compile_archify_diagram
    spec = generate_full_database_archify_erd_spec(eid, db_file)
    content = compile_archify_diagram(spec)
    static_file.parent.mkdir(parents=True, exist_ok=True)
    static_file.write_text(content, encoding="utf-8")
    return HTMLResponse(content=content)


@app.get("/api/geo/{map_name}.geojson")
def get_geo_json(map_name: str):
    m_name = map_name.lower().strip()
    geo_file = Path(__file__).resolve().parent.parent / "web" / "static" / "geo" / f"{m_name}.geojson"
    if not geo_file.exists():
        raise HTTPException(status_code=404, detail=f"Mapa GeoJSON '{map_name}' no encontrado.")
    return JSONResponse(
        content=json.loads(geo_file.read_text(encoding="utf-8")),
        headers={
            "Cache-Control": "public, max-age=86400",
        }
    )


@app.get("/documentation", response_class=HTMLResponse)
def documentation_page():
    content = get_documentation_html()
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


@app.get("/", response_class=HTMLResponse)
def index_page():
    html_content = r"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KRATOS // Sovereign Data Intelligence</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@4.9.0/map/js/world.js"></script>
    <!-- Prism.js for SQL Syntax Color Coding -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-sql.min.js"></script>
    <!-- Mermaid.js for Entity-Relationship Diagrams -->
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        body { background: #0b0f19; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .mermaid { background: #0f172a; padding: 1.25rem; border-radius: 0.75rem; border: 1px solid #1e293b; overflow-x: auto; }
        .mermaid svg { max-width: 100%; height: auto; margin: 0 auto; }
        /* SQL Syntax Color Tokens */
        .token.comment, .token.prolog, .token.doctype, .token.cdata {
            color: #64748b !important;
            font-style: italic !important;
        }
        .token.punctuation {
            color: #94a3b8 !important;
        }
        .token.keyword {
            color: #818cf8 !important;
            font-weight: 700 !important;
        }
        .token.function {
            color: #38bdf8 !important;
            font-weight: 600 !important;
        }
        .token.string {
            color: #34d399 !important;
        }
        .token.number {
            color: #fbbf24 !important;
        }
        .token.operator {
            color: #f472b6 !important;
        }
        .token.property, .token.class-name, .token.constant {
            color: #e2e8f0 !important;
        }
        /* Scrollbar styles */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0b0f19; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
    </style>
</head>
<body class="min-h-screen p-6 max-w-7xl mx-auto">
    <header class="flex flex-col md:flex-row justify-between items-start md:items-center pb-6 border-b border-slate-800 gap-4">
        <div>
            <div class="flex items-center gap-3">
                <span class="text-2xl">🛡️</span>
                <h1 class="text-3xl font-black tracking-wider text-white">KRATOS</h1>
                <span class="bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 text-xs px-2.5 py-1 rounded-full font-semibold">Sovereign Edition</span>
            </div>
            <p class="text-sm text-slate-400 mt-1">Sovereign Data Intelligence &bull; Contracts Protocol &bull; 4-Layer AST Security</p>
        </div>
        
        <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <nav class="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
                <a href="/" class="px-3 py-1 text-xs rounded-lg bg-indigo-600 text-white font-medium flex items-center gap-1">
                    <span>📊</span> Dashboard
                </a>
                <a href="/documentation" class="px-3 py-1 text-xs rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition flex items-center gap-1">
                    <span>📖</span> Documentación
                </a>
                <a href="/docs" target="_blank" class="px-3 py-1 text-xs rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition flex items-center gap-1">
                    <span>⚡</span> Swagger
                </a>
                <a href="https://github.com/aroylee/kratos" target="_blank" class="px-3 py-1 text-xs rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition flex items-center gap-1">
                    <span>🐙</span> GitHub
                </a>
            </nav>
        </div>
    </header>

    <!-- Barra de Selección de Motores Soberanos -->
    <div class="mt-6 bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-3 mb-3 border-b border-slate-800/80 gap-3">
            <div class="flex items-center gap-2">
                <span class="text-xs uppercase tracking-wider font-semibold text-slate-400">Motor Analítico Activo:</span>
                <span id="active-engine-badge" class="font-mono text-xs px-2.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold shadow-sm">Cargando...</span>
            </div>
            <!-- Link arriba del selector para explorar qué contiene la base de datos, ER general y ejemplos -->
            <button id="btn-open-db-docs" onclick="openDatabaseDocsModal(currentEngine)" class="text-xs text-indigo-300 hover:text-white font-semibold flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-950/70 hover:bg-indigo-900/80 border border-indigo-700/70 transition shadow-sm hover:shadow-indigo-500/20 group">
                <span class="text-sm">📖</span>
                <span class="underline decoration-indigo-400/60 group-hover:decoration-white">¿En qué consiste esta base de datos?</span>
                <span class="text-[11px] text-indigo-300/80 font-normal hidden sm:inline">(Qué contiene, ER General &amp; Ejemplos) &rarr;</span>
            </button>
        </div>
        <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
            <span class="text-[11px] text-slate-400">Selecciona el motor de datos para tu consulta:</span>
            <div id="engine-selector-container" class="flex flex-wrap gap-2"></div>
        </div>
    </div>

    <!-- Píldoras de Tablas del Motor -->
    <div id="tables-container" class="mt-3 flex flex-wrap gap-1.5 text-xs text-slate-400"></div>

    <!-- Alert / Feedback Banner -->
    <div id="alert-banner" class="hidden mt-4 p-3 rounded-xl border text-sm flex items-center justify-between transition">
        <div id="alert-content" class="flex items-center gap-2"></div>
        <button onclick="dismissAlert()" class="text-slate-400 hover:text-white font-bold px-2 py-0.5 rounded">&times;</button>
    </div>

    <main class="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        <!-- Columna Izquierda: Entrada y Auditoría -->
        <section class="lg:col-span-1 space-y-4">
            <!-- Tarjeta 1: Entrada de Consulta -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
                <div class="flex justify-between items-center p-3.5 bg-slate-900 border-b border-slate-800/80 cursor-pointer select-none hover:bg-slate-850 transition" onclick="toggleCardCollapse('query-card')">
                    <div class="flex items-center gap-2">
                        <span class="text-indigo-400 text-sm">💬</span>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-slate-300 pointer-events-none">Consulta en Lenguaje Natural</label>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-[10px] text-slate-500 font-mono hidden sm:inline mr-1">Enter ↵</span>
                        <button onclick="event.stopPropagation(); openFullscreen('query')" title="Maximizar Ventana (⛶)" class="text-slate-400 hover:text-white text-xs font-mono px-1.5 py-0.5 rounded hover:bg-slate-800 transition">⛶</button>
                        <button id="toggle-query-card" title="Colapsar / Expandir" class="text-slate-400 hover:text-white text-xs font-mono px-1.5 py-0.5 rounded hover:bg-slate-800 transition">▼</button>
                    </div>
                </div>
                <div id="body-query-card" class="p-4 transition-all">
                    <textarea id="query-input" rows="3" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm focus:outline-none focus:border-indigo-500" placeholder="Ej: dame las ventas por país en el mundo"></textarea>
                    
                    <!-- Chips de Contrato Interpretado (Grounding) -->
                    <div id="contract-chips" class="mt-2 empty:hidden flex flex-wrap gap-1.5 text-[11px]"></div>

                    <!-- Chips de Preguntas Rápidas -->
                    <div class="mt-2.5 flex flex-wrap gap-1.5" id="sample-chips">
                        <button onclick="setQuery('ventas por país')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">🗺️ Ventas por país</button>
                        <button onclick="setQuery('ventas por categoría')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Ventas por categoría</button>
                        <button onclick="setQuery('tendencia de ventas diaria por categoría de las 3 categorías con mejor desempeño')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Top 3 Categorías diario</button>
                    </div>

                    <button id="run-btn" onclick="executeQuery()" class="mt-3 w-full bg-indigo-600 hover:bg-indigo-500 font-medium py-2 rounded-lg text-sm transition flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20">
                        <span>⚡</span> Ejecutar Análisis
                    </button>
                </div>
            </div>

            <!-- Tarjeta 2: Resumen Ejecutivo (Storytelling) -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
                <div class="flex justify-between items-center p-3.5 bg-slate-900 border-b border-slate-800/80 cursor-pointer select-none hover:bg-slate-850 transition" onclick="toggleCardCollapse('storytelling-card')">
                    <div class="flex items-center gap-2">
                        <span class="text-amber-400 text-sm">📑</span>
                        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-300">Resumen Ejecutivo (Storytelling)</h3>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <button onclick="event.stopPropagation(); openFullscreen('storytelling')" title="Maximizar Ventana (⛶)" class="text-slate-400 hover:text-white text-xs font-mono px-1.5 py-0.5 rounded hover:bg-slate-800 transition">⛶</button>
                        <button id="toggle-storytelling-card" title="Colapsar / Expandir" class="text-slate-400 hover:text-white text-xs font-mono px-1.5 py-0.5 rounded hover:bg-slate-800 transition">▼</button>
                    </div>
                </div>
                <div id="body-storytelling-card" class="p-4 transition-all">
                    <div id="storytelling-container" class="text-sm space-y-2 text-slate-300">
                        <p class="text-slate-500 italic">Escribe una pregunta o selecciona un chip y presiona ejecutar.</p>
                    </div>
                </div>
            </div>

            <!-- Tarjeta 3: Preguntas Analíticas Sugeridas -->
            <div id="suggested-container" class="hidden bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
                <div class="flex justify-between items-center p-3.5 bg-slate-900 border-b border-slate-800/80 cursor-pointer select-none hover:bg-slate-850 transition" onclick="toggleCardCollapse('suggested-card')">
                    <div class="flex items-center gap-2">
                        <span class="text-indigo-400 text-sm">💡</span>
                        <h3 class="text-xs font-semibold uppercase tracking-wider text-indigo-300">Preguntas Analíticas Sugeridas</h3>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <button onclick="event.stopPropagation(); openFullscreen('suggested')" title="Maximizar Ventana (⛶)" class="text-slate-400 hover:text-white text-xs font-mono px-1.5 py-0.5 rounded hover:bg-slate-800 transition">⛶</button>
                        <button id="toggle-suggested-card" title="Colapsar / Expandir" class="text-slate-400 hover:text-white text-xs font-mono px-1.5 py-0.5 rounded hover:bg-slate-800 transition">▼</button>
                    </div>
                </div>
                <div id="body-suggested-card" class="p-4 transition-all">
                    <div id="suggested-chips" class="flex flex-wrap gap-1.5 text-xs"></div>
                </div>
            </div>

            <!-- Tarjeta 4: Auditoría DataTask & 4-Layer AST -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
                <div class="flex justify-between items-center p-3.5 bg-slate-900 border-b border-slate-800/80 cursor-pointer select-none hover:bg-slate-850 transition" onclick="toggleCardCollapse('audit-card')">
                    <div class="flex items-center gap-2">
                        <span class="text-emerald-400 text-sm">🛡️</span>
                        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-300">Auditoría DataTask & 4-Layer AST</h3>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <button onclick="event.stopPropagation(); copyCurrentSql()" title="Copiar SQL" class="copy-sql-btn text-slate-400 hover:text-indigo-300 text-xs px-2 py-0.5 rounded bg-slate-950 border border-slate-800 hover:border-slate-700 transition flex items-center gap-1">
                            <span>📋</span> Copiar
                        </button>
                        <button onclick="event.stopPropagation(); openFullscreen('audit')" title="Maximizar Ventana (⛶)" class="text-slate-400 hover:text-white text-xs font-mono px-1.5 py-0.5 rounded hover:bg-slate-800 transition">⛶</button>
                        <button id="toggle-audit-card" title="Colapsar / Expandir" class="text-slate-400 hover:text-white text-xs font-mono px-1.5 py-0.5 rounded hover:bg-slate-800 transition">▼</button>
                    </div>
                </div>
                <div id="body-audit-card" class="p-4 transition-all">
                    <div id="audit-container" class="text-xs font-mono space-y-1 text-slate-400 overflow-x-auto">
                        <p class="text-slate-600">Sin ejecuciones recientes.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- Columna Derecha: Gráficos y Tablas -->
        <section class="lg:col-span-2 space-y-4">
            <!-- Tarjeta 5: Gráfico con Controles Interactivos -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3.5 bg-slate-900 border-b border-slate-800/80 gap-2">
                    <div class="flex items-center gap-2 cursor-pointer select-none" onclick="toggleCardCollapse('chart-card')">
                        <span class="text-indigo-400 text-sm">📈</span>
                        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-300">Visualización Analítica Interactiva</h3>
                        <span id="chart-type-badge" class="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-400 border border-indigo-800">ECharts 5</span>
                        <button id="toggle-chart-card" class="text-slate-400 hover:text-white text-xs font-mono px-1 py-0.5 rounded hover:bg-slate-800 ml-1">▼</button>
                    </div>
                    <div class="flex items-center gap-1.5 flex-wrap">
                        <button onclick="changeChartType('map')" id="btn-chart-map" class="chart-type-btn hidden px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition flex items-center gap-1">🗺️ Mapa</button>
                        <button onclick="changeChartType('line')" id="btn-chart-line" class="chart-type-btn px-2.5 py-1 text-xs rounded bg-indigo-600 border border-indigo-500 text-white font-medium transition shadow-sm">📈 Línea</button>
                        <button onclick="changeChartType('bar')" id="btn-chart-bar" class="chart-type-btn px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">📊 Barra</button>
                        <button onclick="changeChartType('area')" id="btn-chart-area" class="chart-type-btn px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">🏔️ Área</button>
                        <button onclick="downloadChartImage()" title="Descargar Imagen PNG" class="px-2 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-600 transition flex items-center gap-1">
                            <span>📸</span> PNG
                        </button>
                        <button onclick="openFullscreen('chart')" title="Maximizar Ventana (⛶)" class="px-2 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-indigo-300 hover:text-white hover:border-indigo-600 transition flex items-center gap-1">
                            <span>⛶</span>
                        </button>
                    </div>
                </div>
                <div id="body-chart-card" class="p-4 transition-all">
                    <div id="chart-container" style="height: 400px; width: 100%;"></div>
                </div>
            </div>

            <!-- Tarjeta 6: Relaciones y Linaje de la Consulta (Archify ERD) -->
            <div id="archify-card" class="bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3.5 bg-slate-900 border-b border-slate-800/80 gap-2">
                    <div class="flex items-center gap-2 cursor-pointer select-none" onclick="toggleCardCollapse('archify-card')">
                        <span class="text-sky-400 text-sm">🕸️</span>
                        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-300">Relaciones & Esquema ERD (Archify)</h3>
                        <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950/80 text-sky-400 border border-sky-800">Archify 3.2</span>
                        <span id="archify-entity-count-badge" class="hidden text-[10px] font-mono px-2 py-0.5 rounded bg-slate-950 text-sky-300 border border-slate-800"></span>
                        <button id="toggle-archify-card" title="Colapsar / Expandir" class="text-slate-400 hover:text-white text-xs font-mono px-1 py-0.5 rounded hover:bg-slate-800 ml-1">▼</button>
                    </div>
                    <div class="flex items-center gap-1.5 flex-wrap">
                        <div class="flex bg-slate-950 rounded-lg p-0.5 border border-slate-800 text-xs">
                            <button id="btn-archify-tab-visual" onclick="switchArchifyCardTab('visual')" class="px-2.5 py-1 rounded text-sky-400 font-medium bg-slate-900 border border-sky-900/50 transition flex items-center gap-1">
                                <span>🗺️</span> <span class="hidden sm:inline">Diagrama ERD</span>
                            </button>
                            <button id="btn-archify-tab-inspector" onclick="switchArchifyCardTab('inspector')" class="px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition flex items-center gap-1">
                                <span>📋</span> <span class="hidden sm:inline">Inspector de Atributos</span>
                            </button>
                        </div>
                        <a id="btn-archify-external" href="/api/archify/latest.html" target="_blank" title="Abrir en Nueva Pestaña" class="px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-600 transition flex items-center gap-1">
                            <span>↗</span> <span class="hidden sm:inline">Pestaña</span>
                        </a>
                        <button onclick="openFullscreen('archify')" title="Maximizar Ventana (⛶)" class="px-2 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-sky-300 hover:text-white hover:border-sky-600 transition flex items-center gap-1">
                            <span>⛶</span>
                        </button>
                    </div>
                </div>
                <div id="body-archify-card" class="p-2 transition-all">
                    <!-- Vista 1: Diagrama Visual Archify -->
                    <div id="archify-visual-view">
                        <div id="archify-container" class="w-full h-[460px] bg-slate-950 rounded-lg overflow-hidden border border-slate-800/80 flex items-center justify-center">
                            <p class="text-slate-600 text-xs italic">Ejecuta una consulta para visualizar sus relaciones relacionales e integridad con Archify.</p>
                        </div>
                        <div class="flex items-center justify-between text-[11px] text-slate-500 px-2 pt-2">
                            <span>💡 Tip: Usa rueda/scroll para zoom, arrastra para mover el lienzo, o haz clic en cualquier entidad para enfocarla.</span>
                            <span class="text-slate-400 font-mono text-[10px]">100% atributos renderizados</span>
                        </div>
                    </div>

                    <!-- Vista 2: Inspector de Atributos con Scroll y Filtro -->
                    <div id="archify-inspector-view" class="hidden flex flex-col gap-2 p-1">
                        <div class="flex flex-col sm:flex-row items-center justify-between gap-2 bg-slate-950/80 p-2 rounded-lg border border-slate-800">
                            <div class="relative w-full sm:w-72">
                                <input type="text" id="archify-attr-filter" oninput="filterArchifyAttributes()" placeholder="🔍 Filtrar columnas o tablas..." class="w-full bg-slate-900 border border-slate-800 text-slate-300 rounded px-2.5 py-1 text-xs focus:outline-none focus:border-sky-500">
                            </div>
                            <div class="flex items-center gap-2 text-xs">
                                <span id="archify-filter-stats" class="text-slate-400 font-mono text-[11px]"></span>
                                <button onclick="expandAllArchifyEntities(true, 'archify-inspector-cards')" class="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition">↕ Expandir Todo</button>
                                <button onclick="expandAllArchifyEntities(false, 'archify-inspector-cards')" class="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition">⇥ Colapsar Todo</button>
                            </div>
                        </div>
                        <div id="archify-inspector-cards" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[460px] overflow-y-auto p-1 custom-scrollbar">
                            <p class="text-slate-600 text-xs italic p-3">Ejecuta una consulta para inspeccionar los atributos y claves de las entidades.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tarjeta 7: Tabla de Evidencias con Búsqueda y Exportación -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3.5 bg-slate-900 border-b border-slate-800/80 gap-2">
                    <div class="flex items-center gap-2 cursor-pointer select-none" onclick="toggleCardCollapse('table-card')">
                        <span class="text-emerald-400 text-sm">📋</span>
                        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-300">Registros de Evidencia Auditada</h3>
                        <span id="table-row-count-badge" class="hidden text-[11px] font-mono bg-slate-950 text-slate-400 px-2 py-0.5 rounded border border-slate-800"></span>
                        <button id="toggle-table-card" class="text-slate-400 hover:text-white text-xs font-mono px-1 py-0.5 rounded hover:bg-slate-800 ml-1">▼</button>
                    </div>
                    <div class="flex items-center gap-2 w-full sm:w-auto">
                        <div class="relative flex-1 sm:w-48">
                            <input type="text" id="table-search-input" oninput="filterTableRows()" placeholder="🔍 Filtrar registros..." class="w-full bg-slate-950 border border-slate-800 text-slate-300 rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:border-indigo-500">
                        </div>
                        <button onclick="exportTableToCSV()" class="px-2.5 py-1 text-xs rounded-lg bg-slate-950 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-600 transition flex items-center gap-1">
                            <span>📥</span> CSV
                        </button>
                        <button onclick="openFullscreen('table')" title="Maximizar Ventana (⛶)" class="px-2 py-1 text-xs rounded-lg bg-slate-950 border border-slate-800 text-indigo-300 hover:text-white hover:border-indigo-600 transition flex items-center gap-1">
                            <span>⛶</span>
                        </button>
                    </div>
                </div>
                <div id="body-table-card" class="p-4 transition-all">
                    <div id="table-container" class="text-xs overflow-x-auto">
                        <p class="text-slate-600 p-2 italic">Sin registros cargados.</p>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <!-- Modal de Pantalla Completa / Ventana Maximizada (⛶) -->
    <div id="fullscreen-modal" class="hidden fixed inset-0 z-50 bg-slate-950/95 backdrop-blur-md p-4 sm:p-6 flex flex-col justify-between">
        <div class="flex items-center justify-between pb-3.5 border-b border-slate-800">
            <div class="flex items-center gap-2.5">
                <span id="modal-icon" class="text-xl">📈</span>
                <div>
                    <h2 id="modal-title" class="text-sm sm:text-base font-bold text-white tracking-wide">Ventana Maximizada</h2>
                    <p id="modal-subtitle" class="text-[11px] text-slate-400 font-mono">KRATOS SOVEREIGN WORKSPACE</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <div id="modal-actions" class="flex items-center gap-1.5 flex-wrap"></div>
                <button onclick="closeFullscreen()" title="Restaurar / Cerrar (ESC)" class="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-700 text-slate-300 hover:text-white hover:border-rose-500 hover:bg-rose-950/40 text-xs font-semibold flex items-center gap-1 transition">
                    <span>✕</span> <span class="hidden sm:inline">Cerrar</span> <kbd class="text-[10px] bg-slate-950 px-1 py-0.5 rounded border border-slate-800 ml-1">ESC</kbd>
                </button>
            </div>
        </div>

        <!-- Modal Body Container -->
        <div id="modal-content" class="flex-1 my-3 overflow-auto flex flex-col">
            <div id="modal-chart-view" class="w-full h-full min-h-[500px] hidden flex-1">
                <div id="modal-chart-container" class="w-full h-full min-h-[500px]"></div>
            </div>
            <div id="modal-generic-view" class="w-full h-full overflow-auto hidden"></div>
        </div>

        <div class="text-[11px] text-slate-500 flex justify-between items-center pt-2.5 border-t border-slate-800/80 font-mono">
            <span id="modal-footer-info">KRATOS Sovereign Data Intelligence &bull; Modo Ventana Maximizada</span>
            <span>Usa <kbd class="px-1.5 py-0.5 bg-slate-900 border border-slate-800 rounded text-slate-300">ESC</kbd> para volver al dashboard</span>
        </div>
    </div>

    <!-- Modal de Documentación de Base de Datos (Kaggle & ER General) -->
    <div id="database-docs-modal" class="hidden fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-md p-3 sm:p-6 flex items-center justify-center overflow-y-auto">
        <div class="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-fadeIn">
            <!-- Modal Header -->
            <div class="p-4 sm:p-5 border-b border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-slate-950/70">
                <div class="flex items-center gap-3">
                    <span id="db-modal-emoji" class="text-3xl p-2 rounded-xl bg-slate-900 border border-slate-800">🗄️</span>
                    <div>
                        <div class="flex items-center gap-2">
                            <h2 id="db-modal-title" class="text-base sm:text-lg font-bold text-white tracking-wide">Explorador de Bases de Datos</h2>
                            <span id="db-modal-badge" class="text-xs font-mono font-bold bg-indigo-950 text-indigo-300 px-2 py-0.5 rounded border border-indigo-800">NORTHWIND</span>
                        </div>
                        <p id="db-modal-subtitle" class="text-xs text-slate-400 mt-0.5">Qué contiene, cómo se relacionan sus tablas y cómo consultarla en lenguaje natural</p>
                    </div>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto justify-end">
                    <a id="db-modal-docs-link" href="/documentation#databases" target="_blank" class="px-3 py-1.5 text-xs rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white transition flex items-center gap-1.5 font-medium">
                        <span>📖</span> Documentación Completa &nearr;
                    </a>
                    <button onclick="closeDatabaseDocsModal()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-rose-950/60 text-slate-300 hover:text-rose-200 border border-slate-700 hover:border-rose-700 text-xs font-semibold flex items-center gap-1 transition">
                        <span>✕</span> Cerrar <kbd class="text-[10px] bg-slate-950 px-1 py-0.5 rounded border border-slate-800 ml-1">ESC</kbd>
                    </button>
                </div>
            </div>

            <!-- Tabs de Selección de Motores -->
            <div class="px-4 py-2.5 bg-slate-950/90 border-b border-slate-800/80 flex items-center gap-2 overflow-x-auto text-xs">
                <span class="text-slate-500 font-semibold mr-1 shrink-0">Seleccionar Base:</span>
                <button onclick="switchDatabaseDocsTab('northwind')" id="db-tab-northwind" class="db-tab px-3 py-1 rounded-lg font-medium transition border flex items-center gap-1.5 bg-indigo-600 border-indigo-500 text-white">
                    <span>🚢</span> Northwind
                </button>
                <button onclick="switchDatabaseDocsTab('chinook')" id="db-tab-chinook" class="db-tab px-3 py-1 rounded-lg font-medium transition border flex items-center gap-1.5 bg-slate-900 border-slate-800 text-slate-400 hover:text-white">
                    <span>🎧</span> Chinook
                </button>
                <button onclick="switchDatabaseDocsTab('sakila')" id="db-tab-sakila" class="db-tab px-3 py-1 rounded-lg font-medium transition border flex items-center gap-1.5 bg-slate-900 border-slate-800 text-slate-400 hover:text-white">
                    <span>🎬</span> Sakila
                </button>
                <button onclick="switchDatabaseDocsTab('adventureworks_dw')" id="db-tab-adventureworks_dw" class="db-tab px-3 py-1 rounded-lg font-medium transition border flex items-center gap-1.5 bg-slate-900 border-slate-800 text-slate-400 hover:text-white">
                    <span>🚲</span> AdventureWorks DW
                </button>
                <button onclick="switchDatabaseDocsTab('tpch')" id="db-tab-tpch" class="db-tab px-3 py-1 rounded-lg font-medium transition border flex items-center gap-1.5 bg-slate-900 border-slate-800 text-slate-400 hover:text-white">
                    <span>🌐</span> TPC-H
                </button>
            </div>

            <!-- Modal Body Scrollable -->
            <div id="db-modal-body" class="p-4 sm:p-6 overflow-y-auto space-y-6 flex-1 text-slate-300 text-sm">
                <!-- Se llena dinámicamente con JavaScript -->
            </div>

            <!-- Modal Footer -->
            <div class="p-3 bg-slate-950 border-t border-slate-800 text-xs flex flex-col sm:flex-row justify-between items-center gap-2 text-slate-500">
                <span id="db-modal-footer-tip" class="flex items-center gap-1.5">
                    <span>💡</span> Haz clic en <strong class="text-indigo-400">⚡ Probar Consulta</strong> para aplicarla automáticamente al dashboard.
                </span>
                <span class="font-mono text-[11px] text-slate-400">Fuente: Kaggle Datasets &bull; Validación AST: sqlglot</span>
            </div>
        </div>
    </div>

    <script>
        /* DATABASE_CATALOG_PLACEHOLDER */
        let chartInstance = echarts.init(document.getElementById('chart-container'), 'dark');
        let currentEngine = 'northwind';
        let enginesData = [];
        let currentChartOption = null;
        let originalGeoOption = null;
        let currentChartMode = 'line';
        let currentRawRows = [];
        let currentRawCols = [];
        let currentColMeta = [];
        let fullscreenChartInstance = null;
        let currentFullscreenType = null;
        let currentAuditData = null;
        let currentStoryData = null;
        let currentTaskData = null;
        let currentSuggestedQuestions = [];
        let currentArchifyEntities = [];
        let currentArchifyMode = 'visual'; // 'visual' | 'inspector'
        let modalArchifyMode = 'split'; // 'split' | 'diagram' | 'inspector'
        let archifyEntitiesExpanded = {};
        const registeredCustomMaps = {};

        async function ensureMapRegistered(mapName) {
            if (!mapName || mapName === 'world') return;
            if (registeredCustomMaps[mapName] || (echarts.getMap && echarts.getMap(mapName))) {
                registeredCustomMaps[mapName] = true;
                return;
            }
            try {
                const res = await fetch(`/api/geo/${mapName}.geojson`);
                if (res.ok) {
                    const geoJson = await res.json();
                    echarts.registerMap(mapName, geoJson);
                    registeredCustomMaps[mapName] = true;
                    console.log(`Registered custom map '${mapName}' in ECharts`);
                }
            } catch (e) {
                console.warn(`Failed to register custom map '${mapName}':`, e);
            }
        }
        // Preload El Salvador department boundary GeoJSON
        ensureMapRegistered('el_salvador');

        function highlightSQL(sql) {
            if (!sql) return '';
            let formatted = '';
            if (window.Prism && window.Prism.languages && window.Prism.languages.sql) {
                try {
                    formatted = Prism.highlight(sql, Prism.languages.sql, 'sql');
                } catch (e) {
                    console.warn("Prism highlight error, using fallback:", e);
                }
            }
            if (!formatted) {
                const tokenRegex = /(\/\*[\s\S]*?\*\/|--[^\n]*)|('(?:''|[^'\\]|\\.)*')|(\b(?:SELECT|FROM|WHERE|JOIN|INNER|LEFT|RIGHT|FULL|OUTER|CROSS|ON|GROUP\s+BY|ORDER\s+BY|LIMIT|OFFSET|WITH|AS|UNION|ALL|AND|OR|NOT|IN|IS|NULL|BETWEEN|EXISTS|LIKE|ILIKE|CASE|WHEN|THEN|ELSE|END|ASC|DESC|DISTINCT|HAVING|INSERT|UPDATE|DELETE)\b)|(\b(?:ROUND|SUM|AVG|COUNT|MIN|MAX|DATE|DATETIME|STRFTIME|COALESCE|CAST|SUBSTR|TRIM|UPPER|LOWER|LENGTH|TOTAL|IFNULL)\b)|(\b\d+(?:\.\d+)?\b)/gi;

                formatted = sql.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(tokenRegex, (match, comment, str, kw, fn, num) => {
                    if (comment) return `<span class="token comment text-slate-500 italic">${comment}</span>`;
                    if (str) return `<span class="token string text-emerald-400">${str}</span>`;
                    if (kw) return `<span class="token keyword text-indigo-400 font-bold">${kw}</span>`;
                    if (fn) return `<span class="token function text-sky-400 font-semibold">${fn}</span>`;
                    if (num) return `<span class="token number text-amber-400 font-mono">${num}</span>`;
                    return match;
                });
            }
            return formatted;
        }

        function formatCodeWithLineNumbers(rawSql) {
            const highlighted = highlightSQL(rawSql);
            const lines = highlighted.split('\n');
            const gutter = lines.map((_, i) => `<div>${String(i + 1).padStart(2, '0')}</div>`).join('');
            return `
                <div class="flex text-[11px] leading-relaxed font-mono border border-slate-800 rounded-lg overflow-hidden bg-slate-950">
                    <div class="py-2.5 px-2 bg-slate-900/90 border-r border-slate-800 text-slate-600 text-right select-none font-mono text-[10px] space-y-0">
                        ${gutter}
                    </div>
                    <div class="py-2.5 px-3 overflow-x-auto text-slate-300 font-mono whitespace-pre flex-1 select-text">
                        ${lines.join('\n')}
                    </div>
                </div>
            `;
        }

        function copyCurrentSql() {
            if (!currentAuditData || !currentAuditData.sql) {
                alert("No hay consulta SQL para copiar.");
                return;
            }
            navigator.clipboard.writeText(currentAuditData.sql).then(() => {
                const btns = document.querySelectorAll('.copy-sql-btn');
                btns.forEach(b => {
                    const original = b.innerHTML;
                    b.innerHTML = '<span>✓</span> Copiado';
                    b.classList.add('text-emerald-400');
                    setTimeout(() => {
                        b.innerHTML = original;
                        b.classList.remove('text-emerald-400');
                    }, 2000);
                });
            }).catch(e => console.error("Error al copiar SQL:", e));
        }

        function copyStorytellingText() {
            if (!currentStoryData) return;
            const text = [
                "CONCLUSIÓN EJECUTIVA:",
                currentStoryData.key_takeaway,
                "\nDIAGNÓSTICO CUANTITATIVO:",
                ...(currentStoryData.quantitative_findings || []).map(f => `- ${f}`),
                "\nALERTAS DE RIESGO:",
                ...(currentStoryData.risk_alerts || []).map(r => `- ${r}`),
                "\nRECOMENDACIONES:",
                ...(currentStoryData.strategic_recommendations || []).map(rec => `- ${rec}`)
            ].join('\n');

            navigator.clipboard.writeText(text).then(() => {
                alert("Resumen ejecutivo copiado al portapapeles.");
            });
        }

        function executeModalQuery() {
            const modalInput = document.getElementById('modal-query-input');
            if (modalInput) {
                document.getElementById('query-input').value = modalInput.value;
            }
            closeFullscreen();
            executeQuery();
        }

        function setQueryFromModal(text) {
            document.getElementById('query-input').value = text;
            closeFullscreen();
            executeQuery();
        }

        function toggleCardCollapse(cardId) {
            const body = document.getElementById(`body-${cardId}`);
            const btn = document.getElementById(`toggle-${cardId}`);
            if (!body) return;
            const isHidden = body.classList.contains('hidden');
            if (isHidden) {
                body.classList.remove('hidden');
                if (btn) btn.innerText = '▼';
                if (cardId === 'chart-card' && chartInstance) {
                    setTimeout(() => chartInstance.resize(), 60);
                }
            } else {
                body.classList.add('hidden');
                if (btn) btn.innerText = '▲';
            }
        }

        function openFullscreen(type) {
            currentFullscreenType = type;
            const modal = document.getElementById('fullscreen-modal');
            const modalTitle = document.getElementById('modal-title');
            const modalSubtitle = document.getElementById('modal-subtitle');
            const modalIcon = document.getElementById('modal-icon');
            const modalActions = document.getElementById('modal-actions');
            const chartView = document.getElementById('modal-chart-view');
            const genericView = document.getElementById('modal-generic-view');
            const chartBox = document.getElementById('modal-chart-container');

            modal.classList.remove('hidden');
            chartView.classList.add('hidden');
            genericView.classList.add('hidden');
            modalActions.innerHTML = '';

            if (type === 'chart') {
                modalIcon.innerText = '📈';
                modalTitle.innerText = 'Visualización Analítica Interactiva';
                modalSubtitle.innerText = `Motor: ${currentEngine.toUpperCase()} • ECharts 5`;
                chartView.classList.remove('hidden');

                const isGeo = !!(currentChartOption && currentChartOption._meta && currentChartOption._meta.is_geo);
                modalActions.innerHTML = `
                    ${isGeo ? `<button onclick="changeChartType('map')" class="px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition flex items-center gap-1">🗺️ Mapa</button>` : ''}
                    <button onclick="changeChartType('line')" class="px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">📈 Línea</button>
                    <button onclick="changeChartType('bar')" class="px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">📊 Barra</button>
                    <button onclick="changeChartType('area')" class="px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">🏔️ Área</button>
                    <button onclick="downloadChartImage()" class="px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition flex items-center gap-1">
                        <span>📸</span> PNG
                    </button>
                `;

                if (!fullscreenChartInstance) {
                    fullscreenChartInstance = echarts.init(chartBox, 'dark');
                }
                if (currentChartOption) {
                    fullscreenChartInstance.setOption(currentChartOption, true);
                }
                setTimeout(() => {
                    if (fullscreenChartInstance) fullscreenChartInstance.resize();
                }, 60);

            } else if (type === 'audit') {
                modalIcon.innerText = '🛡️';
                modalTitle.innerText = 'Auditoría DataTask, 4-Layer AST & SQL Formateado';
                modalSubtitle.innerText = `Motor: ${currentEngine.toUpperCase()} • Gobernanza AST con sqlglot (100% Read-Only)`;
                genericView.classList.remove('hidden');

                modalActions.innerHTML = `
                    <button onclick="copyCurrentSql()" class="copy-sql-btn px-2.5 py-1 text-xs rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition flex items-center gap-1 shadow-sm">
                        <span>📋</span> Copiar SQL
                    </button>
                `;

                if (currentAuditData && currentAuditData.sql) {
                    genericView.innerHTML = `
                        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                            <div class="bg-slate-900/90 border border-slate-800 p-3 rounded-xl">
                                <div class="text-[10px] uppercase font-mono text-slate-400 font-semibold">Latencia Ejecución</div>
                                <div class="text-base sm:text-lg font-mono text-emerald-400 font-bold mt-0.5">${currentAuditData.execution_ms} ms</div>
                            </div>
                            <div class="bg-slate-900/90 border border-slate-800 p-3 rounded-xl">
                                <div class="text-[10px] uppercase font-mono text-slate-400 font-semibold">Filas Extraídas</div>
                                <div class="text-base sm:text-lg font-mono text-blue-400 font-bold mt-0.5">${currentAuditData.row_count} <span class="text-xs text-slate-500 font-normal">(Límite 500)</span></div>
                            </div>
                            <div class="bg-slate-900/90 border border-slate-800 p-3 rounded-xl">
                                <div class="text-[10px] uppercase font-mono text-slate-400 font-semibold">Gobernanza AST</div>
                                <div class="text-base sm:text-lg font-mono text-indigo-400 font-bold mt-0.5">SAFE (Read-Only)</div>
                            </div>
                            <div class="bg-slate-900/90 border border-slate-800 p-3 rounded-xl">
                                <div class="text-[10px] uppercase font-mono text-slate-400 font-semibold">Motor Base de Datos</div>
                                <div class="text-base sm:text-lg font-mono text-purple-400 font-bold mt-0.5">${(currentAuditData.engine_id || currentEngine).toUpperCase()}</div>
                            </div>
                        </div>

                        <div class="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-2xl flex-1 flex flex-col">
                            <div class="p-2.5 bg-slate-950 border-b border-slate-800 flex justify-between items-center text-xs text-slate-400 font-mono">
                                <span class="flex items-center gap-2">
                                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></span>
                                    <span>SQL Formateado &amp; Coloreado &middot; Wren AI MDL + sqlglot AST</span>
                                </span>
                                <span class="text-slate-500 text-[11px]">${currentAuditData.sql.split('\n').length} líneas</span>
                            </div>
                            ${formatCodeWithLineNumbers(currentAuditData.sql)}
                        </div>
                    `;
                } else {
                    genericView.innerHTML = `<div class="p-8 text-center text-slate-500 italic">No hay consultas ejecutadas en esta sesión.</div>`;
                }

            } else if (type === 'storytelling') {
                modalIcon.innerText = '📑';
                modalTitle.innerText = 'Resumen Ejecutivo & Storytelling Analítico';
                modalSubtitle.innerText = `Diagnóstico Cuantitativo, Alertas de Vulnerabilidad y Decisiones`;
                genericView.classList.remove('hidden');

                modalActions.innerHTML = `
                    <button onclick="copyStorytellingText()" class="px-2.5 py-1 text-xs rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition flex items-center gap-1 shadow-sm">
                        <span>📋</span> Copiar Informe
                    </button>
                `;

                if (currentStoryData) {
                    genericView.innerHTML = `
                        <div class="p-4 bg-indigo-950/40 border border-indigo-800/80 rounded-xl mb-4 shadow-lg">
                            <div class="text-xs font-mono uppercase tracking-wider text-indigo-400 font-bold mb-1.5 flex items-center gap-1.5">
                                <span class="text-base">📌</span> Conclusión Ejecutiva Principal
                            </div>
                            <p class="font-medium text-slate-100 text-base sm:text-lg leading-relaxed">${currentStoryData.key_takeaway}</p>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl space-y-2">
                                <div class="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold mb-2 flex items-center gap-1.5">
                                    <span>📊</span> Diagnóstico Cuantitativo
                                </div>
                                ${(currentStoryData.quantitative_findings || []).map(f => `
                                    <div class="flex items-start gap-2 text-xs text-slate-300 bg-slate-950/80 p-2.5 rounded-lg border border-slate-800/80">
                                        <span class="text-indigo-400 mt-0.5">•</span>
                                        <span class="leading-relaxed">${f}</span>
                                    </div>
                                `).join('')}
                            </div>

                            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl space-y-2">
                                <div class="text-xs font-mono uppercase tracking-wider text-amber-400 font-semibold mb-2 flex items-center gap-1.5">
                                    <span>⚠️</span> Alertas de Riesgo &amp; Vulnerabilidad
                                </div>
                                ${(currentStoryData.risk_alerts && currentStoryData.risk_alerts.length > 0) ? currentStoryData.risk_alerts.map(r => `
                                    <div class="flex items-start gap-2 text-xs text-amber-200 bg-amber-950/30 p-2.5 rounded-lg border border-amber-800/60">
                                        <span class="text-amber-400 mt-0.5">⚠️</span>
                                        <span class="leading-relaxed">${r}</span>
                                    </div>
                                `).join('') : '<div class="text-xs text-slate-500 italic p-3">No se detectaron riesgos críticos.</div>'}
                            </div>

                            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl space-y-2">
                                <div class="text-xs font-mono uppercase tracking-wider text-emerald-400 font-semibold mb-2 flex items-center gap-1.5">
                                    <span>🎯</span> Recomendaciones Accionables
                                </div>
                                ${(currentStoryData.strategic_recommendations && currentStoryData.strategic_recommendations.length > 0) ? currentStoryData.strategic_recommendations.map(rec => `
                                    <div class="flex items-start gap-2 text-xs text-emerald-200 bg-emerald-950/30 p-2.5 rounded-lg border border-emerald-800/50">
                                        <span class="text-emerald-400 mt-0.5">🎯</span>
                                        <span class="leading-relaxed">${rec}</span>
                                    </div>
                                `).join('') : '<div class="text-xs text-slate-500 italic p-3">Sin recomendaciones adicionales.</div>'}
                            </div>
                        </div>
                    `;
                } else {
                    genericView.innerHTML = `<div class="p-8 text-center text-slate-500 italic">No hay resumen ejecutivo disponible aún.</div>`;
                }

            } else if (type === 'table') {
                modalIcon.innerText = '📋';
                modalTitle.innerText = 'Registros de Evidencia Auditada (Vista Completa)';
                modalSubtitle.innerText = `Motor: ${currentEngine.toUpperCase()} • ${currentRawRows.length} registros cargados`;
                genericView.classList.remove('hidden');

                modalActions.innerHTML = `
                    <div class="relative">
                        <input type="text" id="modal-table-search-input" oninput="filterModalTableRows()" placeholder="🔍 Filtrar registros..." class="w-48 sm:w-64 bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:border-indigo-500">
                    </div>
                    <button onclick="exportTableToCSV()" class="px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-300 hover:text-white hover:border-slate-500 transition flex items-center gap-1">
                        <span>📥</span> CSV
                    </button>
                `;

                renderModalTableRows(currentRawRows);

            } else if (type === 'query') {
                modalIcon.innerText = '💬';
                modalTitle.innerText = 'Consola de Consulta en Lenguaje Natural & Grounding';
                modalSubtitle.innerText = `Motor Activo: ${currentEngine.toUpperCase()} • Capa Semántica Wren AI MDL`;
                genericView.classList.remove('hidden');

                modalActions.innerHTML = `
                    <button onclick="executeModalQuery()" class="px-3 py-1 text-xs rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition flex items-center gap-1 shadow-lg shadow-indigo-600/30">
                        <span>⚡</span> Ejecutar Análisis
                    </button>
                `;

                const currentQ = document.getElementById('query-input').value;
                genericView.innerHTML = `
                    <div class="max-w-4xl mx-auto space-y-4 w-full">
                        <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-xl">
                            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">Editor de Consulta en Lenguaje Natural</label>
                            <textarea id="modal-query-input" rows="4" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm text-slate-100 focus:outline-none focus:border-indigo-500" placeholder="Escribe tu consulta analítica en lenguaje natural...">${currentQ}</textarea>
                            <div class="mt-2 flex justify-between items-center text-xs text-slate-400">
                                <span>Presiona <kbd class="px-1.5 py-0.5 bg-slate-950 border border-slate-800 rounded font-mono text-slate-300">Enter</kbd> para ejecutar directamente.</span>
                                <button onclick="executeModalQuery()" class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition">Ejecutar</button>
                            </div>
                        </div>

                        <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                            <div class="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">Esquema y Tablas Disponibles (${currentEngine.toUpperCase()})</div>
                            <div id="modal-tables-container" class="flex flex-wrap gap-1.5 text-xs"></div>
                        </div>
                    </div>
                `;
                const activeEng = enginesData.find(e => e.id === currentEngine);
                const modalTablesContainer = document.getElementById('modal-tables-container');
                if (activeEng && activeEng.tables && modalTablesContainer) {
                    modalTablesContainer.innerHTML = activeEng.tables.map(t => `<span class="bg-slate-950 border border-slate-800 px-2.5 py-1 rounded text-slate-300 font-mono">${t}</span>`).join('');
                }
                document.getElementById('modal-query-input')?.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        executeModalQuery();
                    }
                });

            } else if (type === 'archify') {
                modalIcon.innerText = '🕸️';
                modalTitle.innerText = 'Relaciones de la Consulta & Esquema ERD Completo';
                modalSubtitle.innerText = `Motor: ${currentEngine.toUpperCase()} • Diagrama Interactivo & Diccionario de Atributos`;
                genericView.classList.remove('hidden');

                modalActions.innerHTML = `
                    <div class="flex bg-slate-950 rounded-lg p-0.5 border border-slate-800 text-xs">
                        <button id="modal-archify-btn-split" onclick="switchModalArchifyMode('split')" class="px-2.5 py-1 rounded text-sky-400 font-medium bg-slate-900 border border-sky-900/50 transition flex items-center gap-1">
                            <span>🔀</span> <span class="hidden sm:inline">Vista Dividida</span>
                        </button>
                        <button id="modal-archify-btn-diagram" onclick="switchModalArchifyMode('diagram')" class="px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition flex items-center gap-1">
                            <span>🗺️</span> <span class="hidden sm:inline">Solo Diagrama</span>
                        </button>
                        <button id="modal-archify-btn-inspector" onclick="switchModalArchifyMode('inspector')" class="px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition flex items-center gap-1">
                            <span>📋</span> <span class="hidden sm:inline">Solo Atributos</span>
                        </button>
                    </div>
                    <a href="/api/archify/latest.html" target="_blank" class="px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-700 text-slate-300 hover:text-white hover:border-sky-500 transition flex items-center gap-1 shadow-sm">
                        <span>↗</span> Pestaña
                    </a>
                `;

                renderModalArchifyContent();

            } else if (type === 'suggested') {
                modalIcon.innerText = '💡';
                modalTitle.innerText = 'Banco de Preguntas Analíticas Sugeridas';
                modalSubtitle.innerText = `Exploración Guiada por Contexto Semántico e Introspección`;
                genericView.classList.remove('hidden');

                const questions = (currentSuggestedQuestions && currentSuggestedQuestions.length > 0) ? currentSuggestedQuestions : [
                    "ventas por país",
                    "ventas por categoría",
                    "ventas por empleado",
                    "tendencia de ventas diaria por categoría de las 3 categorías con mejor desempeño",
                    "facturación por país",
                    "canciones por artista",
                    "top actores con más películas"
                ];

                genericView.innerHTML = `
                    <div class="max-w-4xl mx-auto space-y-3 w-full">
                        <p class="text-xs text-slate-400">Selecciona cualquier pregunta analítica sugerida para ejecutarla instantáneamente en el motor activo:</p>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            ${questions.map(q => `
                                <div onclick="setQueryFromModal('${q.replace(/'/g, "\\'")}')" class="p-3.5 bg-slate-900/90 hover:bg-indigo-950/60 border border-slate-800 hover:border-indigo-500 rounded-xl cursor-pointer transition flex items-center justify-between group shadow-sm">
                                    <span class="text-xs text-slate-200 group-hover:text-indigo-200 font-medium">${q}</span>
                                    <span class="text-indigo-400 text-sm group-hover:translate-x-1 transition-transform">⚡</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
        }

        function renderModalTableRows(rows) {
            const genericView = document.getElementById('modal-generic-view');
            if (!genericView) return;
            if (!rows || rows.length === 0) {
                genericView.innerHTML = '<div class="p-8 text-center text-slate-500 italic">No hay registros que coincidan con la búsqueda.</div>';
                return;
            }
            const displayedRows = rows.slice(0, 100);
            genericView.innerHTML = `
                <div class="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-2xl flex-1 flex flex-col">
                    <div class="overflow-x-auto flex-1">
                        <table class="w-full text-left border-collapse">
                            <thead class="sticky top-0 z-10 bg-slate-950 border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider">
                                <tr>
                                    <th class="p-3 text-center w-14 font-semibold text-slate-500">#</th>
                                    ${currentColMeta.map(m => `
                                        <th class="p-3 ${m.align} font-semibold">
                                            <span class="inline-flex items-center">${m.label} ${m.badge}</span>
                                        </th>
                                    `).join('')}
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800/40 text-xs">
                                ${displayedRows.map((r, i) => {
                                    let rankBadge = `<span class="text-slate-500 font-mono text-[11px]">${i + 1}</span>`;
                                    if (i === 0) rankBadge = `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1.5 py-0.5 rounded text-[10px] font-bold">🥇 1</span>`;
                                    else if (i === 1) rankBadge = `<span class="bg-slate-300/20 text-slate-200 border border-slate-400/40 px-1.5 py-0.5 rounded text-[10px] font-bold">🥈 2</span>`;
                                    else if (i === 2) rankBadge = `<span class="bg-amber-700/20 text-amber-500 border border-amber-600/40 px-1.5 py-0.5 rounded text-[10px] font-bold">🥉 3</span>`;

                                    return `
                                        <tr class="transition hover:bg-indigo-950/20 ${i % 2 === 0 ? 'bg-slate-950/30' : 'bg-transparent'}">
                                            <td class="p-3 text-center font-mono">${rankBadge}</td>
                                            ${currentColMeta.map(m => `
                                                <td class="p-3 ${m.align}">
                                                    ${formatTableCell(r[m.col], m.unitType)}
                                                </td>
                                            `).join('')}
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                    ${rows.length > 100 ? `<div class="p-2.5 text-right text-xs text-slate-500 bg-slate-950 border-t border-slate-800 italic">Mostrando primeros 100 de ${rows.length} registros auditados. Descarga CSV para ver todos.</div>` : ''}
                </div>
            `;
        }

        function filterModalTableRows() {
            const input = document.getElementById('modal-table-search-input');
            const query = (input?.value || '').toLowerCase().trim();
            if (!query) {
                renderModalTableRows(currentRawRows);
                return;
            }
            const filtered = currentRawRows.filter(row => {
                return Object.values(row).some(val => String(val).toLowerCase().includes(query));
            });
            renderModalTableRows(filtered);
        }

        function closeFullscreen() {
            const modal = document.getElementById('fullscreen-modal');
            modal.classList.add('hidden');
            currentFullscreenType = null;
        }

        let activeDocsEngine = 'northwind';

        function openDatabaseDocsModal(engineId) {
            const targetEngine = engineId || currentEngine || 'northwind';
            activeDocsEngine = targetEngine;
            const modal = document.getElementById('database-docs-modal');
            modal.classList.remove('hidden');
            renderDatabaseDocsModalContent(targetEngine);
        }

        function closeDatabaseDocsModal() {
            const modal = document.getElementById('database-docs-modal');
            if (modal) modal.classList.add('hidden');
        }

        function switchDatabaseDocsTab(engineId) {
            activeDocsEngine = engineId;
            renderDatabaseDocsModalContent(engineId);
        }

        function renderDatabaseDocsModalContent(engineId) {
            const doc = DATABASE_CATALOG[engineId] || DATABASE_CATALOG['northwind'];
            if (!doc) return;

            document.getElementById('db-modal-emoji').innerText = doc.emoji || '🗄️';
            document.getElementById('db-modal-title').innerText = doc.title;
            document.getElementById('db-modal-badge').innerText = doc.id.toUpperCase();
            document.getElementById('db-modal-subtitle').innerText = doc.subtitle;
            document.getElementById('db-modal-docs-link').href = `/documentation#database-${doc.id}`;

            ['northwind', 'chinook', 'sakila', 'adventureworks_dw', 'tpch'].forEach(id => {
                const btn = document.getElementById(`db-tab-${id}`);
                if (btn) {
                    if (id === doc.id) {
                        btn.className = "db-tab px-3 py-1 rounded-lg font-medium transition border flex items-center gap-1.5 bg-indigo-600 border-indigo-500 text-white shadow-sm shadow-indigo-500/30";
                    } else {
                        btn.className = "db-tab px-3 py-1 rounded-lg font-medium transition border flex items-center gap-1.5 bg-slate-900 border-slate-800 text-slate-400 hover:text-white hover:border-slate-700";
                    }
                }
            });

            const kaggle = doc.kaggle_source;
            const modulesHtml = doc.modules.map(mod => `
                <div class="bg-slate-950/60 border border-slate-800/80 p-3.5 rounded-xl">
                    <div class="flex items-center justify-between mb-1.5">
                        <h5 class="text-xs font-bold text-indigo-300">${mod.name}</h5>
                        <span class="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">${mod.tables.join(', ')}</span>
                    </div>
                    <p class="text-xs text-slate-300 leading-relaxed">${mod.description}</p>
                </div>
            `).join('');

            const tablesPillsHtml = doc.tables_detail.map(t => `
                <span class="text-[11px] font-mono bg-slate-950 border border-slate-800/80 px-2 py-0.5 rounded text-slate-300" title="${t.desc}">${t.table}</span>
            `).join('');

            const examplesHtml = doc.example_queries.map(ex => {
                const safeQuery = ex.query.replace(/'/g, "\\'");
                return `
                <div class="bg-slate-950/70 border border-slate-800/80 p-3.5 rounded-xl flex flex-col justify-between hover:border-indigo-500/50 transition group">
                    <div>
                        <div class="flex items-center justify-between gap-2 mb-2">
                            <span class="text-[10px] uppercase tracking-wider font-semibold text-indigo-400 font-mono bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-900/50">${ex.pattern}</span>
                        </div>
                        <p class="text-xs font-semibold text-white mb-1.5 flex items-start gap-1.5">
                            <span class="text-indigo-400">💬</span> "${ex.query}"
                        </p>
                        <p class="text-[11px] text-slate-400 leading-snug">${ex.insight}</p>
                    </div>
                    <div class="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between">
                        <span class="text-[10px] text-slate-500">Ejecución con 1 clic</span>
                        <button onclick="useExampleQuery('${doc.id}', '${safeQuery}')" class="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center gap-1 shadow-sm transition">
                            <span>⚡ Probar Consulta</span>
                        </button>
                    </div>
                </div>
                `;
            }).join('');

            const nonTechHtml = doc.non_technical_summary.replace(/\\n\\n/g, '<br><br>');
            const erdExpHtml = doc.erd_explanation.replace(/\\n/g, '<br>');

            const container = document.getElementById('db-modal-body');
            container.innerHTML = `
                <!-- Kaggle Primary Source Card -->
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                    <div class="flex items-center gap-3">
                        <span class="text-2xl p-2 rounded-lg bg-sky-950/50 border border-sky-800/60 text-sky-400">📊</span>
                        <div>
                            <div class="flex items-center gap-2">
                                <span class="font-bold text-sky-300 text-xs uppercase tracking-wide">Fuente Primaria: Kaggle Dataset</span>
                                <span class="text-[10px] font-mono text-slate-500">• ${kaggle.license}</span>
                            </div>
                            <a href="${kaggle.url}" target="_blank" rel="noopener noreferrer" class="text-sm font-semibold text-indigo-400 hover:text-indigo-300 underline flex items-center gap-1 mt-0.5">
                                ${kaggle.name} &nearr;
                            </a>
                            <p class="text-[11px] text-slate-400 mt-0.5">${kaggle.author} &bull; ${kaggle.scope}</p>
                        </div>
                    </div>
                    <a href="${kaggle.url}" target="_blank" rel="noopener noreferrer" class="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700 text-xs font-medium flex items-center gap-1 transition self-end sm:self-auto shrink-0">
                        <span>Ver en Kaggle</span> &nearr;
                    </a>
                </div>

                <!-- Explicación No Técnica (En Cristiano) -->
                <div class="bg-slate-950/90 border border-slate-800 p-5 rounded-xl space-y-3">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-2">
                        <span>💡</span> ¿En qué consiste esta base de datos? (Explicación para no técnicos)
                    </h4>
                    <div class="text-slate-300 text-sm leading-relaxed">
                        ${nonTechHtml}
                    </div>
                    <div class="pt-3 border-t border-slate-800 flex items-start gap-2 text-xs text-emerald-400">
                        <span>🎯</span>
                        <div>
                            <strong class="text-emerald-300">Valor de Decisión Ejecutiva:</strong>
                            <span class="text-slate-300 ml-1">${doc.business_value}</span>
                        </div>
                    </div>
                </div>

                <!-- Módulos de Información y Tablas -->
                <div class="space-y-3">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <span>📦</span> ¿Qué información contiene? (Módulos de Negocio)
                    </h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        ${modulesHtml}
                    </div>
                    <div class="flex flex-wrap items-center gap-1.5 pt-1">
                        <span class="text-xs text-slate-500 font-semibold mr-1">Tablas del Motor (${doc.tables_detail.length}):</span>
                        ${tablesPillsHtml}
                    </div>
                </div>

                <!-- Diagrama ER General (Mermaid) -->
                <div class="space-y-2">
                    <div class="flex justify-between items-center">
                        <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <span>🗺️</span> Modelo de Entidad-Relación General (ERD)
                        </h4>
                        <span class="text-[10px] font-mono text-slate-500">Mermaid Render</span>
                    </div>
                    <div class="mermaid rounded-xl border border-slate-800 p-3 bg-slate-950 overflow-x-auto" id="modal-erd-container">
${doc.mermaid_erd}
                    </div>
                    <div class="bg-slate-950 border border-slate-800/80 p-3 rounded-xl text-xs text-slate-300">
                        <strong class="text-indigo-300">¿Cómo se relacionan las tablas en cristiano?</strong>
                        <div class="mt-1 space-y-1 text-slate-400 leading-relaxed">
                            ${erdExpHtml}
                        </div>
                    </div>
                </div>

                <!-- Consultas de Ejemplo en Lenguaje Natural -->
                <div class="space-y-3">
                    <div class="flex items-center justify-between">
                        <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <span>💬</span> ¿Cómo utilizarla? Consultas de ejemplo en lenguaje natural
                        </h4>
                        <span class="text-[11px] text-slate-500">Haz clic en "⚡ Probar Consulta" para cargarla</span>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        ${examplesHtml}
                    </div>
                </div>
            `;

            try {
                if (window.mermaid) {
                    const el = document.getElementById('modal-erd-container');
                    if (el) {
                        el.removeAttribute('data-processed');
                        mermaid.run({ nodes: [el] });
                    }
                }
            } catch (err) {
                console.warn("Mermaid render error:", err);
            }
        }

        async function useExampleQuery(engineId, queryText) {
            closeDatabaseDocsModal();
            if (currentEngine !== engineId) {
                await switchEngine(engineId);
            }
            const input = document.getElementById('query-input');
            input.value = queryText;
            input.focus();
            document.getElementById('query-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeFullscreen();
                closeDatabaseDocsModal();
            }
        });

        function setQuery(text) {
            document.getElementById('query-input').value = text;
            executeQuery();
        }

        async function loadEngines() {
            try {
                const res = await fetch('/api/engines');
                const data = await res.json();
                currentEngine = data.active;
                enginesData = data.engines;

                document.getElementById('active-engine-badge').innerText = currentEngine.toUpperCase();

                const container = document.getElementById('engine-selector-container');
                container.innerHTML = data.engines.map(e => `
                    <button onclick="switchEngine('${e.id}')" class="px-3 py-1.5 text-xs rounded-lg border font-medium transition ${e.id === currentEngine ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-500/20' : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white hover:border-slate-700'}">
                        ${e.id.toUpperCase()} <span class="opacity-60 font-mono text-[10px]">(${e.tables_count})</span>
                    </button>
                `).join('');

                renderTablesPills();
            } catch (err) {
                console.error("Error cargando motores:", err);
            }
        }

        function renderTablesPills() {
            const activeEng = enginesData.find(e => e.id === currentEngine);
            const tablesContainer = document.getElementById('tables-container');
            if (activeEng && activeEng.tables) {
                tablesContainer.innerHTML = `
                    <span class="text-slate-500 mr-1">Tablas disponibles:</span>
                    ${activeEng.tables.map(t => `<span class="bg-slate-950 border border-slate-800/80 px-2 py-0.5 rounded text-[11px] text-slate-300 font-mono">${t}</span>`).join('')}
                    ${activeEng.tables_count > activeEng.tables.length ? `<span class="text-slate-500 text-[11px] self-center">+${activeEng.tables_count - activeEng.tables.length} más</span>` : ''}
                `;
            }
        }

        async function switchEngine(id) {
            try {
                await fetch('/api/engines/select', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({engine_id: id})
                });
                await loadEngines();
                updateSampleChips(id);
            } catch (err) {
                alert("Error al seleccionar motor: " + err.message);
            }
        }

        function updateSampleChips(engineId) {
            const chips = document.getElementById('sample-chips');
            if (engineId === 'chinook') {
                chips.innerHTML = `
                    <button onclick="setQuery('canciones por artista')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Canciones por artista</button>
                    <button onclick="setQuery('facturación por país')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Facturación por país</button>
                    <button onclick="setQuery('tendencia semanal de facturación por género de los 3 mejores')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Top 3 Géneros semanal</button>
                `;
            } else if (engineId === 'sakila') {
                chips.innerHTML = `
                    <button onclick="setQuery('top actores con más películas')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Top actores con más películas</button>
                    <button onclick="setQuery('películas por categoría')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Películas por categoría</button>
                `;
            } else {
                chips.innerHTML = `
                    <button onclick="setQuery('ventas por categoría')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Ventas por categoría</button>
                    <button onclick="setQuery('ventas por empleado')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Ventas por empleado</button>
                    <button onclick="setQuery('tendencia de ventas diaria por categoría de las 3 categorías con mejor desempeño')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Top 3 Categorías diario</button>
                `;
            }
        }

        function showAlert(msg, isError = true) {
            const banner = document.getElementById('alert-banner');
            banner.className = `mt-4 p-3 rounded-xl border text-sm flex items-center justify-between transition ${isError ? 'bg-red-950/80 border-red-800 text-red-200' : 'bg-amber-950/80 border-amber-800 text-amber-200'}`;
            document.getElementById('alert-content').innerHTML = `<span>${isError ? '❌' : '⚠️'}</span> <span>${msg}</span>`;
            banner.classList.remove('hidden');
        }

        function dismissAlert() {
            document.getElementById('alert-banner').classList.add('hidden');
        }

        function renderContractChips(task) {
            const container = document.getElementById('contract-chips');
            if (!task) {
                container.innerHTML = '';
                return;
            }
            const chips = [];
            if (task.analytical_pattern) {
                chips.push(`<span class="bg-indigo-950/80 border border-indigo-700/60 text-indigo-300 px-2 py-0.5 rounded font-mono">🎯 Patrón: ${task.analytical_pattern}</span>`);
            }
            if (task.time_granularity && task.time_granularity !== 'NONE') {
                chips.push(`<span class="bg-blue-950/80 border border-blue-700/60 text-blue-300 px-2 py-0.5 rounded font-mono">⏱️ Grano: ${task.time_granularity}</span>`);
            }
            if (task.top_n) {
                chips.push(`<span class="bg-emerald-950/80 border border-emerald-700/60 text-emerald-300 px-2 py-0.5 rounded font-mono">🏆 Top ${task.top_n} (${task.ranking_criterion || 'Líderes'})</span>`);
            }
            if (task.metric_target) {
                chips.push(`<span class="bg-purple-950/80 border border-purple-700/60 text-purple-300 px-2 py-0.5 rounded font-mono">📊 Métrica: ${task.metric_target}</span>`);
            }
            if (task.dimensions && task.dimensions.length > 0) {
                chips.push(`<span class="bg-slate-950 border border-slate-700 text-slate-300 px-2 py-0.5 rounded font-mono">🗂️ Dimensiones: ${task.dimensions.join(', ')}</span>`);
            }
            container.innerHTML = chips.join('');
        }

        function getColumnMetadata(col) {
            const clean = col.toLowerCase().replace(/[\\-_\\s]+/g, '');
            const isMoney = ['usd', 'total', 'subtotal', 'price', 'unitprice', 'cost', 'revenue', 'sales', 'ingreso', 'precio', 'monto', 'importe', 'venta', 'ventas', 'costo', 'valor', 'tarifa', 'freight', 'facturacion', 'amount'].some(k => clean.includes(k));
            const isPct = ['discount', 'descuento', 'margin', 'margen', 'rate', 'tasa', 'pct', 'ratio'].some(k => clean.includes(k));
            const isCount = ['pedidos', 'ordenes', 'canciones', 'peliculas', 'alquileres', 'clientes', 'unidades', 'piezas', 'tracks', 'actores', 'count', 'cantidad', 'volumen', 'orders'].some(k => clean.includes(k));
            const isDate = ['fecha', 'date', 'orderdate', 'paymentdate', 'invoicedate', 'ano', 'mes', 'semana'].some(k => clean.includes(k));

            let label = col.replace(/_USD$/i, '').replace(/_/g, ' ');
            label = label.charAt(0).toUpperCase() + label.slice(1);

            if (isMoney) {
                return {
                    label: label,
                    badge: '<span class="bg-emerald-950/80 text-emerald-400 border border-emerald-800 text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ml-1.5">$ USD</span>',
                    unitType: 'currency',
                    align: 'text-right'
                };
            }
            if (isPct) {
                return {
                    label: label,
                    badge: '<span class="bg-amber-950/80 text-amber-400 border border-amber-800 text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ml-1.5">%</span>',
                    unitType: 'percentage',
                    align: 'text-right'
                };
            }
            if (isCount) {
                return {
                    label: label,
                    badge: '<span class="bg-purple-950/80 text-purple-400 border border-purple-800 text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ml-1.5">Conteo</span>',
                    unitType: 'count',
                    align: 'text-right'
                };
            }
            if (isDate) {
                return {
                    label: label,
                    badge: '<span class="bg-blue-950/80 text-blue-400 border border-blue-800 text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ml-1.5">Fecha</span>',
                    unitType: 'date',
                    align: 'text-center'
                };
            }
            return {
                label: label,
                badge: '',
                unitType: 'text',
                align: 'text-left'
            };
        }

        function formatTableCell(val, unitType) {
            if (val === null || val === undefined) {
                return '<span class="text-slate-600">—</span>';
            }
            const num = Number(val);
            const isNumeric = !isNaN(num) && typeof val !== 'boolean' && val !== '';

            if (unitType === 'currency' && isNumeric) {
                const formatted = new Intl.NumberFormat('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }).format(num);
                return `<span class="font-mono text-emerald-400 font-semibold tracking-tight"><span class="text-emerald-500/80 font-bold mr-0.5">$</span>${formatted}</span>`;
            }

            if (unitType === 'percentage' && isNumeric) {
                const pctVal = (Math.abs(num) <= 1.0 && num !== 0) ? num * 100 : num;
                return `<span class="font-mono text-amber-300 font-medium">${pctVal.toFixed(1)}%</span>`;
            }

            if (unitType === 'count' && isNumeric) {
                const formatted = new Intl.NumberFormat('en-US').format(Math.round(num));
                return `<span class="font-mono text-blue-300 font-medium">${formatted}</span>`;
            }

            if (unitType === 'date') {
                return `<span class="font-mono text-slate-300">${val}</span>`;
            }

            if (isNumeric) {
                return `<span class="font-mono text-slate-200">${val}</span>`;
            }

            return `<span class="text-slate-200 font-medium">${val}</span>`;
        }

        async function executeQuery() {
            dismissAlert();
            const query = document.getElementById('query-input').value.trim();
            if (!query) return;

            const runBtn = document.getElementById('run-btn');
            runBtn.disabled = true;
            runBtn.innerHTML = '<span>⏳</span> Analizando con 4-Layer AST...';

            try {
                const res = await fetch('/api/query', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query, engine_id: currentEngine})
                });

                if (!res.ok) {
                    const err = await res.json();
                    showAlert("Error en consulta: " + (err.detail || "Fallo desconocido"));
                    return;
                }

                const data = await res.json();

                // Render Grounding Contract Chips
                currentTaskData = data.task;
                renderContractChips(data.task);

                // Render Advanced Executive Storytelling
                const story = data.storytelling;
                currentStoryData = story;
                document.getElementById('storytelling-container').innerHTML = `
                    <div class="p-3 bg-indigo-950/40 border border-indigo-800/60 rounded-xl mb-3">
                        <div class="text-[10px] font-mono uppercase tracking-wider text-indigo-400 font-bold mb-1 flex items-center gap-1">
                            <span>📌</span> Conclusión Ejecutiva
                        </div>
                        <p class="font-medium text-slate-100 text-xs sm:text-sm leading-snug">${story.key_takeaway}</p>
                    </div>

                    <div class="space-y-1.5 mb-3">
                        <div class="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold mb-1">
                            Diagnóstico Cuantitativo
                        </div>
                        ${story.quantitative_findings.map(f => `
                            <div class="flex items-start gap-2 text-xs text-slate-300 bg-slate-950/60 p-1.5 rounded border border-slate-800/60">
                                <span class="text-indigo-400 mt-0.5">📊</span>
                                <span>${f}</span>
                            </div>
                        `).join('')}
                    </div>

                    ${story.risk_alerts && story.risk_alerts.length > 0 ? `
                        <div class="space-y-1.5 mb-3">
                            <div class="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-semibold mb-1">
                                Alertas de Riesgo & Vulnerabilidad
                            </div>
                            ${story.risk_alerts.map(r => `
                                <div class="flex items-start gap-2 text-xs text-amber-200 bg-amber-950/40 p-2 rounded-lg border border-amber-800/60">
                                    <span class="text-amber-400">⚠️</span>
                                    <span>${r}</span>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    ${story.strategic_recommendations && story.strategic_recommendations.length > 0 ? `
                        <div class="space-y-1.5">
                            <div class="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold mb-1">
                                Recomendaciones Accionables
                            </div>
                            ${story.strategic_recommendations.map(rec => `
                                <div class="flex items-start gap-2 text-xs text-emerald-200 bg-emerald-950/30 p-2 rounded-lg border border-emerald-800/50">
                                    <span class="text-emerald-400">🎯</span>
                                    <span>${rec}</span>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                `;

                // Render Suggested Questions
                currentSuggestedQuestions = data.suggested_questions || [];
                renderSuggestedQuestions(data.suggested_questions);

                // Render Audit
                const q = (data.evidence && data.evidence.queries && data.evidence.queries.length > 0) ? data.evidence.queries[0] : null;
                if (q) {
                    currentAuditData = {
                        sql: q.sql,
                        execution_ms: q.execution_ms,
                        row_count: q.row_count,
                        engine_id: data.evidence.engine_id,
                        warnings: data.evidence.warnings
                    };
                    const codeBlock = formatCodeWithLineNumbers(q.sql);
                    document.getElementById('audit-container').innerHTML = `
                        <div class="mb-2">
                            <div class="flex justify-between items-center mb-1">
                                <span class="text-indigo-400 font-semibold block text-xs">SQL Formateado &amp; Comentado:</span>
                                <span class="text-[10px] text-slate-500 font-mono">AST Verificado (sqlglot)</span>
                            </div>
                            ${codeBlock}
                        </div>
                        <p class="mt-2 text-slate-400 text-xs"><span class="text-emerald-400 font-semibold">Latencia:</span> ${q.execution_ms} ms &bull; <span class="text-blue-400 font-semibold">Filas:</span> ${q.row_count} &bull; <span class="text-purple-400 font-semibold">Motor:</span> ${data.evidence.engine_id.toUpperCase()}</p>
                    `;

                    // Store rows for interactive filtering & CSV export
                    currentRawRows = q.rows || [];
                    if (currentRawRows.length > 0) {
                        currentRawCols = Object.keys(currentRawRows[0]);
                        currentColMeta = currentRawCols.map(c => ({ col: c, ...getColumnMetadata(c) }));
                        document.getElementById('table-search-input').value = '';
                        renderTableRows(currentRawRows);
                    } else {
                        document.getElementById('table-row-count-badge').classList.add('hidden');
                        document.getElementById('table-container').innerHTML = '<p class="text-slate-500 italic p-3">Sin registros devueltos.</p>';
                    }
                } else {
                    currentAuditData = null;
                    document.getElementById('audit-container').innerHTML = `
                        <p class="text-amber-400">${data.evidence.warnings.join(' | ') || 'Consulta procesada sin queries SQL directas.'}</p>
                    `;
                    document.getElementById('table-container').innerHTML = '<p class="text-slate-500 italic p-2">Sin registros devueltos.</p>';
                }

                // Render Chart & store options for dynamic switching
                if (data.visualization) {
                    currentChartOption = data.visualization;
                    const isGeo = !!(data.visualization._meta && data.visualization._meta.is_geo);
                    const mapBtn = document.getElementById('btn-chart-map');
                    if (isGeo) {
                        mapBtn.classList.remove('hidden');
                        const targetMap = (data.visualization.geo && data.visualization.geo.map) || (data.visualization._meta && data.visualization._meta.map_name) || 'world';
                        if (targetMap !== 'world') {
                            await ensureMapRegistered(targetMap);
                        }
                        const catCol = data.visualization._meta && data.visualization._meta.category_col;
                        if (catCol) {
                            data.visualization.tooltip = {
                                trigger: 'item',
                                backgroundColor: '#0F172A',
                                borderColor: '#334155',
                                textStyle: { color: '#E2E8F0' },
                                formatter: function(params) {
                                    if (!params.data) return params.name;
                                    const cat = params.data.category ? `<br/><span class="text-indigo-400 font-semibold">${catCol}:</span> <strong>${params.data.category}</strong>` : '';
                                    const unit = (data.visualization._meta && data.visualization._meta.unit) || '';
                                    const valStr = (params.value !== undefined && params.value !== null) ? `${params.value} ${unit}`.trim() : '0';
                                    return `<div class="p-1"><span class="text-slate-200 font-bold">${params.name}</span>${cat}<br/><span class="text-slate-400">${params.seriesName || 'Volumen'}:</span> <span class="text-emerald-400 font-mono font-semibold">${valStr}</span></div>`;
                                }
                            };
                        }
                        originalGeoOption = JSON.parse(JSON.stringify(data.visualization));
                        currentChartMode = 'map';
                    } else {
                        mapBtn.classList.add('hidden');
                        originalGeoOption = null;
                        if (currentChartOption.series && currentChartOption.series.length > 0) {
                            const firstType = currentChartOption.series[0].type;
                            currentChartMode = (firstType === 'bar') ? 'bar' : 'line';
                        } else {
                            currentChartMode = 'line';
                        }
                    }
                    chartInstance.setOption(currentChartOption, true);
                    updateChartTypeButtons(currentChartMode);
                } else {
                    currentChartOption = null;
                    originalGeoOption = null;
                    document.getElementById('btn-chart-map').classList.add('hidden');
                    chartInstance.clear();
                }

                // Render Archify Relational Diagram & Attribute Inspector
                if (data.has_archify) {
                    currentArchifyEntities = data.archify_entities || [];
                    const iframe = `<iframe src="/api/archify/latest.html?theme=dark&embed=1&t=${Date.now()}" class="w-full h-full border-0 rounded-lg" loading="lazy"></iframe>`;
                    document.getElementById('archify-container').innerHTML = iframe;

                    const countBadge = document.getElementById('archify-entity-count-badge');
                    if (countBadge) {
                        const totalCols = currentArchifyEntities.reduce((acc, e) => acc + (e.attributes ? e.attributes.length : 0), 0);
                        countBadge.innerText = `${currentArchifyEntities.length} tablas • ${totalCols} atributos`;
                        countBadge.classList.remove('hidden');
                    }

                    renderArchifyInspectorCards('archify-inspector-cards', false);
                }

                // Refresh modal view if currently open
                if (currentFullscreenType && !document.getElementById('fullscreen-modal').classList.contains('hidden')) {
                    openFullscreen(currentFullscreenType);
                }
            } catch (err) {
                showAlert("Error de conexión: " + err.message);
            } finally {
                runBtn.disabled = false;
                runBtn.innerHTML = '<span>⚡</span> Ejecutar Análisis';
            }
        }

        function renderSuggestedQuestions(questions) {
            const container = document.getElementById('suggested-container');
            const chips = document.getElementById('suggested-chips');
            if (questions && questions.length > 0) {
                chips.innerHTML = questions.map(q => `
                    <button onclick="setQuery('${q.replace(/'/g, "\\'")}')" class="px-2.5 py-1 rounded-lg bg-slate-950 border border-indigo-900/60 text-indigo-300 hover:text-white hover:bg-indigo-950/80 hover:border-indigo-500 transition text-left flex items-center gap-1.5 shadow-sm">
                        <span class="text-indigo-400">⚡</span> ${q}
                    </button>
                `).join('');
                container.classList.remove('hidden');
            } else {
                container.classList.add('hidden');
            }
        }

        function renderTableRows(rows) {
            if (!rows || rows.length === 0) {
                document.getElementById('table-container').innerHTML = '<p class="text-slate-500 italic p-3">No hay registros que coincidan con la búsqueda.</p>';
                document.getElementById('table-row-count-badge').innerText = `0 de ${currentRawRows.length} registros`;
                return;
            }

            const badge = document.getElementById('table-row-count-badge');
            if (rows.length !== currentRawRows.length) {
                badge.innerText = `${rows.length} de ${currentRawRows.length} filtrados`;
            } else {
                badge.innerText = `${rows.length} ${rows.length === 1 ? 'registro' : 'registros'}`;
            }
            badge.classList.remove('hidden');

            const displayedRows = rows.slice(0, 30);
            document.getElementById('table-container').innerHTML = `
                <table class="w-full text-left border-collapse rounded-lg overflow-hidden">
                    <thead>
                        <tr class="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider">
                            <th class="p-2.5 text-center w-12 font-semibold text-slate-500">#</th>
                            ${currentColMeta.map(m => `
                                <th class="p-2.5 ${m.align} font-semibold">
                                    <span class="inline-flex items-center">${m.label} ${m.badge}</span>
                                </th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800/40">
                        ${displayedRows.map((r, i) => {
                            let rankBadge = `<span class="text-slate-500 font-mono text-[11px]">${i + 1}</span>`;
                            if (i === 0) rankBadge = `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1.5 py-0.5 rounded text-[10px] font-bold">🥇 1</span>`;
                            else if (i === 1) rankBadge = `<span class="bg-slate-300/20 text-slate-200 border border-slate-400/40 px-1.5 py-0.5 rounded text-[10px] font-bold">🥈 2</span>`;
                            else if (i === 2) rankBadge = `<span class="bg-amber-700/20 text-amber-500 border border-amber-600/40 px-1.5 py-0.5 rounded text-[10px] font-bold">🥉 3</span>`;

                            return `
                                <tr class="transition hover:bg-indigo-950/20 ${i % 2 === 0 ? 'bg-slate-950/30' : 'bg-transparent'}">
                                    <td class="p-2.5 text-center font-mono">${rankBadge}</td>
                                    ${currentColMeta.map(m => `
                                        <td class="p-2.5 ${m.align}">
                                            ${formatTableCell(r[m.col], m.unitType)}
                                        </td>
                                    `).join('')}
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
                ${rows.length > 30 ? `<p class="text-right text-[11px] text-slate-500 mt-2 italic">Mostrando primeros 30 de ${rows.length} registros auditados</p>` : ''}
            `;
        }

        function filterTableRows() {
            const query = (document.getElementById('table-search-input').value || '').toLowerCase().trim();
            if (!query) {
                renderTableRows(currentRawRows);
                return;
            }
            const filtered = currentRawRows.filter(row => {
                return Object.values(row).some(val => String(val).toLowerCase().includes(query));
            });
            renderTableRows(filtered);
        }

        function exportTableToCSV() {
            if (!currentRawRows || currentRawRows.length === 0) {
                alert("No hay registros disponibles para exportar.");
                return;
            }
            const headers = currentRawCols.join(',');
            const rowsCsv = currentRawRows.map(r => {
                return currentRawCols.map(col => {
                    let val = r[col];
                    if (val === null || val === undefined) return '""';
                    val = String(val).replace(/"/g, '""');
                    return `"${val}"`;
                }).join(',');
            }).join('\\n');

            const csvContent = "data:text/csv;charset=utf-8," + headers + "\\n" + rowsCsv;
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", `kratos_data_${currentEngine}_${new Date().toISOString().slice(0,10)}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        function changeChartType(newType) {
            if (!currentChartOption) return;
            currentChartMode = newType;
            updateChartTypeButtons(newType);

            // Switching back to Geo Map
            if (newType === 'map' && originalGeoOption) {
                currentChartOption = JSON.parse(JSON.stringify(originalGeoOption));
                chartInstance.setOption(currentChartOption, true);
                if (fullscreenChartInstance && currentFullscreenType === 'chart') {
                    fullscreenChartInstance.setOption(currentChartOption, true);
                }
                return;
            }

            // Converting Geo Map to Bar / Line / Area
            if (originalGeoOption && newType !== 'map') {
                const meta = originalGeoOption._meta || {};
                const cats = meta.categories || [];
                const vals = meta.values || [];
                const unit = meta.unit || '';
                const metricCol = meta.metric_col || 'Valor';

                const pairs = cats.map((c, i) => {
                    const label = (meta.category_col && meta.categories_secondary && meta.categories_secondary[i])
                        ? `${c} • ${meta.categories_secondary[i]}`
                        : c;
                    return { name: label, val: vals[i] || 0 };
                });
                pairs.sort((a, b) => b.val - a.val);
                const topPairs = pairs.slice(0, 15);
                const chartCats = topPairs.map(p => p.name);
                const chartVals = topPairs.map(p => p.val);

                currentChartOption = {
                    title: {
                        text: `${originalGeoOption.title?.text || 'Distribución'} (Top 15)`,
                        textStyle: { color: '#E2E8F0' }
                    },
                    tooltip: {
                        trigger: 'axis',
                        backgroundColor: '#0F172A',
                        borderColor: '#334155',
                        textStyle: { color: '#E2E8F0' },
                        formatter: `{b}: {c} ${unit}`.trim()
                    },
                    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
                    xAxis: {
                        type: 'category',
                        data: chartCats,
                        axisLabel: { color: '#94A3B8', interval: 0, rotate: 25 },
                        axisLine: { lineStyle: { color: '#334155' } }
                    },
                    yAxis: {
                        type: 'value',
                        axisLabel: { color: '#94A3B8' },
                        splitLine: { lineStyle: { color: '#1E293B' } }
                    },
                    series: [{
                        name: metricCol,
                        type: (newType === 'bar') ? 'bar' : 'line',
                        data: chartVals,
                        smooth: true,
                        areaStyle: (newType === 'area') ? { opacity: 0.25 } : undefined,
                        itemStyle: (newType === 'bar') ? { borderRadius: [4, 4, 0, 0], color: '#6366F1' } : { color: '#6366F1' }
                    }],
                    _meta: originalGeoOption._meta
                };

                chartInstance.setOption(currentChartOption, true);
                if (fullscreenChartInstance && currentFullscreenType === 'chart') {
                    fullscreenChartInstance.setOption(currentChartOption, true);
                }
                return;
            }

            // Standard series transformation
            if (currentChartOption.series) {
                currentChartOption.series.forEach(s => {
                    if (newType === 'bar') {
                        s.type = 'bar';
                        s.itemStyle = Object.assign({}, s.itemStyle || {}, { borderRadius: [4, 4, 0, 0] });
                        delete s.areaStyle;
                    } else if (newType === 'area') {
                        s.type = 'line';
                        s.smooth = true;
                        s.areaStyle = { opacity: 0.25 };
                    } else {
                        s.type = 'line';
                        s.smooth = true;
                        delete s.areaStyle;
                    }
                });

                chartInstance.setOption(currentChartOption, true);
                if (fullscreenChartInstance && currentFullscreenType === 'chart') {
                    fullscreenChartInstance.setOption(currentChartOption, true);
                }
            }
        }

        function updateChartTypeButtons(activeType) {
            ['map', 'line', 'bar', 'area'].forEach(t => {
                const btn = document.getElementById(`btn-chart-${t}`);
                if (!btn) return;
                if (t === activeType) {
                    btn.className = "chart-type-btn px-2.5 py-1 text-xs rounded bg-indigo-600 border border-indigo-500 text-white font-medium transition shadow-sm flex items-center gap-1";
                } else {
                    btn.className = "chart-type-btn px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition flex items-center gap-1";
                }
            });
        }

        function downloadChartImage() {
            if (!chartInstance) return;
            const url = chartInstance.getDataURL({
                type: 'png',
                pixelRatio: 2,
                backgroundColor: '#0B0F19'
            });
            const link = document.createElement("a");
            link.href = url;
            link.download = `kratos_chart_${currentEngine}_${new Date().toISOString().slice(0,10)}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        function switchArchifyCardTab(tab) {
            currentArchifyMode = tab;
            const visualView = document.getElementById('archify-visual-view');
            const inspectorView = document.getElementById('archify-inspector-view');
            const btnVisual = document.getElementById('btn-archify-tab-visual');
            const btnInspector = document.getElementById('btn-archify-tab-inspector');

            if (tab === 'visual') {
                visualView?.classList.remove('hidden');
                inspectorView?.classList.add('hidden');
                if (btnVisual) btnVisual.className = 'px-2.5 py-1 rounded text-sky-400 font-medium bg-slate-900 border border-sky-900/50 transition flex items-center gap-1';
                if (btnInspector) btnInspector.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition flex items-center gap-1';
            } else {
                visualView?.classList.add('hidden');
                inspectorView?.classList.remove('hidden');
                if (btnVisual) btnVisual.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition flex items-center gap-1';
                if (btnInspector) btnInspector.className = 'px-2.5 py-1 rounded text-sky-400 font-medium bg-slate-900 border border-sky-900/50 transition flex items-center gap-1';
                renderArchifyInspectorCards('archify-inspector-cards', false);
            }
        }

        function switchModalArchifyMode(mode) {
            modalArchifyMode = mode;
            renderModalArchifyContent();
        }

        function renderModalArchifyContent() {
            const genericView = document.getElementById('modal-generic-view');
            if (!genericView) return;

            ['split', 'diagram', 'inspector'].forEach(m => {
                const btn = document.getElementById(`modal-archify-btn-${m}`);
                if (btn) {
                    if (m === modalArchifyMode) {
                        btn.className = 'px-2.5 py-1 rounded text-sky-400 font-medium bg-slate-900 border border-sky-900/50 transition flex items-center gap-1';
                    } else {
                        btn.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-slate-200 transition flex items-center gap-1';
                    }
                }
            });

            if (modalArchifyMode === 'diagram') {
                genericView.innerHTML = `
                    <div class="w-full h-full min-h-[620px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-2xl flex flex-col flex-1">
                        <iframe src="/api/archify/latest.html?theme=dark&t=${Date.now()}" class="w-full h-full flex-1 border-0" style="min-height: 620px;"></iframe>
                    </div>
                `;
            } else if (modalArchifyMode === 'inspector') {
                genericView.innerHTML = `
                    <div class="w-full min-h-[620px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 p-4 shadow-2xl flex flex-col gap-3">
                        <div class="flex flex-col sm:flex-row items-center justify-between gap-2 bg-slate-900/90 p-3 rounded-lg border border-slate-800">
                            <div class="relative w-full sm:w-96">
                                <input type="text" id="modal-archify-filter" oninput="filterModalArchifyAttributes()" placeholder="🔍 Filtrar columnas o tablas por nombre o tipo..." class="w-full bg-slate-950 border border-slate-800 text-slate-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-sky-500">
                            </div>
                            <div class="flex items-center gap-3 text-xs">
                                <span id="modal-archify-filter-stats" class="text-slate-400 font-mono text-[11px]"></span>
                                <button onclick="expandAllArchifyEntities(true, 'modal-archify-cards')" class="px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition">↕ Expandir Todo</button>
                                <button onclick="expandAllArchifyEntities(false, 'modal-archify-cards')" class="px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition">⇥ Colapsar Todo</button>
                            </div>
                        </div>
                        <div id="modal-archify-cards" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 max-h-[68vh] overflow-y-auto p-1 custom-scrollbar"></div>
                    </div>
                `;
                renderArchifyInspectorCards('modal-archify-cards', true);
            } else {
                // Split View
                genericView.innerHTML = `
                    <div class="w-full min-h-[620px] flex flex-col lg:flex-row gap-3">
                        <div class="lg:w-7/12 min-h-[500px] lg:min-h-[620px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-2xl flex flex-col">
                            <iframe src="/api/archify/latest.html?theme=dark&t=${Date.now()}" class="w-full h-full flex-1 border-0" style="min-height: 580px;"></iframe>
                        </div>
                        <div class="lg:w-5/12 min-h-[400px] lg:min-h-[620px] bg-slate-950 rounded-xl border border-slate-800 p-3 shadow-2xl flex flex-col gap-2">
                            <div class="flex flex-col gap-2 bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                                        <span>📋</span> Atributos & Claves
                                    </span>
                                    <div class="flex items-center gap-1 text-[11px]">
                                        <button onclick="expandAllArchifyEntities(true, 'modal-split-archify-cards')" class="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">↕ Expandir</button>
                                        <button onclick="expandAllArchifyEntities(false, 'modal-split-archify-cards')" class="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">⇥ Colapsar</button>
                                    </div>
                                </div>
                                <input type="text" id="modal-split-filter" oninput="filterModalSplitArchifyAttributes()" placeholder="🔍 Filtrar columnas (ej. price, date, id)..." class="w-full bg-slate-950 border border-slate-800 text-slate-300 rounded px-2.5 py-1 text-xs focus:outline-none focus:border-sky-500">
                                <span id="modal-split-filter-stats" class="text-slate-400 font-mono text-[10px]"></span>
                            </div>
                            <div id="modal-split-archify-cards" class="flex flex-col gap-2.5 max-h-[520px] overflow-y-auto p-1 custom-scrollbar"></div>
                        </div>
                    </div>
                `;
                renderArchifyInspectorCards('modal-split-archify-cards', true);
            }
        }

        function renderArchifyInspectorCards(containerId, isModal = false, filterQuery = '') {
            const container = document.getElementById(containerId);
            if (!container) return;
            if (!currentArchifyEntities || currentArchifyEntities.length === 0) {
                container.innerHTML = '<p class="text-slate-600 text-xs italic p-4">Ejecuta una consulta para inspeccionar los atributos y claves de las entidades.</p>';
                return;
            }

            const q = (filterQuery || '').toLowerCase().trim();
            let totalAttrs = 0;
            let visibleAttrs = 0;

            const cardsHtml = currentArchifyEntities.map(ent => {
                totalAttrs += ent.attributes.length;
                const matchingAttrs = ent.attributes.filter(attr => {
                    if (!q) return true;
                    return ent.id.toLowerCase().includes(q) ||
                           attr.name.toLowerCase().includes(q) ||
                           (attr.type && attr.type.toLowerCase().includes(q)) ||
                           (attr.references && attr.references.toLowerCase().includes(q)) ||
                           (attr.external_fk && attr.external_fk.toLowerCase().includes(q));
                });

                visibleAttrs += matchingAttrs.length;
                if (q && matchingAttrs.length === 0 && !ent.id.toLowerCase().includes(q)) {
                    return '';
                }

                const tagColors = {
                    'métricas': 'bg-rose-950/80 text-rose-300 border-rose-800',
                    'hechos': 'bg-amber-950/80 text-amber-300 border-amber-800',
                    'dimensión': 'bg-emerald-950/80 text-emerald-300 border-emerald-800',
                    'transacción': 'bg-sky-950/80 text-sky-300 border-sky-800'
                };
                const tagClass = tagColors[ent.tag] || 'bg-slate-800 text-slate-300 border-slate-700';

                const attrRows = matchingAttrs.map(attr => {
                    const isPk = attr.key === 'pk';
                    const isFk = attr.key === 'fk';
                    const isExtFk = !!attr.external_fk;

                    let keyBadge = '';
                    if (isPk) {
                        keyBadge = `<span class="px-1.5 py-0.5 text-[10px] font-mono font-bold rounded bg-amber-950 text-amber-300 border border-amber-700 flex items-center gap-0.5">🔑 PK</span>`;
                    } else if (isFk) {
                        keyBadge = `<span class="px-1.5 py-0.5 text-[10px] font-mono font-medium rounded bg-sky-950 text-sky-300 border border-sky-700 flex items-center gap-0.5" title="Enlaza a ${attr.references}">🔗 FK</span>`;
                    } else if (isExtFk) {
                        keyBadge = `<span class="px-1.5 py-0.5 text-[10px] font-mono font-normal rounded bg-indigo-950 text-indigo-300 border border-indigo-800 flex items-center gap-0.5" title="FK Externa: ${attr.external_fk}">↗ FK</span>`;
                    }

                    let refInfo = '';
                    if (isFk && attr.references) {
                        refInfo = `<span class="text-[10px] font-mono text-sky-400 truncate max-w-[130px]" title="${attr.references}">→ ${attr.references}</span>`;
                    } else if (isExtFk && attr.external_fk) {
                        refInfo = `<span class="text-[10px] font-mono text-indigo-400 truncate max-w-[130px]" title="${attr.external_fk}">→ ${attr.external_fk}</span>`;
                    }

                    return `
                        <div class="flex items-center justify-between py-1 px-2 border-b border-slate-800/60 hover:bg-slate-900/60 transition text-xs font-mono">
                            <div class="flex items-center gap-1.5 overflow-hidden">
                                ${keyBadge}
                                <span class="${isPk ? 'text-amber-200 font-bold' : (isFk ? 'text-sky-200' : 'text-slate-300')} truncate">${attr.name}</span>
                                ${refInfo}
                            </div>
                            <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">${attr.type}</span>
                        </div>
                    `;
                }).join('');

                const cardKey = `ent-card-${containerId}-${ent.id}`;
                const bodyKey = `ent-body-${containerId}-${ent.id}`;
                const isExpanded = archifyEntitiesExpanded[ent.id] !== false; // default expanded

                return `
                    <div id="${cardKey}" class="bg-slate-950 border border-slate-800/90 rounded-xl overflow-hidden shadow flex flex-col transition-all">
                        <div class="flex items-center justify-between p-2.5 bg-slate-900/90 border-b border-slate-800 cursor-pointer select-none" onclick="toggleArchifyEntityCard('${ent.id}', '${containerId}')">
                            <div class="flex items-center gap-2">
                                <span class="text-sky-400 text-xs">🗄️</span>
                                <span class="font-mono font-semibold text-slate-200 text-xs">${ent.id}</span>
                                <span class="text-[10px] px-1.5 py-0.2 rounded border ${tagClass}">${ent.tag}</span>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                                    ${matchingAttrs.length}${matchingAttrs.length !== ent.attributes.length ? '/' + ent.attributes.length : ''} cols
                                </span>
                                <button id="btn-toggle-${cardKey}" title="Colapsar / Maximizar Entidad" class="text-slate-400 hover:text-white text-xs font-mono px-1">
                                    ${isExpanded ? '▲' : '▼'}
                                </button>
                            </div>
                        </div>
                        <div id="${bodyKey}" class="${isExpanded ? '' : 'hidden'} overflow-y-auto ${isModal ? 'max-h-[380px]' : 'max-h-56'} divide-y divide-slate-800/40 custom-scrollbar">
                            ${attrRows || '<p class="text-slate-600 text-xs italic p-2">Sin columnas coincidentes</p>'}
                        </div>
                    </div>
                `;
            }).join('');

            container.innerHTML = cardsHtml || '<p class="text-slate-500 text-xs italic p-4">No se encontraron atributos con el filtro aplicado.</p>';

            const statsBadge = document.getElementById(isModal ? (containerId.includes('split') ? 'modal-split-filter-stats' : 'modal-archify-filter-stats') : 'archify-filter-stats');
            if (statsBadge) {
                statsBadge.innerText = `${visibleAttrs} de ${totalAttrs} atributos en ${currentArchifyEntities.length} entidades`;
            }
        }

        function toggleArchifyEntityCard(entityId, containerId) {
            const body = document.getElementById(`ent-body-${containerId}-${entityId}`);
            const btn = document.getElementById(`btn-toggle-ent-card-${containerId}-${entityId}`);
            if (!body) return;
            const isNowHidden = !body.classList.contains('hidden');
            if (isNowHidden) {
                body.classList.add('hidden');
                if (btn) btn.innerText = '▼';
                archifyEntitiesExpanded[entityId] = false;
            } else {
                body.classList.remove('hidden');
                if (btn) btn.innerText = '▲';
                archifyEntitiesExpanded[entityId] = true;
            }
        }

        function expandAllArchifyEntities(expand, containerId) {
            if (!currentArchifyEntities) return;
            currentArchifyEntities.forEach(ent => {
                archifyEntitiesExpanded[ent.id] = expand;
                const body = document.getElementById(`ent-body-${containerId}-${ent.id}`);
                const btn = document.getElementById(`btn-toggle-ent-card-${containerId}-${ent.id}`);
                if (body) {
                    if (expand) body.classList.remove('hidden');
                    else body.classList.add('hidden');
                }
                if (btn) {
                    btn.innerText = expand ? '▲' : '▼';
                }
            });
        }

        function filterArchifyAttributes() {
            const q = document.getElementById('archify-attr-filter')?.value || '';
            renderArchifyInspectorCards('archify-inspector-cards', false, q);
        }

        function filterModalArchifyAttributes() {
            const q = document.getElementById('modal-archify-filter')?.value || '';
            renderArchifyInspectorCards('modal-archify-cards', true, q);
        }

        function filterModalSplitArchifyAttributes() {
            const q = document.getElementById('modal-split-filter')?.value || '';
            renderArchifyInspectorCards('modal-split-archify-cards', true, q);
        }

        // Enter key to submit
        document.getElementById('query-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                executeQuery();
            }
        });

        loadEngines();

        // Check URL parameters for engine and query (e.g. from documentation portal)
        const urlParams = new URLSearchParams(window.location.search);
        const paramEngine = urlParams.get('engine');
        const paramQuery = urlParams.get('q');
        if (paramEngine) {
            switchEngine(paramEngine).then(() => {
                if (paramQuery) {
                    setQuery(paramQuery);
                }
            });
        } else if (paramQuery) {
            setQuery(paramQuery);
        }

        window.addEventListener('resize', () => {
            if (chartInstance) chartInstance.resize();
            if (fullscreenChartInstance && !document.getElementById('fullscreen-modal').classList.contains('hidden')) {
                fullscreenChartInstance.resize();
            }
        });
    </script>
</body>
</html>"""
    json_catalog = json.dumps(DATABASE_CATALOG)
    final_content = html_content.replace(
        "/* DATABASE_CATALOG_PLACEHOLDER */",
        f"const DATABASE_CATALOG = {json_catalog};"
    )
    return HTMLResponse(
        content=final_content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )
