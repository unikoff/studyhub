from app.cli import run
from app.core.config import load_settings
from app.errors import StorageError
from app.services import PlannerService
from app.storage import JsonStorage


def build_service(storage=None, settings=None):
    if storage is not None:
        return PlannerService(storage)

    if settings is None:
        settings = load_settings()

    return PlannerService(JsonStorage(settings.json_path))


def main():
    settings = load_settings()
    try:
        return run(build_service(settings=settings))
    except StorageError as error:
        print(f"Planner остановлен: {error}")


if __name__ == "__main__":
    main()
