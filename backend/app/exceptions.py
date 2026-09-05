from enum import Enum


class GuardrailFailureCategory(str, Enum):
    EMPTY_REQUEST = "empty_request"
    PROMPT_INJECTION = "prompt_injection"
    WRITE_INTENT = "write_intent"
    EMPTY_SQL = "empty_sql"
    SQL_COMMENTS = "sql_comments"
    MULTIPLE_STATEMENTS = "multiple_statements"
    NON_SELECT_STATEMENT = "non_select_statement"
    DISALLOWED_KEYWORD = "disallowed_keyword"
    DANGEROUS_PATTERN = "dangerous_pattern"
    WRITABLE_CTE = "writable_cte"
    NOT_SELECT = "not_select"
    SENSITIVE_COLUMN = "sensitive_column"
    UNKNOWN_TABLE = "unknown_table"
    SYSTEM_SCHEMA = "system_schema"
    MISSING_LIMIT = "missing_limit"
    SELECT_STAR = "select_star"


class AppError(Exception):
    """Base class for application-level errors."""


class WorkspaceNotFound(AppError):
    pass


class WorkspaceAlreadyExists(AppError):
    pass


class WorkspaceKeyMissing(AppError):
    pass


class SessionNotFound(AppError):
    pass


class SessionAlreadyExists(AppError):
    pass


class SessionKeyMissing(AppError):
    pass


class DatabaseConnectionAlreadyExists(AppError):
    pass


class EncryptionKeyMissing(AppError):
    pass


class DatabaseConnectionNotFound(AppError):
    pass


class DatabaseMetadataNotReady(AppError):
    pass


class UnsafeSQLQuery(AppError):
    def __init__(self, message: str, category: GuardrailFailureCategory | None = None):
        super().__init__(message)
        self.category = category


class SQLGenerationFailed(AppError):
    pass


class SQLGenerationTimedOut(AppError):
    def __init__(
        self,
        message: str = "We're unable to complete your query at the moment. Please try again.",
    ):
        super().__init__(message)
        self.attempts_so_far: list = []


class AgentRecursionLimitExceeded(AppError):
    def __init__(
        self,
        message: str = (
            "The assistant took too many steps trying to answer this question. "
            "Please try again or rephrase your question."
        ),
    ):
        super().__init__(message)
        self.attempts_so_far: list = []


class SQLExecutionFailed(AppError):
    pass


class RateLimitExceeded(AppError):
    def __init__(self, message: str, retry_after_seconds: int):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RateLimitUnavailable(AppError):
    pass
