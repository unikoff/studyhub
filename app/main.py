from pathlib import Path

from app.cli import run
from app.errors import StorageError
from app.services import PlannerService
from app.storage import JsonStorage


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "tasks.json"


def build_service(storage=None):
    if storage is None:
        storage = JsonStorage(DATA_PATH)
    return PlannerService(storage)


def main():
    try:
        return run(build_service())
    except StorageError as error:
        print(f"Planner остановлен: {error}")


if __name__ == "__main__":
    main()