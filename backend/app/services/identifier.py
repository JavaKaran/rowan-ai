from ulid import ULID


class IdentifierService:
    @staticmethod
    def generate(prefix: str) -> str:
        return f"{prefix}_{ULID()}"

    @staticmethod
    def workspace() -> str:
        return IdentifierService.generate("ws")

    @staticmethod
    def session() -> str:
        return IdentifierService.generate("sess")

    @staticmethod
    def query() -> str:
        return IdentifierService.generate("qry")
