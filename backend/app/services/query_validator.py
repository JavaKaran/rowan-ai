import re

from app.exceptions import UnsafeSQLQuery


class ReadOnlySQLValidator:
    _disallowed_keywords = re.compile(
        r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|merge|replace|call|execute|copy)\b",
        re.IGNORECASE,
    )
    _comment_patterns = ("--", "/*", "*/", "#")

    def validate(self, sql_text: str) -> str:
        normalized = sql_text.strip()
        if not normalized:
            raise UnsafeSQLQuery("Generated SQL query is empty.")

        if any(pattern in normalized for pattern in self._comment_patterns):
            raise UnsafeSQLQuery("SQL comments are not allowed.")

        trimmed = normalized[:-1].strip() if normalized.endswith(";") else normalized
        if ";" in trimmed:
            raise UnsafeSQLQuery("Multiple SQL statements are not allowed.")

        if self._disallowed_keywords.search(trimmed):
            raise UnsafeSQLQuery("Only read-only SQL queries are allowed.")

        if not re.match(r"^(select|with)\b", trimmed, re.IGNORECASE):
            raise UnsafeSQLQuery("Only SELECT queries are allowed.")

        return trimmed
