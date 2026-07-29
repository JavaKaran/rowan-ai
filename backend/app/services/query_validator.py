import re
from collections.abc import Iterable
from typing import Any

from app.exceptions import UnsafeSQLQuery


class ReadOnlySQLValidator:
    _disallowed_keywords = re.compile(
        r"\b("
        r"insert|update|delete|drop|alter|create|truncate|grant|revoke|"
        r"merge|replace|call|execute|copy|upsert|rename|comment|vacuum|"
        r"analyze|repair|optimize|lock|unlock|set|reset"
        r")\b",
        re.IGNORECASE,
    )
    _non_select_statements = re.compile(
        r"^\s*(show|describe|desc|explain|pragma|use)\b",
        re.IGNORECASE,
    )
    _dangerous_select_patterns = [
        re.compile(r"\bselect\s+.*\binto\b", re.IGNORECASE | re.DOTALL),
        re.compile(r"\binto\s+outfile\b", re.IGNORECASE),
        re.compile(r"\bfor\s+update\b", re.IGNORECASE),
        re.compile(r"\bload_file\s*\(", re.IGNORECASE),
    ]
    _writable_cte_pattern = re.compile(
        r"\bwith\b[\s\S]*?\b(insert|update|delete|merge)\b",
        re.IGNORECASE,
    )
    _comment_patterns = ("--", "/*", "*/", "#")
    _prompt_injection_patterns = [
        re.compile(
            r"\b(ignore|disregard|bypass|override)\b[\s\S]{0,80}\b("
            r"instruction|instructions|system prompt|prompt|guardrail|"
            r"guardrails|policy|policies|rules|restriction|restrictions|safety"
            r")\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(jailbreak|sudo mode|developer mode|hard force|force the model)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\byou are now\b[\s\S]{0,80}\b(dba|database administrator|root|superuser)\b",
            re.IGNORECASE,
        ),
    ]
    _write_intent_patterns = [
        re.compile(
            r"\b(insert|create|add|update|modify|change|edit|delete|remove|drop|truncate)\b"
            r"[\s\S]{0,40}\b(row|rows|record|records|table|tables|column|columns|"
            r"schema|schemas|database|databases|data)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(grant|revoke|alter|rename)\b[\s\S]{0,40}\b(table|schema|database|user|role|permission)\b",
            re.IGNORECASE,
        ),
    ]
    _sensitive_column_patterns = [
        re.compile(
            r"\b(password|passwd|secret|token|api[_ ]?key|access[_ ]?token|"
            r"refresh[_ ]?token|private[_ ]?key|ssn|social[_ ]?security|"
            r"credit[_ ]?card|card[_ ]?number|cvv)\b",
            re.IGNORECASE,
        )
    ]
    _aggregate_functions = re.compile(
        r"\b(count|sum|avg|min|max|exists)\s*\(",
        re.IGNORECASE,
    )
    _table_reference_pattern = re.compile(
        r"\b(?:from|join)\s+([a-zA-Z_][\w$]*(?:\.[a-zA-Z_][\w$]*)?)",
        re.IGNORECASE,
    )

    def validate_user_request(self, question: str) -> str:
        normalized = question.strip()
        if not normalized:
            raise UnsafeSQLQuery("Query request is empty.")

        if self._matches_any(self._prompt_injection_patterns, normalized):
            raise UnsafeSQLQuery(
                "This assistant only supports safe read-only SQL requests and cannot follow attempts to bypass safety rules."
            )

        if self._matches_any(self._write_intent_patterns, normalized):
            raise UnsafeSQLQuery(
                "This assistant only supports read-only database questions and cannot help modify data or schema."
            )

        return normalized

    def validate(
        self,
        sql_text: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> str:
        normalized = sql_text.strip()
        if not normalized:
            raise UnsafeSQLQuery("Generated SQL query is empty.")

        if any(pattern in normalized for pattern in self._comment_patterns):
            raise UnsafeSQLQuery("SQL comments are not allowed.")

        trimmed = normalized[:-1].strip() if normalized.endswith(";") else normalized
        if ";" in trimmed:
            raise UnsafeSQLQuery("Multiple SQL statements are not allowed.")

        if self._non_select_statements.search(trimmed):
            raise UnsafeSQLQuery("Only read-only SELECT queries are allowed.")

        if self._disallowed_keywords.search(trimmed):
            raise UnsafeSQLQuery("Only read-only SQL queries are allowed.")

        if any(pattern.search(trimmed) for pattern in self._dangerous_select_patterns):
            raise UnsafeSQLQuery("This SQL pattern is not allowed for read-only queries.")

        if self._writable_cte_pattern.search(trimmed):
            raise UnsafeSQLQuery("Writable CTE statements are not allowed.")

        if not re.match(r"^(select|with)\b", trimmed, re.IGNORECASE):
            raise UnsafeSQLQuery("Only SELECT queries are allowed.")

        if self._contains_sensitive_columns(trimmed):
            raise UnsafeSQLQuery("Queries that access sensitive columns are not allowed.")

        if metadata_json:
            self._validate_metadata_usage(trimmed, metadata_json)

        if self._requires_limit(trimmed):
            raise UnsafeSQLQuery("Queries must include a LIMIT unless they are aggregate-only reads.")

        if re.search(r"\bselect\s+\*", trimmed, re.IGNORECASE):
            raise UnsafeSQLQuery("SELECT * is not allowed. Query only the columns you need.")

        return trimmed

    def _validate_metadata_usage(
        self,
        sql_text: str,
        metadata_json: dict[str, Any],
    ) -> None:
        allowed_tables = self._build_allowed_table_names(metadata_json)
        referenced_tables = self._extract_table_references(sql_text)

        unknown_tables = sorted(table for table in referenced_tables if table not in allowed_tables)
        if unknown_tables:
            raise UnsafeSQLQuery(
                "Generated SQL references tables that are not present in the discovered database metadata."
            )

        blocked_schemas = {"information_schema", "pg_catalog", "pg_toast", "mysql", "sys", "performance_schema"}
        if any(table.split(".", 1)[0] in blocked_schemas for table in referenced_tables if "." in table):
            raise UnsafeSQLQuery("System schemas are not available for querying.")

    def _build_allowed_table_names(self, metadata_json: dict[str, Any]) -> set[str]:
        allowed_tables: set[str] = set()
        for schema in metadata_json.get("schemas", []):
            schema_name = schema.get("name")
            for table in schema.get("tables", []):
                table_name = str(table.get("name", "")).lower()
                if not table_name:
                    continue
                allowed_tables.add(table_name)
                if schema_name:
                    allowed_tables.add(f"{str(schema_name).lower()}.{table_name}")
        return allowed_tables

    def _extract_table_references(self, sql_text: str) -> set[str]:
        return {
            match.group(1).strip().strip('"').strip("`").lower()
            for match in self._table_reference_pattern.finditer(sql_text)
        }

    def _requires_limit(self, sql_text: str) -> bool:
        if re.search(r"\blimit\b", sql_text, re.IGNORECASE):
            return False
        if self._aggregate_functions.search(sql_text):
            return False
        if re.search(r"\bdistinct\b", sql_text, re.IGNORECASE):
            return False
        return True

    def _contains_sensitive_columns(self, sql_text: str) -> bool:
        select_match = re.search(
            r"\bselect\b(?P<select>[\s\S]*?)\bfrom\b",
            sql_text,
            re.IGNORECASE,
        )
        if not select_match:
            return False

        select_clause = select_match.group("select")
        return self._matches_any(self._sensitive_column_patterns, select_clause)

    def _matches_any(self, patterns: Iterable[re.Pattern[str]], value: str) -> bool:
        return any(pattern.search(value) for pattern in patterns)
