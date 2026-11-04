"""Kratos FastAPI Web Application & Sovereign API Endpoints."""

from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from kratos.engines.registry import EngineRegistry
from kratos.agents.orchestrator import InterpreterAgent, InvestigatorAgent
from kratos.contracts.schemas import DataTask, FinalAnswer
from kratos.semantics.bi_engine import compile_echarts
from kratos.web.docs_page import get_documentation_html

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

    return FinalAnswer(
        storytelling=storytelling,
        evidence=evidence,
        visualization=echarts,
        task=task,
        suggested_questions=[
            "Ver distribución por país",
            "Consultar top 5 entidades líderes",
            "Explorar resumen del esquema",
        ]
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
    html_content = """<!DOCTYPE html>
<html lang="es">
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
    <div class="mt-6 bg-slate-900/60 border border-slate-800 p-4 rounded-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div>
            <span class="text-xs uppercase tracking-wider font-semibold text-slate-400">Motor Analítico Activo:</span>
            <span id="active-engine-badge" class="ml-2 font-mono text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">Cargando...</span>
        </div>
        <div id="engine-selector-container" class="flex flex-wrap gap-2"></div>
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
            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                <div class="flex justify-between items-center mb-2">
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400">Consulta en Lenguaje Natural</label>
                    <span class="text-[10px] text-slate-500 font-mono">Presiona Enter ↵</span>
                </div>
                <textarea id="query-input" rows="3" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm focus:outline-none focus:border-indigo-500" placeholder="Ej: dame una tendencia de ventas diaria por categoría de las 3 categorías con mejor desempeño"></textarea>
                
                <!-- Chips de Contrato Interpretado (Grounding) -->
                <div id="contract-chips" class="mt-2 empty:hidden flex flex-wrap gap-1.5 text-[11px]"></div>

                <!-- Chips de Preguntas Rápidas -->
                <div class="mt-2.5 flex flex-wrap gap-1.5" id="sample-chips">
                    <button onclick="setQuery('ventas por categoría')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Ventas por categoría</button>
                    <button onclick="setQuery('ventas por empleado')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Ventas por empleado</button>
                    <button onclick="setQuery('tendencia de ventas diaria por categoría de las 3 categorías con mejor desempeño')" class="text-[11px] bg-slate-950 hover:bg-indigo-950 hover:text-indigo-300 text-slate-400 border border-slate-800 px-2 py-0.5 rounded transition">Top 3 Categorías diario</button>
                </div>

                <button id="run-btn" onclick="executeQuery()" class="mt-3 w-full bg-indigo-600 hover:bg-indigo-500 font-medium py-2 rounded-lg text-sm transition flex items-center justify-center gap-2">
                    <span>⚡</span> Ejecutar Análisis
                </button>
            </div>

            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Resumen Ejecutivo (Storytelling)</h3>
                <div id="storytelling-container" class="text-sm space-y-2 text-slate-300">
                    <p class="text-slate-500 italic">Escribe una pregunta o selecciona un chip y presiona ejecutar.</p>
                </div>
            </div>

            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Auditoría DataTask & 4-Layer AST</h3>
                <div id="audit-container" class="text-xs font-mono space-y-1 text-slate-400 overflow-x-auto">
                    <p class="text-slate-600">Sin ejecuciones recientes.</p>
                </div>
            </div>
        </section>

        <!-- Columna Derecha: Gráficos y Tablas -->
        <section class="lg:col-span-2 space-y-4">
            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Visualización Analítica (Apache ECharts 5)</h3>
                <div id="chart-container" style="height: 380px; width: 100%;"></div>
            </div>

            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl overflow-x-auto">
                <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Registros de Evidencia Auditada</h3>
                <div id="table-container" class="text-xs">
                    <p class="text-slate-600 p-2 italic">Sin registros cargados.</p>
                </div>
            </div>
        </section>
    </main>

    <script>
        let chartInstance = echarts.init(document.getElementById('chart-container'), 'dark');
        let currentEngine = 'northwind';
        let enginesData = [];

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
                renderContractChips(data.task);

                // Render Storytelling
                const story = data.storytelling;
                document.getElementById('storytelling-container').innerHTML = `
                    <p class="font-bold text-indigo-300">${story.key_takeaway}</p>
                    <ul class="list-disc pl-4 space-y-1 text-slate-300">
                        ${story.quantitative_findings.map(f => `<li>${f}</li>`).join('')}
                    </ul>
                `;

                // Render Audit
                const q = (data.evidence && data.evidence.queries && data.evidence.queries.length > 0) ? data.evidence.queries[0] : null;
                if (q) {
                    // Escape HTML for pre block
                    const escapedSql = q.sql.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    document.getElementById('audit-container').innerHTML = `
                        <div class="mb-2">
                            <span class="text-indigo-400 font-semibold block mb-1">SQL Formateado & Comentado:</span>
                            <pre class="bg-slate-950 p-3 rounded-lg border border-slate-800 text-slate-300 overflow-x-auto text-[11px] leading-relaxed font-mono whitespace-pre">${escapedSql}</pre>
                        </div>
                        <p class="mt-2 text-slate-400"><span class="text-emerald-400 font-semibold">Latencia:</span> ${q.execution_ms} ms &bull; <span class="text-blue-400 font-semibold">Filas:</span> ${q.row_count} &bull; <span class="text-purple-400 font-semibold">Motor:</span> ${data.evidence.engine_id.toUpperCase()}</p>
                    `;

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
                    } else {
                        document.getElementById('table-container').innerHTML = '<p class="text-slate-500 italic p-2">Sin registros devueltos.</p>';
                    }
                } else {
                    document.getElementById('audit-container').innerHTML = `
                        <p class="text-amber-400">${data.evidence.warnings.join(' | ') || 'Consulta procesada sin queries SQL directas.'}</p>
                    `;
                    document.getElementById('table-container').innerHTML = '<p class="text-slate-500 italic p-2">Sin registros devueltos.</p>';
                }

                // Render Chart
                if (data.visualization) {
                    chartInstance.setOption(data.visualization, true);
                } else {
                    chartInstance.clear();
                }
            } catch (err) {
                showAlert("Error de conexión: " + err.message);
            } finally {
                runBtn.disabled = false;
                runBtn.innerHTML = '<span>⚡</span> Ejecutar Análisis';
            }
        }

        // Enter key to submit
        document.getElementById('query-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                executeQuery();
            }
        });

        loadEngines();
        window.addEventListener('resize', () => chartInstance.resize());
    </script>
</body>
</html>"""
    return HTMLResponse(
        content=html_content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )
