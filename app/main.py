from app.cli import run
from app.core.config import get_json_path
from app.errors import StorageError
from app.services import PlannerService
from app.storage import JsonStorage


def build_service(storage=None):
    if storage is None:
        storage = JsonStorage(get_json_path())
    return PlannerService(storage)


def main():
    try:
        return run(build_service())
    except StorageError as error:
        print(f"Planner остановлен: {error}")


if __name__ == "__main__":
    main()