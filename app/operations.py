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


def find_task(storage, task_id):
    return _find_task(storage.load(), task_id)


def get_task(storage, task_id):
    task = find_task(storage, task_id)
    if task is None:
        raise TaskNotFoundError(f"Задача с номером {task_id} не найдена")
    return task


def list_tasks(storage):
    return storage.load()


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


def build_statistics(storage):
    tasks = storage.load()
    total = 0
    completed = 0
    for task in tasks:
        total += 1
        if task.is_done:
            completed += 1
    left = total - completed
    return {"total": total, "completed": completed, "left": left}


def completion_percent(statistics):
    total = statistics["total"]
    if total == 0:
        return 0.0
    completed = statistics["completed"]
    return round(completed / total * 100, 1)


def search_tasks(storage, query):
    normalized_query = query.strip().lower()
    if normalized_query == "":
        return []
    tasks = storage.load()
    matches = []
    for task in tasks:
        if normalized_query in task.title.lower():
            matches.append(task)
    return matches
