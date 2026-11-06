"""Precompile interactive Archify ERD diagrams for all database engines."""

from pathlib import Path
from kratos.semantics.archify_generator import generate_full_database_archify_erd_spec, compile_archify_diagram

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "kratos" / "web" / "static" / "archify"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

ENGINES = ["northwind", "chinook", "sakila", "adventureworks_dw", "tpch", "el_salvador"]

def main():
    print("🎨 Precompilando diagramas interactivos Archify con TODOS los atributos y relaciones...")
    for eid in ENGINES:
        db_path = DATA_DIR / f"{eid}.db"
        if not db_path.exists():
            print(f"⚠️  {eid}: Archivo {db_path} no existe, omitiendo.")
            continue
        spec = generate_full_database_archify_erd_spec(eid, db_path)
        html = compile_archify_diagram(spec)
        dest = STATIC_DIR / f"{eid}.html"
        dest.write_text(html, encoding="utf-8")
        print(f"✅ {eid.upper()}: Guardado en {dest} ({len(html)} bytes)")

    print("🚀 Todos los diagramas Archify han sido generados exitosamente.")

if __name__ == "__main__":
    main()
