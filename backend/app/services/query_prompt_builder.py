from typing import Any

DEFAULT_SYSTEM_PROMPT = (
    "You are a read-only SQL generation assistant. "
    "Generate exactly one SQL query that answers the user's question using only the provided "
    "database metadata. Use only schemas, tables, and columns present in the metadata. "
    "Never guess missing fields. Only produce read-only SQL. Prefer schema-qualified names "
    "when useful. Add a LIMIT when the question does not require the full dataset."
)


class QueryPromptBuilder:
    _user_prompt_template = (
        "Database metadata:\n{metadata}\n\n"
        "User question:\n{question}\n\n"
        "Return a read-only SQL query and a short summary that explains what the query does "
        "and anything important to notice about it."
    )

    def build(
        self,
        system_prompt: str | None,
        metadata_json: dict[str, Any],
        question: str,
    ) -> dict[str, str]:
        prompt_system = (system_prompt or DEFAULT_SYSTEM_PROMPT).strip()
        metadata_text = self._format_metadata(metadata_json)
        normalized_question = question.strip()
        user_prompt = self._build_user_prompt(metadata_text, normalized_question)
        return {
            "system_prompt": prompt_system,
            "metadata": metadata_text,
            "question": normalized_question,
            "user_prompt": user_prompt,
        }

    def _build_user_prompt(self, metadata_text: str, question: str) -> str:
        return self._user_prompt_template.format(
            metadata=metadata_text,
            question=question,
        )

    def _format_metadata(self, metadata_json: dict[str, Any]) -> str:
        lines = [
            f"database_type: {metadata_json.get('database_type', 'unknown')}",
            f"database_name: {metadata_json.get('database_name', 'unknown')}",
            "schemas:",
        ]

        for schema in metadata_json.get("schemas", []):
            schema_name = schema.get("name") or "default"
            lines.append(f"- schema: {schema_name}")
            for table in schema.get("tables", []):
                lines.append(f"  - table: {table['name']}")
                primary_key = ", ".join(table.get("primary_key", [])) or "none"
                lines.append(f"    primary_key: {primary_key}")
                columns = ", ".join(
                    self._format_column(column)
                    for column in table.get("columns", [])
                )
                lines.append(f"    columns: {columns or 'none'}")
                foreign_keys = table.get("foreign_keys", [])
                if foreign_keys:
                    formatted_foreign_keys = "; ".join(
                        (
                            f"{', '.join(fk.get('columns', []))} -> "
                            f"{fk.get('referred_schema') or schema_name}.{fk.get('referred_table')}"
                            f"({', '.join(fk.get('referred_columns', []))})"
                        )
                        for fk in foreign_keys
                    )
                    lines.append(f"    foreign_keys: {formatted_foreign_keys}")

        relationships = metadata_json.get("relationships", [])
        if relationships:
            lines.append("relationships:")
            for relationship in relationships:
                from_schema = relationship.get("from_schema") or "default"
                to_schema = relationship.get("to_schema") or "default"
                lines.append(
                    "- "
                    f"{from_schema}.{relationship['from_table']}({', '.join(relationship.get('from_columns', []))}) "
                    f"-> {to_schema}.{relationship['to_table']}({', '.join(relationship.get('to_columns', []))})"
                )

        return "\n".join(lines)

    def _format_column(self, column: dict[str, Any]) -> str:
        column_text = f"{column['name']} ({column.get('type', 'unknown')}"
        enum_values = column.get("enum_values", [])
        if enum_values:
            column_text += f"; allowed: {', '.join(enum_values)}"
        json_kind = column.get("json_kind")
        if json_kind:
            column_text += f"; {json_kind} document"
        array_item_type = column.get("array_item_type")
        if array_item_type:
            column_text += f"; array items: {array_item_type}"
        column_text += ")"
        return column_text
