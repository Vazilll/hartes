"""
services.data_fabric.click_to_ast
=================================
Click-to-AST Auto-CRUD and Schema Mutation Generator.
Translates UI interaction events into verified AST code patches and database migration statements.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class FieldDef:
    """Specification of a new or mutated schema field."""
    name: str
    type_name: str = "str"
    required: bool = False
    default: Optional[Any] = None
    description: str = ""


class ClickToAST:
    """Generates Python FastAPI router code and SQLite DDL from UI field definitions."""

    @classmethod
    def generate_crud_patch(cls, entity_name: str, field_def: FieldDef) -> str:
        """Generates dynamic endpoint code for setting a specific field on an entity."""
        clean_entity = entity_name.strip().capitalize()
        py_type = field_def.type_name
        return f"""
# Auto-generated CRUD endpoint for {clean_entity}.{field_def.name}
@app.post("/api/{entity_name.lower()}/{{item_id}}/{field_def.name}")
async def set_{entity_name.lower()}_{field_def.name}(item_id: int, value: {py_type}):
    with get_db_connection() as conn:
        conn.execute("UPDATE {entity_name.lower()} SET {field_def.name} = ? WHERE id = ?", [value, item_id])
        conn.commit()
    return {{"success": True, "id": item_id, "{field_def.name}": value}}
""".strip()

    @classmethod
    def generate_sql_migration(cls, table_name: str, field_def: FieldDef) -> str:
        """Generates SQLite ALTER TABLE DDL statement."""
        sql_type = "TEXT"
        t = field_def.type_name.lower()
        if t in ("int", "integer"):
            sql_type = "INTEGER"
        elif t in ("float", "real"):
            sql_type = "REAL"
        elif t in ("bool", "boolean"):
            sql_type = "INTEGER"

        default_clause = ""
        if field_def.default is not None:
            default_clause = f" DEFAULT '{field_def.default}'" if sql_type == "TEXT" else f" DEFAULT {field_def.default}"

        return f"ALTER TABLE {table_name} ADD COLUMN {field_def.name} {sql_type}{default_clause};"

    @classmethod
    def validate_patch_syntax(cls, code_str: str) -> bool:
        """Validates generated AST syntax."""
        try:
            ast.parse(code_str)
            return True
        except SyntaxError:
            return False
