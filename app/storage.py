import json
from pathlib import Path


def encode_tasks(tasks):
    return json.dumps(tasks, ensure_ascii=False, indent=2)


def decode_tasks(text):
    return json.loads(text)


def load_tasks(path: Path):
    try:
        with path.open("r", encoding="utf-8") as file:
            text = file.read()
    except FileNotFoundError:
        return []
    return decode_tasks(text)


def save_tasks(path: Path, tasks):
    text = encode_tasks(tasks)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        file.write(text)
