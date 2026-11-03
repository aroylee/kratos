# 📜 Kratos Context & Evolution Manifesto

> **Historial de Decisiones de Arquitectura, Comparativas y Evolución hacia Kratos.**

---

## 🧭 1. Génesis y Propósito

**Kratos** nació de la necesidad de sintetizar las mejores lecciones de ingeniería obtenidas en tres proyectos analíticos previos, destilándolas en una plataforma personal, moderna y soberana para GitHub sin acoplamientos institucionales:

1. **`nlp2sql`**:
   - **Lo adoptado:** Inferencia soberana desacoplada vía **LiteLLM Gateway** (LAN / vLLM / Ollama), poda quirúrgica de esquemas (**Schema Pruning**) que reduce el contexto en 75%, y consultas vectorizadas sobre Data Lakehouses.
2. **`agente-consultor`**:
   - **Lo adoptado:** Protocolo formal de contratos tipados con Pydantic (`DataTask -> DataEvidence -> FinalAnswer`), defensa en 4 capas con AST en `sqlglot` (sin regex), y bucle de investigación con presupuesto y auto-reflexión.
3. **`db_analytics`**:
   - **Lo adoptado:** Inteligencia semántica de unidades de negocio (`unit_utils.py`), generación heurística de visualizaciones Apache ECharts 5, framework de decisión ejecutiva (`ExecutiveStorytelling`), auto-descubrimiento en caliente de bases de datos y sustrato recursivo **Harness²**.

---

## 📐 2. El Protocolo de Contratos `DataTask`

Para erradicar el antipatrón de agentes que conversan entre sí en texto libre sin control:

```
[Usuario] 
   │
   ▼
[InterpreterAgent] ────────► Emite DataTask (Contrato Pydantic)
                                   │
                                   ▼
                            [InvestigatorAgent]
                                   │
                                   ├─► SchemaPruner (Poda 75% + Reglas)
                                   ├─► LLMClient / Heurística
                                   ├─► sqlglot 4-Layer Guard
                                   ├─► Read-Only Engine Execution
                                   │
                                   ▼
[InterpreterAgent] ◄──────── Devuelve DataEvidence (Hechos Numéricos Auditados)
   │
   ▼
[FinalAnswer] (Storytelling Ejecutivo + ECharts 5 + Preguntas Sugeridas)
```

---

## 🛡️ 3. Seguridad en 4 Capas con AST (`sqlglot`)

1. **Capa 1 (Motor):** Conexión física SQLite en modo URI `?mode=ro` o transacción `read_only=True`.
2. **Capa 2 (Protocolo/Sesión):** Timeouts a nivel de conexión y límites de ejecución.
3. **Capa 3 (AST Determinista):** `sqlglot` parsea la consulta y bloquea recursivamente:
   - Cualquier nodo de mutación (`DROP`, `DELETE`, `UPDATE`, `ALTER`, `TRUNCATE`, `MERGE`, `COPY`, `VACUUM`).
   - Explotación de CTEs: `WITH x AS (DELETE ...) SELECT * FROM x` es interceptado en el árbol.
   - Funciones peligrosas de disco o ejecución de comandos (`pg_read_file`, `read_csv`, `pg_sleep`).
   - Bloqueo de locks (`FOR UPDATE`, `FOR SHARE`) y creación de tablas (`SELECT ... INTO`).
   - Inyección automática y acotación de `LIMIT 500`.
4. **Capa 4 (Runtime):** Bounding forzoso con `fetchmany(max_rows + 1)` y bandera `truncated`.

---

## 🔬 4. Sustrato de Optimización Harness²

Kratos incorpora nativamente el sustrato de **Harness²** (Google Research, arXiv:2610.14224):
* **Auditoría de los 8 componentes de arnés:** Prompts, guardrails, memoria, contratos, agentes, unidades, motores e interfaces.
* **Evaluación de Benchmark:** 6 tareas analíticas multi-motor con 100% de tasa de éxito y latencia media de ~78 ms.
* Ejecución: `uv run kratos harness`.
