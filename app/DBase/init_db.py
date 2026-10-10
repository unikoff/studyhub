from app.DBase.engine import make_engine
from app.DBase.models import Base
from app.core.config import Settings, load_settings


def initialize_database(settings: Settings | None = None) -> None:
    if settings is None:
        settings = load_settings()

    engine = make_engine(settings.database_url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    initialize_database()
