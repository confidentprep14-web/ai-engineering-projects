"""Schema introspection for the SQL agent.

introspect_db reads the live SQLite schema (sqlite_master + PRAGMA
table_info / foreign_key_list) at startup so the LLM prompt always
reflects the actual database, not a hand-maintained description that can
drift out of sync.
"""

import os
import sqlite3


def introspect_db(db_path: str) -> dict:
    """Introspect a SQLite database and return its schema as a dict.

    Output shape:
        {"tables": [{"name": str, "columns": [{"name", "type", "nullable", "pk"}],
                      "foreign_keys": [...]}]}

    Raises FileNotFoundError if db_path does not exist.
    """
    if not os.path.isfile(db_path):
        raise FileNotFoundError(
            f"Database file not found: {db_path}. Run: python scripts/init_db.py"
        )

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        tables = []
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]

        for table_name in table_names:
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = [
                {
                    "name": row[1],
                    "type": row[2],
                    "nullable": not row[3],
                    "pk": bool(row[5]),
                }
                for row in cursor.fetchall()
            ]

            cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
            foreign_keys = [
                {"column": row[3], "references_table": row[2], "references_column": row[4]}
                for row in cursor.fetchall()
            ]

            tables.append({"name": table_name, "columns": columns, "foreign_keys": foreign_keys})

        return {"tables": tables}
    finally:
        conn.close()


def format_schema_for_prompt(schema: dict) -> str:
    """Format a schema dict (from introspect_db) into a string for the LLM prompt."""
    lines = ["Tables:", ""]

    for table in schema["tables"]:
        fk_by_column = {fk["column"]: fk for fk in table["foreign_keys"]}

        col_parts = []
        for col in table["columns"]:
            part = f"{col['name']} {col['type']}"
            if col["pk"]:
                part += " PK"
            fk = fk_by_column.get(col["name"])
            if fk:
                part += f" FK→{fk['references_table']}.{fk['references_column']}"
            col_parts.append(part)

        lines.append(f"{table['name']} ({', '.join(col_parts)})")

    return "\n".join(lines)
