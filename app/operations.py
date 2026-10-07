from app.errors import TaskNotFoundError
from app.models import Task


def get_next_id(tasks):
    max_id = 0
    for task in tasks:
        if task.id > max_id:
            max_id = task.id
    return max_id + 1


def _find_task(tasks, task_id):
    for task in tasks:
        if task.id == task_id:
            return task
    return None


def add_task(storage, title, priority):
    tasks = storage.load()
    task = Task(get_next_id(tasks), title, priority)
    tasks.append(task)
    storage.save(tasks)
    return task


def mark_task_done(storage, task_id):
    tasks = storage.load()
    task = _find_task(tasks, task_id)
    if task is None:
        raise TaskNotFoundError(f"Задача с номером {task_id} не найдена")
    if not task.is_done:
        task.mark_done()
        storage.save(tasks)
    return True


def completion_percent(statistics):
    total = statistics["all"]
    if total == 0:
        return 0.0
    done = statistics["done"]
    return round(done / total * 100, 1)
