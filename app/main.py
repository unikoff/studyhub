from contextlib import contextmanager
from collections.abc import Iterator

from app.cli import run
from app.core.config import load_settings
from app.services import PlannerService
from app.DBase.engine import make_engine
from app.DBase.repositories import SqlTaskRepository
from app.DBase.session import make_session_factory


def build_service(repository, write_scope) -> PlannerService:
    return PlannerService(repository=repository, write_scope=write_scope)


@contextmanager
def sql_service_context(session_factory) -> Iterator[PlannerService]:
    with session_factory() as db:
        yield build_service(SqlTaskRepository(db), db.begin)


def main():
    settings = load_settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    try:
        return run(lambda: sql_service_context(session_factory))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
