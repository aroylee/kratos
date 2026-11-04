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

            <div id="suggested-container" class="hidden bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
                <h3 class="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-2 flex items-center gap-1.5">
                    <span>💡</span> Preguntas Analíticas Sugeridas
                </h3>
                <div id="suggested-chips" class="flex flex-wrap gap-1.5 text-xs"></div>
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
            <!-- Tarjeta de Gráfico con Controles Interactivos -->
            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-xl">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-3 border-b border-slate-800/80 mb-3 gap-2">
                    <div class="flex items-center gap-2">
                        <span class="text-sm">📈</span>
                        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-300">Visualización Analítica Interactiva</h3>
                        <span id="chart-type-badge" class="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-400 border border-indigo-800">ECharts 5</span>
                    </div>
                    <div class="flex items-center gap-1.5 flex-wrap">
                        <span class="text-[11px] text-slate-500 mr-1 hidden sm:inline">Modo:</span>
                        <button onclick="changeChartType('line')" id="btn-chart-line" class="chart-type-btn px-2.5 py-1 text-xs rounded bg-indigo-600 border border-indigo-500 text-white font-medium transition shadow-sm">📈 Línea</button>
                        <button onclick="changeChartType('bar')" id="btn-chart-bar" class="chart-type-btn px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">📊 Barra</button>
                        <button onclick="changeChartType('area')" id="btn-chart-area" class="chart-type-btn px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition">🏔️ Área</button>
                        <button onclick="downloadChartImage()" title="Descargar Imagen PNG" class="px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-600 transition flex items-center gap-1">
                            <span>📸</span> PNG
                        </button>
                    </div>
                </div>
                <div id="chart-container" style="height: 390px; width: 100%;"></div>
            </div>

            <!-- Tarjeta de Tabla de Evidencias con Búsqueda y Exportación -->
            <div class="bg-slate-900/90 border border-slate-800 p-4 rounded-xl shadow-xl">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-3 border-b border-slate-800/80 mb-3 gap-2">
                    <div class="flex items-center gap-2">
                        <span class="text-sm">📋</span>
                        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-300">Registros de Evidencia Auditada</h3>
                        <span id="table-row-count-badge" class="hidden text-[11px] font-mono bg-slate-950 text-slate-400 px-2 py-0.5 rounded border border-slate-800"></span>
                    </div>
                    <div class="flex items-center gap-2 w-full sm:w-auto">
                        <div class="relative flex-1 sm:w-48">
                            <input type="text" id="table-search-input" oninput="filterTableRows()" placeholder="🔍 Filtrar registros..." class="w-full bg-slate-950 border border-slate-800 text-slate-300 rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:border-indigo-500">
                        </div>
                        <button onclick="exportTableToCSV()" class="px-2.5 py-1 text-xs rounded-lg bg-slate-950 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-600 transition flex items-center gap-1">
                            <span>📥</span> CSV
                        </button>
                    </div>
                </div>
                <div id="table-container" class="text-xs overflow-x-auto">
                    <p class="text-slate-600 p-2 italic">Sin registros cargados.</p>
                </div>
            </div>
        </section>
    </main>

    <script>
        let chartInstance = echarts.init(document.getElementById('chart-container'), 'dark');
        let currentEngine = 'northwind';
        let enginesData = [];
        let currentChartOption = null;
        let currentChartMode = 'line';
        let currentRawRows = [];
        let currentRawCols = [];
        let currentColMeta = [];

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
            const clean = col.toLowerCase().replace(/[_\-\s]+/g, '');
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
                renderContractChips(data.task);

                // Render Advanced Executive Storytelling
                const story = data.storytelling;
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
                renderSuggestedQuestions(data.suggested_questions);

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
                    document.getElementById('audit-container').innerHTML = `
                        <p class="text-amber-400">${data.evidence.warnings.join(' | ') || 'Consulta procesada sin queries SQL directas.'}</p>
                    `;
                    document.getElementById('table-container').innerHTML = '<p class="text-slate-500 italic p-2">Sin registros devueltos.</p>';
                }

                // Render Chart & store options for dynamic switching
                if (data.visualization) {
                    currentChartOption = data.visualization;
                    chartInstance.setOption(currentChartOption, true);
                    updateChartTypeButtons(currentChartMode);
                } else {
                    currentChartOption = null;
                    chartInstance.clear();
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
            if (!currentChartOption || !currentChartOption.series) return;
            currentChartMode = newType;
            updateChartTypeButtons(newType);

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
        }

        function updateChartTypeButtons(activeType) {
            ['line', 'bar', 'area'].forEach(t => {
                const btn = document.getElementById(`btn-chart-${t}`);
                if (!btn) return;
                if (t === activeType) {
                    btn.className = "chart-type-btn px-2.5 py-1 text-xs rounded bg-indigo-600 border border-indigo-500 text-white font-medium transition shadow-sm";
                } else {
                    btn.className = "chart-type-btn px-2.5 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white transition";
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
