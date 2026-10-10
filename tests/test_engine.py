import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from app.DBase.engine import make_engine


def test_engine_opens_explicit_sqlite_file_and_connection_closes(tmp_path):
    database_path = tmp_path / "probe.sqlite3"
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)

    engine = make_engine(database_url)
    try:
        assert not database_path.exists()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
            assert connection.closed is False
            assert connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            ).all() == []

        assert connection.closed is True
        assert database_path.exists()
    finally:
        engine.dispose()


def test_connection_closes_when_operation_raises(tmp_path):
    database_path = tmp_path / "failure.sqlite3"
    database_url = URL.create(
        "sqlite", database=database_path.as_posix()
    ).render_as_string(hide_password=False)
    engine = make_engine(database_url)

    try:
        with pytest.raises(RuntimeError, match="stop"):
            with engine.connect() as connection:
                raise RuntimeError("stop")

        assert connection.closed is True
    finally:
        engine.dispose()
