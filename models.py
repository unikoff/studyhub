from validators import validate_priority, validate_task_id, validate_title

def create_task(task_id, title, priority=2):
    task_id = validate_task_id(task_id)
    title = validate_title(title)
    priority = validate_priority(priority)
    return {
        "id": task_id,
        "title": title,
        "priority": priority,
        "is_done": False,
    }
