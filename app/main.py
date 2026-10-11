from contextlib import contextmanager
from collections.abc import Iterator

from app.cli import run
from app.core.config import load_settings
from app.errors import StorageError
from app.services import PlannerService
from app.storage import JsonStorage
from app.DBase.repositories import SqlTaskRepository


def build_service(
    storage=None, settings=None, repository=None, write_scope=None
):
    if repository is not None:
        if storage is not None:
            raise ValueError("Pass either storage or repository, not both")
        return PlannerService(
            repository=repository,
            write_scope=write_scope,
        )
    if write_scope is not None:
        raise ValueError("write_scope requires a repository")

    if storage is not None:
        return PlannerService(storage)

    if settings is None:
        settings = load_settings()

    return PlannerService(JsonStorage(settings.json_path))


@contextmanager
def sql_service_context(session_factory) -> Iterator[PlannerService]:
    with session_factory() as db:
        yield build_service(
            repository=SqlTaskRepository(db),
            write_scope=db.begin,
        )


def main():
    settings = load_settings()
    try:
        return run(build_service(settings=settings))
    except StorageError as error:
        print(f"Planner остановлен: {error}")


if __name__ == "__main__":
    main()
