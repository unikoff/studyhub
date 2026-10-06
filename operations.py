from errors import TaskNotFoundError
from models import create_task

def get_next_id(tasks):
    max_id = 0
    for task in tasks:
        if task["id"] > max_id:
            max_id = task["id"]
    return max_id + 1


def add_task(tasks, title, priority):
    task_id = get_next_id(tasks)
    new_task = create_task(task_id, title, priority)
    tasks.append(new_task)
    return new_task


def find_task(tasks, task_id):
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


def get_task(tasks, task_id):
    task = find_task(tasks, task_id)
    if task is None:
        raise TaskNotFoundError(f"Задача с номером {task_id} не найдена")
    return task


def mark_task_done(tasks, task_id):
    task = get_task(tasks, task_id)
    task["is_done"] = True
    return True


def build_statistics(tasks):
    total = 0
    completed = 0
    for task in tasks:
        total += 1
        if task["is_done"]:
            completed += 1
    left = total - completed
    return {"total": total, "completed": completed, "left": left}


def completion_percent(statistics):
    total = statistics["total"]
    if total == 0:
        return 0.0
    completed = statistics["completed"]
    return round(completed / total * 100, 1)


def search_tasks(tasks, query):
    normalized_query = query.strip().lower()
    matches = []
    if normalized_query == "":
        return matches
    for task in tasks:
        comparison_title = task["title"].lower()
        if normalized_query in comparison_title:
            matches.append(task)
    return matches
