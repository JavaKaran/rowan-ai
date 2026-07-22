from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models import DatabaseMetadata


class DatabaseMetadataRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create_pending(self, database_connection_id: int) -> DatabaseMetadata:
        metadata = DatabaseMetadata(
            database_connection_id=database_connection_id,
            status="pending",
            progress_current=0,
            progress_total=0,
        )
        self.db.add(metadata)
        self.db.commit()
        self.db.refresh(metadata)

        return metadata

    def get_by_connection_id(
        self,
        database_connection_id: int,
    ) -> DatabaseMetadata | None:
        return (
            self.db.query(DatabaseMetadata)
            .filter(DatabaseMetadata.database_connection_id == database_connection_id)
            .first()
        )

    def update_status(
        self,
        metadata: DatabaseMetadata,
        status: str,
        progress_current: int | None = None,
        progress_total: int | None = None,
        metadata_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> DatabaseMetadata:
        metadata.status = status

        if progress_current is not None:
            metadata.progress_current = progress_current

        if progress_total is not None:
            metadata.progress_total = progress_total

        if metadata_json is not None:
            metadata.metadata_json = metadata_json

        metadata.error_message = error_message

        self.db.commit()
        self.db.refresh(metadata)

        return metadata
