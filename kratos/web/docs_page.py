"""Kratos Interactive Documentation Web Page."""

def get_documentation_html() -> str:
    """Returns the standalone HTML for the Kratos architecture and documentation portal."""
    return """<!DOCTYPE html>
<html lang="es" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KRATOS // Arquitectura y Documentación</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        body { background: #0b0f19; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .mermaid { background: #0f172a; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid #1e293b; }
        .mermaid svg { max-width: 100%; height: auto; }
    </style>
</head>
<body class="min-h-screen p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <header class="flex flex-col md:flex-row justify-between items-start md:items-center pb-6 border-b border-slate-800 gap-4">
        <div>
            <div class="flex items-center gap-3">
                <span class="text-2xl">🛡️</span>
                <h1 class="text-3xl font-black tracking-wider text-white">KRATOS</h1>
                <span class="bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 text-xs px-2.5 py-1 rounded-full font-semibold">Docs v0.1.0</span>
            </div>
            <p class="text-sm text-slate-400 mt-1">Sovereign Data Intelligence &bull; Contracts Protocol &bull; 4-Layer AST Security</p>
        </div>

        <nav class="flex items-center gap-2">
            <a href="/" class="px-3.5 py-1.5 text-xs rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:text-white hover:bg-slate-800 transition flex items-center gap-1.5">
                <span>📊</span> Dashboard
            </a>
            <a href="/documentation" class="px-3.5 py-1.5 text-xs rounded-lg border border-indigo-500 bg-indigo-600 text-white font-medium flex items-center gap-1.5">
                <span>📖</span> Documentación
            </a>
            <a href="/docs" target="_blank" class="px-3.5 py-1.5 text-xs rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:text-white hover:bg-slate-800 transition flex items-center gap-1.5">
                <span>⚡</span> API Swagger
            </a>
            <a href="https://github.com/aroylee/kratos" target="_blank" class="px-3.5 py-1.5 text-xs rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:text-white hover:bg-slate-800 transition flex items-center gap-1.5">
                <span>🐙</span> GitHub
            </a>
        </nav>
    </header>

    <!-- Sub-Navbar de Navegación Rápida -->
    <div class="sticky top-0 z-30 bg-[#0b0f19]/95 backdrop-blur py-3 border-b border-slate-800/80 my-4 flex gap-2 overflow-x-auto text-xs">
        <a href="#vision" class="px-3 py-1 rounded-md bg-slate-900 text-slate-300 hover:text-white border border-slate-800">🎯 Visión y Problema</a>
        <a href="#restaurante" class="px-3 py-1 rounded-md bg-slate-900 text-slate-300 hover:text-white border border-slate-800">🏛️ Analogía del Restaurante</a>
        <a href="#arquitectura" class="px-3 py-1 rounded-md bg-slate-900 text-slate-300 hover:text-white border border-slate-800">🗺️ Diagrama General</a>
        <a href="#componentes" class="px-3 py-1 rounded-md bg-slate-900 text-slate-300 hover:text-white border border-slate-800">🧩 Componentes Clave</a>
        <a href="#seguridad" class="px-3 py-1 rounded-md bg-slate-900 text-slate-300 hover:text-white border border-slate-800">🛡️ Seguridad en 4 Capas</a>
        <a href="#flujo" class="px-3 py-1 rounded-md bg-slate-900 text-slate-300 hover:text-white border border-slate-800">🔄 Flujo de una Consulta</a>
    </div>

    <main class="space-y-12 mt-6">
        <!-- Sección 1: Visión y Problema -->
        <section id="vision" class="bg-slate-900/60 border border-slate-800 p-6 md:p-8 rounded-2xl">
            <h2 class="text-xl font-bold text-white flex items-center gap-2 mb-3">
                <span>🎯</span> ¿Qué es Kratos y qué problema resuelve?
            </h2>
            <p class="text-slate-300 leading-relaxed mb-4 text-sm md:text-base">
                Cuando una empresa o analista le pide a una Inteligencia Artificial tradicional que analice su base de datos (por ejemplo: <em class="text-indigo-300">"¿cuánto vendimos el último mes?"</em>), ocurren 3 peligros graves:
            </p>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs md:text-sm">
                <div class="bg-red-950/30 border border-red-900/40 p-4 rounded-xl">
                    <p class="font-bold text-red-300 mb-1">❌ 1. Alucinación de Números</p>
                    <p class="text-slate-400">La IA inventa cifras o confunde unidades (afirma "$500 dólares" cuando en realidad eran "500 cajas de producto").</p>
                </div>
                <div class="bg-amber-950/30 border border-amber-900/40 p-4 rounded-xl">
                    <p class="font-bold text-amber-300 mb-1">⚠️ 2. Riesgo de Destrucción</p>
                    <p class="text-slate-400">Si un usuario escribe una trampa o hay un error, la IA puede emitir sentencias como <code class="text-red-400">DROP</code> o <code class="text-red-400">DELETE</code> y vaciar la base de datos.</p>
                </div>
                <div class="bg-purple-950/30 border border-purple-900/40 p-4 rounded-xl">
                    <p class="font-bold text-purple-300 mb-1">🌀 3. Agentes Descontrolados</p>
                    <p class="text-slate-400">Los agentes de IA empiezan a "charlar" entre sí en texto libre sin límites, gastando miles de tokens y perdiéndose en bucles.</p>
                </div>
            </div>
            <p class="text-slate-300 mt-4 text-sm bg-indigo-950/30 border border-indigo-900/50 p-3 rounded-lg">
                <strong class="text-indigo-300">La solución de Kratos:</strong> Trata a la base de datos como un banco suizo. Los agentes solo pueden hablar mediante <strong>contratos formales estrictos</strong>, cada consulta pasa por un <strong>detector de metales matemático en 4 capas (AST)</strong> que destruye cualquier comando destructivo, y un <strong>motor semántico</strong> certifica que los dólares jamás se confundan con cajas o días.
            </p>
        </section>

        <!-- Sección 2: Analogía del Restaurante -->
        <section id="restaurante" class="bg-slate-900/60 border border-slate-800 p-6 md:p-8 rounded-2xl">
            <h2 class="text-xl font-bold text-white flex items-center gap-2 mb-3">
                <span>🏛️</span> Kratos explicado como un Restaurante de Alta Cocina
            </h2>
            <p class="text-slate-300 text-sm md:text-base mb-6 leading-relaxed">
                Si no eres experto en software ni en bases de datos, imagina a Kratos como la cocina de un restaurante gourmet con las reglas de higiene más estrictas del mundo:
            </p>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs md:text-sm">
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">🤵</div>
                    <h3 class="font-bold text-indigo-300">1. El Capitán de Meseros</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">InterpreterAgent</p>
                    <p class="text-slate-300">Escucha al comensal, comprende qué quiere comer y anota la orden en una comanda formal inmutable.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">📜</div>
                    <h3 class="font-bold text-indigo-300">2. La Comanda Formal</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">Contrato DataTask</p>
                    <p class="text-slate-300">Es la orden por escrito con casillas obligatorias. Nadie cocina nada si la comanda no tiene casillas claras.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">👨‍🍳</div>
                    <h3 class="font-bold text-indigo-300">3. El Chef Investigador</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">InvestigatorAgent</p>
                    <p class="text-slate-300">Recibe la comanda y planea cómo preparar los datos necesarios de la despensa.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">🧺</div>
                    <h3 class="font-bold text-indigo-300">4. El Ayudante Archivista</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">SchemaPruner</p>
                    <p class="text-slate-300">En vez de sacar 50 ingredientes y llenar la mesa de desorden, saca solo los 2 o 3 ingredientes que la receta necesita.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">👮</div>
                    <h3 class="font-bold text-indigo-300">5. El Inspector Sanitario</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">4-Layer AST Guard</p>
                    <p class="text-slate-300">Revisa la receta antes de tocar la cocina. Si detecta peligro o veneno (DROP, DELETE), confisca la orden de inmediato.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">❄️</div>
                    <h3 class="font-bold text-indigo-300">6. Las Despensas en Frío</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">DuckDB & SQLite</p>
                    <p class="text-slate-300">Despensas ultrarrápidas en disco dentro del mismo restaurante. No hay que viajar a un almacén externo (sin Docker).</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">⚖️</div>
                    <h3 class="font-bold text-indigo-300">7. La Balanza de Precisión</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">Semantic Unit Intelligence</p>
                    <p class="text-slate-300">Verifica que los gramos no se confundan con dólares. Cada número sale con su etiqueta exacta.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">🍷</div>
                    <h3 class="font-bold text-indigo-300">8. El Sommelier Presentador</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">ExecutiveStorytelling</p>
                    <p class="text-slate-300">Le explica al comensal en 2 oraciones qué significan los datos y qué decisión de negocio le conviene tomar.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div class="text-2xl mb-2">🎨</div>
                    <h3 class="font-bold text-indigo-300">9. El Emplatador Visual</h3>
                    <p class="text-slate-400 font-mono text-xs mb-2">Apache ECharts 5</p>
                    <p class="text-slate-300">Presenta el plato de forma hermosa: barras, donas o líneas según el tipo de datos, listo para el comensal.</p>
                </div>
            </div>
        </section>

        <!-- Sección 3: Diagrama General de Arquitectura -->
        <section id="arquitectura" class="bg-slate-900/60 border border-slate-800 p-6 md:p-8 rounded-2xl">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold text-white flex items-center gap-2">
                    <span>🗺️</span> Diagrama General de Arquitectura (Archify / Mermaid)
                </h2>
                <span class="text-xs text-slate-500 font-mono">Renderizado en vivo</span>
            </div>
            <p class="text-slate-400 text-xs md:text-sm mb-4">
                El siguiente diagrama representa cómo los datos y las instrucciones fluyen a través de las 4 capas de Kratos:
            </p>
            <div class="mermaid">
flowchart TD
    subgraph CapaUsuario ["👤 1. Interfaz y Recepción"]
        User(["Usuario"]) -->|Pregunta Natural| WebUI["FastAPI Dashboard & Endpoint /api/query"]
    end

    subgraph AgenteInterprete ["🧠 2. Intérprete de Intenciones"]
        WebUI --> Int["InterpreterAgent\n(Clasifica Intent)"]
        Int --> TaskBuilder["Constructor de Contrato Pydantic"]
        TaskBuilder --> Contract["📜 Contrato DataTask"]
    end

    subgraph AgenteInvestigador ["🔍 3. Investigador y Seguridad"]
        Contract --> Inv["InvestigatorAgent"]
        Inv --> Pruner["Schema Pruner\n(Poda 75% + Reglas de negocio)"]
        Pruner --> Guard["🛡️ 4-Layer AST Guard\n(sqlglot: Sin mutaciones, LIMIT 500)"]
    end

    subgraph Motores ["🗄️ 4. Motores Analíticos Embebidos"]
        Guard --> Registry["Engine Registry (In-Process)"]
        Registry --> DBNorthwind[("northwind.db\n(E-commerce)")]
        Registry --> DBChinook[("chinook.db\n(Música)")]
        Registry --> DBSakila[("sakila.db\n(Películas)")]
        Registry --> DBAdv[("adventureworks_dw.db")]
        Registry --> DBTPCH[("tpch.db")]
        Registry --> Evidence["📊 Contrato DataEvidence\n(Filas auditadas + Metadatos)"]
    end

    subgraph CapaPresentacion ["📈 5. Presentación y Storytelling"]
        Evidence --> Semantics["Auditor de Unidades Semánticas\n($, %, días, pedidos, uds)"]
        Semantics --> Story["Executive Storytelling\n(Conclusiones para decisiones)"]
        Evidence --> ECharts["Compilador Visual ECharts 5"]
        Story & ECharts --> Final["FinalAnswer Payload"]
        Final --> WebUI
    end
            </div>
        </section>

        <!-- Sección 4: Los Componentes del Sistema -->
        <section id="componentes" class="bg-slate-900/60 border border-slate-800 p-6 md:p-8 rounded-2xl space-y-6">
            <h2 class="text-xl font-bold text-white flex items-center gap-2">
                <span>🧩</span> Desglose de Componentes Clave
            </h2>

            <div class="space-y-4">
                <!-- Componente 1 -->
                <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2 mb-2">
                        <h3 class="text-base font-bold text-indigo-300 flex items-center gap-2">
                            <span>1️⃣</span> El Agente Intérprete
                        </h3>
                        <span class="text-xs font-mono bg-slate-900 px-2 py-1 rounded text-slate-400">kratos/agents/orchestrator.py: InterpreterAgent</span>
                    </div>
                    <p class="text-slate-300 text-sm mb-2">
                        <strong>¿Qué hace en cristiano?</strong> Lee lo que escribe el usuario, detecta la verdadera intención (ejemplo: ¿quiere contar datos? ¿comparar períodos? ¿ver la estructura?) y genera la orden formal sin inventar nada.
                    </p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-slate-900/50 p-3 rounded-lg border border-slate-800/80">
                        <div><strong class="text-slate-400">Entrada:</strong> "Dime los clientes de México" (Texto libre)</div>
                        <div><strong class="text-indigo-400">Salida:</strong> <code class="text-indigo-300">DataTask(intent=FIND_DATA, goal="Listar clientes de México")</code></div>
                    </div>
                </div>

                <!-- Componente 2 -->
                <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2 mb-2">
                        <h3 class="text-base font-bold text-indigo-300 flex items-center gap-2">
                            <span>2️⃣</span> El Escudo de Seguridad AST en 4 Capas
                        </h3>
                        <span class="text-xs font-mono bg-slate-900 px-2 py-1 rounded text-slate-400">kratos/security/sql_guard.py: SQLGuard</span>
                    </div>
                    <p class="text-slate-300 text-sm mb-2">
                        <strong>¿Qué hace en cristiano?</strong> Desarma matemáticamente cualquier consulta SQL propuesta. Si alguien escribe o la IA sugiere un comando que modifique datos (<code class="text-red-400">DROP</code>, <code class="text-red-400">DELETE</code>, <code class="text-red-400">ALTER</code>, <code class="text-red-400">UPDATE</code>) o lea archivos del sistema (<code class="text-red-400">pg_read_file</code>), el escudo lo neutraliza y le añade un límite de 500 filas para no colapsar la memoria.
                    </p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-slate-900/50 p-3 rounded-lg border border-slate-800/80">
                        <div><strong class="text-slate-400">Entrada:</strong> Consulta SQL propuesta</div>
                        <div><strong class="text-emerald-400">Salida:</strong> Aprobado (SQL Sanitizado + LIMIT 500) o Rechazo Inmediato con Causa</div>
                    </div>
                </div>

                <!-- Componente 3 -->
                <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2 mb-2">
                        <h3 class="text-base font-bold text-indigo-300 flex items-center gap-2">
                            <span>3️⃣</span> El Podador de Esquemas (Schema Pruner)
                        </h3>
                        <span class="text-xs font-mono bg-slate-900 px-2 py-1 rounded text-slate-400">kratos/inference/schema_pruner.py: SchemaPruner</span>
                    </div>
                    <p class="text-slate-300 text-sm mb-2">
                        <strong>¿Qué hace en cristiano?</strong> Si una base de datos tiene 20 tablas, el podador se fija en las palabras clave y selecciona únicamente las 2 o 3 tablas que se necesitan. Esto ahorra un 75% de memoria y evita que la IA se confunda con tablas irrelevantes.
                    </p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-slate-900/50 p-3 rounded-lg border border-slate-800/80">
                        <div><strong class="text-slate-400">Entrada:</strong> Esquema completo (ej. 16 tablas) + Pregunta del usuario</div>
                        <div><strong class="text-indigo-400">Salida:</strong> 2-3 tablas relevantes + Fórmulas oficiales de negocio</div>
                    </div>
                </div>

                <!-- Componente 4 -->
                <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2 mb-2">
                        <h3 class="text-base font-bold text-indigo-300 flex items-center gap-2">
                            <span>4️⃣</span> Inteligencia Semántica de Unidades y Negocio
                        </h3>
                        <span class="text-xs font-mono bg-slate-900 px-2 py-1 rounded text-slate-400">kratos/semantics/unit_utils.py</span>
                    </div>
                    <p class="text-slate-300 text-sm mb-2">
                        <strong>¿Qué hace en cristiano?</strong> Identifica qué representa cada columna. Si se llama <code class="text-slate-300">Freight</code> sabe que son dólares ($), si se llama <code class="text-slate-300">Discount</code> sabe que es porcentaje (%), y si se llama <code class="text-slate-300">Orders</code> jamás le pondrá un signo de dólar.
                    </p>
                </div>

                <!-- Componente 5 -->
                <div class="bg-slate-950 border border-slate-800 p-5 rounded-xl">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2 mb-2">
                        <h3 class="text-base font-bold text-indigo-300 flex items-center gap-2">
                            <span>5️⃣</span> Sustrato Recursivo Harness²
                        </h3>
                        <span class="text-xs font-mono bg-slate-900 px-2 py-1 rounded text-slate-400">kratos/harness/agent.py</span>
                    </div>
                    <p class="text-slate-300 text-sm mb-2">
                        <strong>¿Qué hace en cristiano?</strong> Inspirado en investigaciones de Google Research, audita periódicamente los 8 componentes del sistema y corre un conjunto de 6 misiones de prueba multi-motor para certificar que todo responda en menos de 100 ms y con 100% de éxito.
                    </p>
                </div>
            </div>
        </section>

        <!-- Sección 5: Seguridad en 4 Capas -->
        <section id="seguridad" class="bg-slate-900/60 border border-slate-800 p-6 md:p-8 rounded-2xl">
            <h2 class="text-xl font-bold text-white flex items-center gap-2 mb-4">
                <span>🛡️</span> Las 4 Capas de Blindaje de Seguridad
            </h2>
            <div class="mermaid mb-6">
flowchart LR
    Q["Consulta SQL Candidata"] --> C1["1. Motor Físico\nModo Solo Lectura (?mode=ro)"]
    C1 --> C2["2. Límites de Sesión\nTimeouts de milisegundos"]
    C2 --> C3["3. AST Guard (sqlglot)\nDescompone el árbol y neutraliza mutaciones"]
    C3 --> C4["4. Runtime Bounding\nCorte forzoso a máx 500 filas"]
    C4 --> OK["✅ Ejecución Segura"]
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs md:text-sm">
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <h4 class="font-bold text-emerald-400 mb-1">Capa 1: Conexión en Solo Lectura</h4>
                    <p class="text-slate-400">El motor abre los archivos SQLite y DuckDB con parámetros estrictos de solo lectura. Incluso si se intentara escribir físicamente, el sistema operativo rechaza la operación.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <h4 class="font-bold text-emerald-400 mb-1">Capa 2: Límites de Sesión</h4>
                    <p class="text-slate-400">Si una consulta entra en un bucle o tarda demasiado en computar, se corta automáticamente para no congelar la máquina.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <h4 class="font-bold text-emerald-400 mb-1">Capa 3: Árbol AST (sqlglot)</h4>
                    <p class="text-slate-400">La consulta se desarma como un diagrama gramatical. Si detecta DROP, DELETE, UPDATE, ALTER, o lectura de archivos del disco, el query es destruido al instante.</p>
                </div>
                <div class="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <h4 class="font-bold text-emerald-400 mb-1">Capa 4: Bounding Forzoso de Filas</h4>
                    <p class="text-slate-400">Ninguna consulta puede devolver 1 millón de filas y comerse la memoria RAM. El guardia inyecta <code class="text-indigo-400">LIMIT 500</code> automáticamente.</p>
                </div>
            </div>
        </section>

        <!-- Sección 6: Flujo Secuencial -->
        <section id="flujo" class="bg-slate-900/60 border border-slate-800 p-6 md:p-8 rounded-2xl">
            <h2 class="text-xl font-bold text-white flex items-center gap-2 mb-4">
                <span>🔄</span> El Ciclo de Vida de una Consulta (Diagrama de Secuencia)
            </h2>
            <div class="mermaid">
sequenceDiagram
    autonumber
    actor U as Usuario
    participant API as FastAPI Web App
    participant IA as InterpreterAgent
    participant DT as Contrato DataTask
    participant IV as InvestigatorAgent
    participant SP as SchemaPruner
    participant SG as 4-Layer AST Guard
    participant DB as Motor de Datos (DuckDB/SQLite)
    participant BI as Semantic BI & ECharts

    U->>API: Escribe: "¿Cuáles son las ventas por categoría?"
    API->>IA: interpret("ventas por categoría", engine="northwind")
    IA->>DT: Genera DataTask(goal, intent=ANALYZE_DATA, engine_id="northwind")
    DT->>IV: execute_task(DataTask)
    
    IV->>SP: Solicita esquema reducido y reglas de cálculo
    SP-->>IV: Devuelve tablas clave y fórmulas oficiales
    
    IV->>IV: Formula consulta SQL candidata
    IV->>SG: inspect_and_sanitize(SQL)
    
    alt Consulta peligrosa o mutación
        SG-->>IV: RECHAZADO (RejectReason: not_read_only)
        IV-->>IA: Devuelve evidencia con advertencia de seguridad
    else Consulta segura
        SG-->>IV: APROBADO (Sanitized SQL con LIMIT 500)
        IV->>DB: Ejecuta en cursor READ-ONLY
        DB-->>IV: Retorna filas de datos (0.4 ms)
        IV-->>IA: Devuelve DataEvidence con filas auditadas
    end

    IA->>BI: compile_echarts(rows) + formulate_storytelling()
    BI-->>IA: Opciones ECharts 5 + Resumen Ejecutivo
    IA-->>API: Payload completo FinalAnswer
    API-->>U: Renderiza Gráfico Interactivo + Resumen Ejecutivo
            </div>
        </section>
    </main>

    <footer class="mt-16 pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
        <p>KRATOS &bull; Sovereign Multi-Engine Conversational Data Intelligence Platform &bull; Roy Lee</p>
    </footer>

    <script>
        mermaid.initialize({
            startOnLoad: true,
            theme: 'dark',
            themeVariables: {
                darkMode: true,
                background: '#0f172a',
                primaryColor: '#6366f1',
                primaryTextColor: '#ffffff',
                primaryBorderColor: '#4f46e5',
                lineColor: '#94a3b8',
                secondaryColor: '#1e293b',
                tertiaryColor: '#0b0f19'
            }
        });
    </script>
</body>
</html>
"""
