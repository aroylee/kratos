"""Kratos FastAPI Web Application & API Endpoints."""

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kratos.engines.registry import EngineRegistry
from kratos.agents.orchestrator import InterpreterAgent, InvestigatorAgent
from kratos.contracts.schemas import DataTask, FinalAnswer
from kratos.semantics.bi_engine import compile_echarts

app = FastAPI(title="Kratos Intelligence", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

registry = EngineRegistry(DATA_DIR)
interpreter = InterpreterAgent()
investigator = InvestigatorAgent(registry)


class QueryRequest(BaseModel):
    query: str
    engine_id: str | None = None


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
            {"id": eid, "tables_count": len(eng.get_tables()), "is_active": (eid == registry.active_engine_id)}
            for eid, eng in registry.engines.items()
        ]
    }


@app.post("/api/engines/select")
def select_engine(payload: dict):
    engine_id = payload.get("engine_id")
    try:
        registry.set_active(engine_id)
        return {"ok": True, "active": registry.active_engine_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/schema")
def get_schema():
    active = registry.get_active()
    return {"engine_id": active.engine_id, "schema": active.introspect()}


@app.post("/api/query")
def run_query(req: QueryRequest):
    engine_id = req.engine_id or registry.active_engine_id
    if engine_id not in registry.engines:
        registry.discover()

    # Step 1: Interpreter parses request
    interpreted = interpreter.interpret(req.query, engine_id)

    # Step 2: Formal DataTask creation
    task = DataTask(
        intent=interpreted.intent,
        engine_id=engine_id,
        goal=interpreted.goal,
        constraints=interpreted.constraints,
        required_evidence=interpreted.required_evidence,
    )

    # Step 3: Investigator executes task with 4-layer security
    evidence = investigator.execute_task(task)

    # Step 4: Storytelling & Visualization
    storytelling = interpreter.formulate_storytelling(task, evidence)
    rows = evidence.queries[0].rows if evidence.queries else []
    echarts = compile_echarts(rows, title=task.goal)

    return FinalAnswer(
        storytelling=storytelling,
        evidence=evidence,
        visualization=echarts,
        suggested_questions=[
            "Ver distribución por país",
            "Consultar top 5 entidades líderes",
            "Explorar resumen del esquema",
        ]
    )


@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>KRATOS // Sovereign Data Intelligence</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            body { background: #0b0f19; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        </style>
    </head>
    <body class="min-h-screen p-6 max-w-7xl mx-auto">
        <header class="flex justify-between items-center pb-6 border-b border-slate-800">
            <div>
                <h1 class="text-3xl font-black tracking-wider text-white">KRATOS</h1>
                <p class="text-sm text-slate-400">Sovereign Data Intelligence &bull; Contracts Protocol &bull; 4-Layer AST Security</p>
            </div>
            <div id="engine-selector-container" class="flex gap-2"></div>
        </header>

        <main class="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
            <section class="lg:col-span-1 space-y-4">
                <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Consulta en Lenguaje Natural</label>
                    <textarea id="query-input" rows="3" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm focus:outline-none focus:border-indigo-500" placeholder="Ej: ¿Cuáles son las ventas por categoría?"></textarea>
                    <button onclick="executeQuery()" class="mt-3 w-full bg-indigo-600 hover:bg-indigo-500 font-medium py-2 rounded-lg text-sm transition">Ejecutar Análisis</button>
                </div>

                <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Resumen Ejecutivo</h3>
                    <div id="storytelling-container" class="text-sm space-y-2 text-slate-300">
                        <p class="text-slate-500 italic">Escribe una pregunta y presiona ejecutar.</p>
                    </div>
                </div>

                <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Auditoría DataTask</h3>
                    <div id="audit-container" class="text-xs font-mono space-y-1 text-slate-400 overflow-x-auto">
                        <p class="text-slate-600">Sin ejecuciones recientes.</p>
                    </div>
                </div>
            </section>

            <section class="lg:col-span-2 space-y-4">
                <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Visualización Analítica (ECharts 5)</h3>
                    <div id="chart-container" style="height: 380px; width: 100%;"></div>
                </div>

                <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl overflow-x-auto">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Registros de Evidencia</h3>
                    <div id="table-container" class="text-xs"></div>
                </div>
            </section>
        </main>

        <script>
            let chartInstance = echarts.init(document.getElementById('chart-container'), 'dark');
            let currentEngine = 'northwind';

            async function loadEngines() {
                const res = await fetch('/api/engines');
                const data = await res.json();
                currentEngine = data.active;
                const container = document.getElementById('engine-selector-container');
                container.innerHTML = data.engines.map(e => `
                    <button onclick="switchEngine('${e.id}')" class="px-3 py-1 text-xs rounded-lg border ${e.id === currentEngine ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'}">
                        ${e.id.toUpperCase()} (${e.tables_count})
                    </button>
                `).join('');
            }

            async function switchEngine(id) {
                await fetch('/api/engines/select', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({engine_id: id})
                });
                await loadEngines();
            }

            async function executeQuery() {
                const query = document.getElementById('query-input').value.trim();
                if (!query) return;

                const res = await fetch('/api/query', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query, engine_id: currentEngine})
                });
                const data = await res.json();

                // Render Storytelling
                const story = data.storytelling;
                document.getElementById('storytelling-container').innerHTML = `
                    <p class="font-bold text-indigo-300">${story.key_takeaway}</p>
                    <ul class="list-disc pl-4 space-y-1 text-slate-300">
                        ${story.quantitative_findings.map(f => `<li>${f}</li>`).join('')}
                    </ul>
                `;

                // Render Audit
                const q = data.evidence.queries[0];
                document.getElementById('audit-container').innerHTML = `
                    <p><span class="text-indigo-400">SQL:</span> ${q.sql}</p>
                    <p><span class="text-emerald-400">Latencia:</span> ${q.execution_ms} ms &bull; <span class="text-blue-400">Filas:</span> ${q.row_count}</p>
                `;

                // Render Chart
                if (data.visualization) {
                    chartInstance.setOption(data.visualization, true);
                }

                // Render Table
                if (q.rows && q.rows.length > 0) {
                    const cols = Object.keys(q.rows[0]);
                    document.getElementById('table-container').innerHTML = `
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="border-b border-slate-800 text-slate-400">
                                    ${cols.map(c => `<th class="p-2">${c}</th>`).join('')}
                                </tr>
                            </thead>
                            <tbody>
                                ${q.rows.slice(0, 10).map(r => `
                                    <tr class="border-b border-slate-900 hover:bg-slate-800/50">
                                        ${cols.map(c => `<td class="p-2 text-slate-300">${r[c]}</td>`).join('')}
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `;
                }
            }

            loadEngines();
            window.addEventListener('resize', () => chartInstance.resize());
        </script>
    </body>
    </html>
    """
