import subprocess
import sys

import pytest

from app import main as main_module
from app.core import config as config_module
from app.cli import execute_command
from app.errors import StorageError
from app.main import build_service
from app.models import Task
from app.services import PlannerService
from app.storage import JsonStorage, MemoryStorage


class ObservedStorage:
    def __init__(self, inner):
        self.inner = inner
        self.events = []

    def load(self):
        self.events.append("load")
        return self.inner.load()

    def save(self, tasks):
        self.events.append("save")
        return self.inner.save(tasks)


class FailingStorage(ObservedStorage):
    def __init__(self, inner, fail_on):
        super().__init__(inner)
        self.fail_on = fail_on

    def load(self):
        self.events.append("load")
        if self.fail_on == "load":
            raise StorageError("ошибка чтения")
        return self.inner.load()

    def save(self, tasks):
        self.events.append("save")
        if self.fail_on == "save":
            raise StorageError("ошибка записи")
        return self.inner.save(tasks)


def make_reader(answers):
    pending = list(answers)

    def read(_prompt):
        return pending.pop(0)

    return read


def run_command(storage, command, answers=()):
    messages = []
    service = PlannerService(storage)
    keep_running = execute_command(
        service,
        command,
        read=make_reader(answers),
        write=messages.append,
    )
    return service, keep_running, messages


@pytest.mark.parametrize(
    "command, answers, expected_text",
    [
        ("add", ["Новая задача", "2"], "новая задача"),
        ("done", ["1"], "выполнена"),
        ("delete", ["1"], "удалена"),
    ],
)
def test_mutating_commands_save_once_and_change_state(
    command, answers, expected_text
):
    storage = ObservedStorage(MemoryStorage([Task(1, "Python", 3)]))

    _, keep_running, messages = run_command(storage, command, answers)

    tasks = storage.inner.load()
    assert keep_running is True
    assert storage.events.count("save") == 1
    assert expected_text in " ".join(messages).casefold()
    if command == "add":
        assert len(tasks) == 2
        assert tasks[1].title == "Новая задача"
        assert tasks[1].priority == 2
    elif command == "done":
        assert len(tasks) == 1
        assert tasks[0].is_done is True
    else:
        assert tasks == []


@pytest.mark.parametrize(
    "command, answers, expected_text",
    [
        ("list", [], "python"),
        ("find", ["1"], "python"),
        ("search", ["Pyth"], "python"),
        ("stats", [], "всего: 1"),
    ],
)
def test_read_commands_show_result_without_saving(command, answers, expected_text):
    storage = ObservedStorage(MemoryStorage([Task(1, "Python", 3)]))

    _, keep_running, messages = run_command(storage, command, answers)

    assert keep_running is True
    assert expected_text in " ".join(messages).casefold()
    assert "save" not in storage.events


def test_exit_and_unknown_command_have_distinct_session_results():
    storage = ObservedStorage(MemoryStorage())

    _, keep_running, messages = run_command(storage, "exit")

    assert keep_running is False
    assert any("заверш" in message.casefold() for message in messages)
    assert "save" not in storage.events

    _, keep_running, messages = run_command(storage, "unknown")

    assert keep_running is True
    assert any("неизвест" in message.casefold() for message in messages)
    assert "save" not in storage.events


def test_invalid_input_unknown_id_and_repeated_done_do_not_save():
    storage = ObservedStorage(MemoryStorage([Task(1, "Python", 3, is_done=True)]))
    before = [task.to_dict() for task in storage.inner.load()]
    service = PlannerService(storage)
    messages = []

    execute_command(
        service,
        "find",
        read=make_reader(["not-an-int", "999"]),
        write=messages.append,
    )
    execute_command(
        service,
        "done",
        read=make_reader(["1"]),
        write=messages.append,
    )

    assert "save" not in storage.events
    assert [task.to_dict() for task in storage.inner.load()] == before
    assert any("целое число" in message.casefold() for message in messages)
    assert any("не найдена" in message.casefold() for message in messages)


@pytest.mark.parametrize(
    "fail_on, command, answers",
    [
        ("load", "list", []),
        ("save", "add", ["Новая задача", "3"]),
    ],
)
def test_storage_error_propagates_without_success_message(fail_on, command, answers):
    storage = FailingStorage(MemoryStorage(), fail_on=fail_on)
    service = PlannerService(storage)
    messages = []

    with pytest.raises(StorageError):
        execute_command(
            service,
            command,
            read=make_reader(answers),
            write=messages.append,
        )

    assert not any("добавлена" in message.casefold() for message in messages)


def test_build_service_uses_injected_storage_without_io():
    storage = ObservedStorage(MemoryStorage())

    service = build_service(storage)

    assert service.storage is storage
    assert storage.events == []


def test_default_build_selects_json_storage_without_loading_data(tmp_path, monkeypatch):
    data_path = tmp_path / "tasks.json"
    monkeypatch.delenv("JSON_PATH", raising=False)
    monkeypatch.setattr(config_module, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(config_module, "DEFAULT_JSON_PATH", data_path)

    service = main_module.build_service()

    assert isinstance(service.storage, JsonStorage)
    assert service.storage.path == data_path
    assert not data_path.exists()


def test_import_main_does_not_start_cli():
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    assert result.stdout == ""
    assert result.stderr == ""
