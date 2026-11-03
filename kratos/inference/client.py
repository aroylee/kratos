"""Kratos Sovereign LLM Client with LiteLLM & Local Fallbacks."""

import os
import re
from typing import Dict, List, Optional
import litellm


class LLMClient:
    """Dispatches queries to local (vLLM/Ollama/LiteLLM) or remote providers with fallback."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model = model or os.getenv("KRATOS_LLM_MODEL", "openai/vllm-auto")
        self.api_base = api_base or os.getenv("KRATOS_LLM_API_BASE", "http://localhost:4000/v1")
        self.api_key = api_key or os.getenv("KRATOS_LLM_API_KEY", "dummy-key")
        litellm.suppress_debug_info = True

    def generate_sql(
        self,
        goal: str,
        engine_id: str,
        pruned_schema: Dict[str, List[str]],
        rules: List[str],
        dialect: str = "sqlite"
    ) -> Optional[str]:
        """Calls the configured LLM to generate dialect-specific SQL."""
        schema_desc = "\n".join(
            f"Tabla '{t}': {', '.join(cols)}" for t, cols in pruned_schema.items()
        )
        rules_desc = "\n".join(f"- {r}" for r in rules)

        prompt = f"""Eres Kratos SQL Generator. Convierte la solicitud del usuario en una consulta SQL de solo lectura (SELECT).
Dialecto: {dialect}
Motor: {engine_id}

Esquema Podado:
{schema_desc}

Reglas de Negocio:
{rules_desc}

Instrucciones estrictas:
1. Genera únicamente código SQL envuelto en bloque ```sql ... ```.
2. NUNCA generes DROP, DELETE, UPDATE, INSERT, ALTER o TRUNCATE.
3. Utiliza alias legibles para métricas (ej. Ventas_USD, Clientes, Facturacion_USD).
4. Limita los resultados a 10 filas (LIMIT 10).

Solicitud del usuario: {goal}
"""

        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=10,
                temperature=0.0,
            )
            content = response.choices[0].message.content or ""
            match = re.search(r"```sql\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
            # If plain SQL was returned
            clean_content = content.strip().strip("`")
            if clean_content.upper().startswith("SELECT") or clean_content.upper().startswith("WITH"):
                return clean_content
            return None
        except Exception:
            # Fallback cleanly when offline or LLM server is unreachable
            return None
