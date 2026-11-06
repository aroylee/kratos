"""Kratos Sovereign Data Engineering Agent.

Automates end-to-end database onboarding, schema profiling, implicit/explicit
relationship discovery, Wren MDL semantic model generation, and 1:1 grounded ERD synthesis.
Allows pointing Kratos to any database file (.db, .sqlite, .duckdb) or directory of databases.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from kratos.engines.registry import DatabaseEngine, EngineRegistry
from kratos.ontology.auto_ontology import AutoOntologyExtractor, AutoOntologyService
from kratos.semantics.mdl import SemanticModelMDL


class IngestionReport(BaseModel):
    engine_id: str
    db_path: str
    tables_count: int
    columns_count: int
    relationships_count: int
    dimensions: List[str]
    metrics: List[str]
    yaml_path: Optional[str] = None
    grounded_erd: str


class DataEngineeringAgent:
    """Autonomous agent for data engineering, schema extraction, and semantic onboarding."""

    def __init__(self, models_dir: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.models_dir = (models_dir or (base_dir / "semantics" / "models")).resolve()
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def ingest_database(self, db_path: Path, engine_id: Optional[str] = None, overwrite: bool = False) -> IngestionReport:
        """Inspects, models, and registers a single database file."""
        db_path = Path(db_path).resolve()
        if not db_path.exists():
            raise FileNotFoundError(f"Archivo de base de datos no encontrado: {db_path}")

        eid = (engine_id or db_path.stem).lower().replace(" ", "_").replace("-", "_")
        engine = DatabaseEngine(eid, db_path)

        extractor = AutoOntologyExtractor(engine)
        model: SemanticModelMDL = extractor.extract()
        grounded_erd: str = extractor.generate_mermaid_erd()

        # Save Wren MDL YAML
        yaml_dest = self.models_dir / f"{eid}.yaml"
        if yaml_dest.exists() and not overwrite:
            # Avoid clobbering curated benchmark models unless overwrite is explicitly requested
            yaml_dest = self.models_dir / f"{eid}.auto.yaml"

        AutoOntologyService.export_to_yaml(model, yaml_dest)

        # Count total columns across tables
        total_cols = sum(len(e.primary_key) for e in model.entities)
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [r[0] for r in cursor.fetchall()]
            total_cols = 0
            for t in tables:
                cursor.execute(f"PRAGMA table_info('{t}');")
                total_cols += len(cursor.fetchall())
            conn.close()
        except Exception:
            pass

        return IngestionReport(
            engine_id=eid,
            db_path=str(db_path),
            tables_count=len(model.entities),
            columns_count=total_cols,
            relationships_count=len(model.relationships),
            dimensions=[d.id for d in model.dimensions],
            metrics=[m.id for m in model.metrics],
            yaml_path=str(yaml_dest),
            grounded_erd=grounded_erd
        )

    def ingest_path(self, target_path: Path, overwrite: bool = False) -> List[IngestionReport]:
        """Ingests a single database file OR recursively ingests an entire directory of data files."""
        target_path = Path(target_path).resolve()
        if not target_path.exists():
            raise FileNotFoundError(f"Ruta objetivo no encontrada: {target_path}")

        if target_path.is_file():
            return [self.ingest_database(target_path, overwrite=overwrite)]

        reports: List[IngestionReport] = []
        extensions = ["*.db", "*.sqlite", "*.sqlite3"]
        discovered_files: List[Path] = []
        for ext in extensions:
            discovered_files.extend(target_path.glob(ext))
            discovered_files.extend(target_path.glob(f"**/{ext}"))

        unique_files = sorted(list(set(discovered_files)))
        for f in unique_files:
            try:
                rep = self.ingest_database(f, overwrite=overwrite)
                reports.append(rep)
            except Exception as e:
                print(f"⚠️  Error al procesar '{f.name}': {e}")

        return reports

    def generate_grounded_erd_for_engine(self, engine: DatabaseEngine) -> str:
        """Synthesizes a 100% grounded Mermaid ERD directly from physical catalog introspection."""
        extractor = AutoOntologyExtractor(engine)
        return extractor.generate_mermaid_erd()
