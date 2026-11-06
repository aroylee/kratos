"""Script to build unified relational SQLite database: data/el_salvador.db

Loads Censo 2024, BCR Macroeconomía (Remesas & IPC), and MARN Clima
with normalized relational foreign key hierarchy.
"""

import csv
import re
import sqlite3
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SALVADOR_DIR = DATA_DIR / "salvador"
DB_PATH = DATA_DIR / "el_salvador.db"


def normalize_str(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().upper()


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. DDL Statements
    cursor.executescript("""
    CREATE TABLE departamentos (
        departamento_id TEXT PRIMARY KEY,
        departamento_nombre TEXT NOT NULL,
        zona_geografica TEXT NOT NULL
    );

    CREATE TABLE municipios (
        municipio_id TEXT PRIMARY KEY,
        departamento_id TEXT NOT NULL,
        municipio_nombre TEXT NOT NULL,
        FOREIGN KEY (departamento_id) REFERENCES departamentos(departamento_id)
    );

    CREATE TABLE distritos (
        distrito_id TEXT PRIMARY KEY,
        municipio_id TEXT NOT NULL,
        departamento_id TEXT NOT NULL,
        distrito_nombre TEXT NOT NULL,
        FOREIGN KEY (municipio_id) REFERENCES municipios(municipio_id),
        FOREIGN KEY (departamento_id) REFERENCES departamentos(departamento_id)
    );

    CREATE TABLE censo_poblacion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        censo_anio INTEGER NOT NULL,
        departamento_id TEXT,
        municipio_id TEXT,
        distrito_id TEXT,
        nivel_geografico TEXT NOT NULL,
        rango_edad TEXT NOT NULL,
        genero TEXT NOT NULL,
        poblacion INTEGER NOT NULL,
        FOREIGN KEY (departamento_id) REFERENCES departamentos(departamento_id),
        FOREIGN KEY (municipio_id) REFERENCES municipios(municipio_id),
        FOREIGN KEY (distrito_id) REFERENCES distritos(distrito_id)
    );

    CREATE TABLE remesas_mensuales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        periodo TEXT NOT NULL,
        monto_millones_usd REAL NOT NULL,
        fuente TEXT,
        frecuencia TEXT,
        es_preliminar INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE ipc_mensual (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        periodo TEXT NOT NULL,
        indice REAL NOT NULL,
        serie TEXT,
        base_indice TEXT,
        fuente TEXT
    );

    CREATE TABLE clima_indicadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anio INTEGER NOT NULL,
        indicador TEXT NOT NULL,
        valor REAL NOT NULL,
        unidad TEXT NOT NULL,
        estacion TEXT,
        departamento_id TEXT,
        periodo_inicio TEXT,
        periodo_fin TEXT,
        anotacion TEXT,
        FOREIGN KEY (departamento_id) REFERENCES departamentos(departamento_id)
    );
    """)

    # 2. Extract and insert Departamentos, Municipios, Distritos from Censo
    dept_map = {}
    muni_map = {}
    dist_map = {}

    def get_zone(dept_id: str) -> str:
        if dept_id in ["01", "02", "03"]:
            return "Zona Occidental"
        if dept_id in ["04", "05", "06", "07"]:
            return "Zona Central"
        if dept_id in ["08", "09", "10"]:
            return "Zona Paracentral"
        if dept_id in ["11", "12", "13", "14"]:
            return "Zona Oriental"
        return "Nacional"

    censo_file = SALVADOR_DIR / "censo_2024_poblacion_nombres.csv"
    with open(censo_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            d_id = (r.get("departamento_id") or "").strip()
            d_nm = (r.get("departamento_nombre") or "").strip()
            m_id = (r.get("municipio_id") or "").strip()
            m_nm = (r.get("municipio_nombre") or "").strip()
            di_id = (r.get("distrito_id") or "").strip()
            di_nm = (r.get("distrito_nombre") or "").strip()

            if d_id and d_id not in dept_map:
                dept_map[d_id] = (d_id, d_nm, get_zone(d_id))
            if m_id and m_id not in muni_map:
                muni_map[m_id] = (m_id, d_id, m_nm)
            if di_id and di_id not in dist_map:
                dist_map[di_id] = (di_id, m_id, d_id, di_nm)

    cursor.executemany(
        "INSERT INTO departamentos (departamento_id, departamento_nombre, zona_geografica) VALUES (?, ?, ?);",
        sorted(dept_map.values())
    )
    cursor.executemany(
        "INSERT INTO municipios (municipio_id, departamento_id, municipio_nombre) VALUES (?, ?, ?);",
        sorted(muni_map.values())
    )
    cursor.executemany(
        "INSERT INTO distritos (distrito_id, municipio_id, departamento_id, distrito_nombre) VALUES (?, ?, ?, ?);",
        sorted(dist_map.values())
    )

    # 3. Insert Censo Población
    with open(censo_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows_to_insert = []
        for r in reader:
            # First key may have BOM
            first_key = [k for k in r.keys() if "censo" in k.lower()][0]
            c_anio = int(r[first_key])
            d_id = r["departamento_id"].strip()
            m_id = r["municipio_id"].strip() or None
            di_id = r["distrito_id"].strip() or None
            nivel = r["nivel_geografico"].strip()
            r_edad = r["rango_edad"].strip()
            gen = r["genero"].strip()
            pob = int(r["poblacion"].strip())

            # Validate FKs if not national
            if m_id and m_id not in muni_map:
                m_id = None
            if di_id and di_id not in dist_map:
                di_id = None

            rows_to_insert.append((c_anio, d_id, m_id, di_id, nivel, r_edad, gen, pob))

        cursor.executemany(
            """INSERT INTO censo_poblacion
               (censo_anio, departamento_id, municipio_id, distrito_id, nivel_geografico, rango_edad, genero, poblacion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
            rows_to_insert
        )

    # 4. Insert Remesas Mensuales
    remesas_file = SALVADOR_DIR / "bcr_remesas_mensuales.csv"
    with open(remesas_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        remesas_rows = []
        for r in reader:
            per = r["periodo"].strip()
            val = float(r["valor"].strip())
            fuente = r.get("fuente", "BCR El Salvador").strip()
            frec = r.get("frecuencia", "mensual").strip()
            prelim = 1 if r.get("preliminar", "").lower() == "true" else 0
            remesas_rows.append((per, val, fuente, frec, prelim))

        cursor.executemany(
            """INSERT INTO remesas_mensuales (periodo, monto_millones_usd, fuente, frecuencia, es_preliminar)
               VALUES (?, ?, ?, ?, ?);""",
            remesas_rows
        )

    # 5. Insert IPC Mensual
    ipc_file = SALVADOR_DIR / "bcr_ipc_indice.csv"
    with open(ipc_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ipc_rows = []
        for r in reader:
            per = r["periodo"].strip()
            val = float(r["valor"].strip())
            serie = r.get("serie", "").strip()
            base = r.get("base_indice", "").strip()
            fuente = r.get("fuente", "BCR El Salvador").strip()
            ipc_rows.append((per, val, serie, base, fuente))

        cursor.executemany(
            """INSERT INTO ipc_mensual (periodo, indice, serie, base_indice, fuente)
               VALUES (?, ?, ?, ?, ?);""",
            ipc_rows
        )

    # 6. Insert Clima Indicadores with FK to Departamentos
    # Create normalized lookup for department IDs
    dept_norm_to_id = {normalize_str(v[1]): v[0] for v in dept_map.values() if v[0] != "00"}

    clima_file = SALVADOR_DIR / "marn_clima_indicadores_2025.csv"
    with open(clima_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        clima_rows = []
        for r in reader:
            anio = int(r["anio"].strip())
            indicador = r["indicador"].strip()
            val = float(r["valor"].strip())
            unidad = r["unidad"].strip()
            estacion = r.get("estacion", "").strip()
            raw_dept = r.get("departamento", "").strip()
            dept_id = dept_norm_to_id.get(normalize_str(raw_dept))
            p_ini = r.get("periodo_inicio", "").strip()
            p_fin = r.get("periodo_fin", "").strip()
            anot = r.get("anotacion", "").strip()
            clima_rows.append((anio, indicador, val, unidad, estacion, dept_id, p_ini, p_fin, anot))

        cursor.executemany(
            """INSERT INTO clima_indicadores
               (anio, indicador, valor, unidad, estacion, departamento_id, periodo_inicio, periodo_fin, anotacion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            clima_rows
        )

    # Create Performance Indexes
    cursor.executescript("""
    CREATE INDEX idx_censo_nivel ON censo_poblacion (nivel_geografico);
    CREATE INDEX idx_censo_dept ON censo_poblacion (departamento_id);
    CREATE INDEX idx_censo_muni ON censo_poblacion (municipio_id);
    CREATE INDEX idx_censo_dist ON censo_poblacion (distrito_id);
    CREATE INDEX idx_remesas_per ON remesas_mensuales (periodo);
    CREATE INDEX idx_ipc_per ON ipc_mensual (periodo);
    """)

    conn.commit()
    conn.close()
    print(f"✅ Base de datos relacional creada con éxito en: {DB_PATH}")


if __name__ == "__main__":
    main()
