from typing import Protocol

from fastapi import BackgroundTasks

from app.services.database_metadata import parse_database_metadata_job


class MetadataJobDispatcher(Protocol):
    def enqueue_parse_metadata(self, database_connection_id: int) -> None:
        ...


class FastAPIMetadataJobDispatcher:
    def __init__(self, background_tasks: BackgroundTasks):
        self.background_tasks = background_tasks

    def enqueue_parse_metadata(self, database_connection_id: int) -> None:
        self.background_tasks.add_task(parse_database_metadata_job, database_connection_id)


def get_metadata_job_dispatcher(
    background_tasks: BackgroundTasks,
) -> MetadataJobDispatcher:
    return FastAPIMetadataJobDispatcher(background_tasks)
