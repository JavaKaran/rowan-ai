class AppError(Exception):
    """Base class for application-level errors."""


class WorkspaceNotFound(AppError):
    pass


class WorkspaceAlreadyExists(AppError):
    pass
