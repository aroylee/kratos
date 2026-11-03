# 🛡️ Kratos — Sovereign Data Intelligence & Governance Framework

> **A contract-driven, AST-governed multi-engine conversational data intelligence platform.**

---

## ⚡ Overview

**Kratos** fuses the best paradigms of modern conversational analytics:
1. **Contract-Driven Agent Orchestration:** Strict `DataTask -> DataEvidence -> FinalAnswer` pipelines, eliminating unbounded LLM chat loops.
2. **4-Layer AST SQL Defense:** AST verification powered by `sqlglot` that detects and neutralizes mutations, CTE exploits, system table access, and runaway query complexity.
3. **Semantic Unit & Metric Intelligence:** Strict metric differentiation (`$ USD`, `%`, `días`, `pedidos`, `unidades`) preventing the hallucination of non-additive statistics or wrong units.
4. **Multi-Engine In-Process Analytics:** Hot auto-discovery of analytical databases (DuckDB, SQLite) and native read-only transactional safety.

---

## 🚀 Quickstart

```bash
# Run with uv
uv run uvicorn kratos.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` to interact with the dashboard.
