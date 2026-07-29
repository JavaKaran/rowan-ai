from typing import Any

DEFAULT_SYSTEM_PROMPT = (
    "You are a read-only SQL generation assistant. "
    "Generate exactly one SQL query that answers the user's question using only the provided "
    "database metadata. Use only schemas, tables, and columns present in the metadata. "
    "Never guess missing fields. Only produce read-only SQL. Prefer schema-qualified names "
    "when useful. Add a LIMIT when the question does not require the full dataset."
)


class QueryPromptBuilder:
    _prompt_template = (
        "Database metadata:\n{metadata}\n\n"
        "{session_context}"
        "Current user question:\n{question}\n\n"
        "Return a read-only SQL query and a short summary that explains what the query does "
        "and anything important to notice about it."
    )

    def build(
        self,
        metadata_json: dict[str, Any],
        question: str,
        last_user_question: str | None = None,
        last_sql_query: str | None = None,
    ) -> dict[str, str]:
        metadata_text = self._format_metadata(metadata_json)
        normalized_question = question.strip()
        session_context = self._format_session_context(last_user_question, last_sql_query)
        prompt_text = self._build_prompt_text(
            metadata_text,
            session_context,
            normalized_question,
        )
        return {
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "metadata": metadata_text,
            "question": normalized_question,
            "prompt_text": prompt_text,
        }

    def _build_prompt_text(
        self,
        metadata_text: str,
        session_context: str,
        question: str,
    ) -> str:
        return self._prompt_template.format(
            metadata=metadata_text,
            session_context=session_context,
            question=question,
        )

    def _format_session_context(
        self,
        last_user_question: str | None,
        last_sql_query: str | None,
    ) -> str:
        context_lines: list[str] = []
        if last_user_question:
            context_lines.append(f"last_user_question: {last_user_question}")
        if last_sql_query:
            context_lines.append(f"last_sql_query: {last_sql_query}")

        if not context_lines:
            return ""

        return "Session context:\n" + "\n".join(context_lines) + "\n\n"

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
