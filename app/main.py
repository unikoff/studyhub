from pathlib import Path

from app.cli import run
from app.errors import StorageError
from app.storage import load_tasks, save_tasks


def make_on_change(path):
    def on_change(tasks):
        save_tasks(path, tasks)
    return on_change


def main():
    data_file = Path(__file__).resolve().parents[1] / "data" / "tasks.json"
    try:
        tasks = load_tasks(data_file)
        return run(tasks=tasks, on_change=make_on_change(data_file))
    except StorageError as error:
        print(f"Planner остановлен: {error}")


if __name__ == "__main__":
    main()
