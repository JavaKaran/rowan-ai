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
    pass


class SQLGenerationFailed(AppError):
    pass


class SQLExecutionFailed(AppError):
    pass
