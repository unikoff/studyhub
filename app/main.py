from pathlib import Path

from app.cli import run
from app.errors import StorageError
from app.storage import JsonStorage


def main():
    data_file = Path(__file__).resolve().parents[1] / "data" / "tasks.json"
    storage = JsonStorage(data_file)
    try:
        return run(storage)
    except StorageError as error:
        print(f"Planner остановлен: {error}")


if __name__ == "__main__":
    main()
