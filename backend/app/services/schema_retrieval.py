import re
from typing import Any


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class SchemaRetrievalService:
    def __init__(self, metadata_json: dict[str, Any]):
        self.metadata_json = metadata_json
        self._tables = self._flatten_tables(metadata_json)

    def find_relevant_tables(self, question: str) -> list[dict[str, Any]]:
        question_tokens = _tokenize(question)

        scored = []
        for table in self._tables:
            score = self._score_table(table, question_tokens)
            scored.append((score, table))

        if all(score == 0 for score, _ in scored):
            return [self._table_summary(table) for _, table in scored]

        scored.sort(key=lambda item: item[0], reverse=True)
        return [self._table_summary(table) for score, table in scored if score > 0]

    def get_columns(self, table_names: list[str]) -> list[dict[str, Any]]:
        results = []
        for table_name in table_names:
            table = self._find_table(table_name)
            if table is None:
                continue
            results.append(
                {
                    "schema": table["schema"],
                    "table": table["name"],
                    "primary_key": table.get("primary_key", []),
                    "columns": table.get("columns", []),
                }
            )
        return results

    def get_relationships(self, table_names: list[str]) -> list[dict[str, Any]]:
        requested = {self._short_name(name) for name in table_names}
        relationships = self.metadata_json.get("relationships", [])
        return [
            relationship
            for relationship in relationships
            if relationship["from_table"] in requested
            or relationship["to_table"] in requested
        ]

    def _score_table(self, table: dict[str, Any], question_tokens: set[str]) -> int:
        table_tokens = _tokenize(table["name"])
        column_tokens: set[str] = set()
        for column in table.get("columns", []):
            column_tokens |= _tokenize(column["name"])

        score = len(question_tokens & table_tokens) * 2
        score += len(question_tokens & column_tokens)
        return score

    def _table_summary(self, table: dict[str, Any]) -> dict[str, Any]:
        return {"schema": table["schema"], "table": table["name"]}

    def _find_table(self, table_name: str) -> dict[str, Any] | None:
        schema_name, name = self._split_table_name(table_name)
        for table in self._tables:
            if table["name"] != name:
                continue
            if schema_name is not None and table["schema"] != schema_name:
                continue
            return table
        return None

    def _short_name(self, table_name: str) -> str:
        _, name = self._split_table_name(table_name)
        return name

    def _split_table_name(self, table_name: str) -> tuple[str | None, str]:
        if "." in table_name:
            schema_name, name = table_name.split(".", 1)
            return schema_name, name
        return None, table_name

    def _flatten_tables(self, metadata_json: dict[str, Any]) -> list[dict[str, Any]]:
        tables = []
        for schema in metadata_json.get("schemas", []):
            for table in schema.get("tables", []):
                tables.append({**table, "schema": schema.get("name")})
        return tables
