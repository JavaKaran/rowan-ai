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
