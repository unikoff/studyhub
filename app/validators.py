def normalize_title(title):
    return title.strip()


def validate_title(title):
    if not isinstance(title, str):
        raise ValueError("Название должно быть строкой")
    normalized = normalize_title(title)
    if normalized == "":
        raise ValueError("Название не может быть пустым")
    return normalized


def validate_priority(priority):
    if type(priority) is not int:
        raise ValueError("Приоритет должен быть целым числом")
    if not 1 <= priority <= 5:
        raise ValueError("Приоритет должен быть от 1 до 5")
    return priority


def validate_task_id(task_id):
    if not isinstance(task_id, int):
        raise ValueError("Номер задачи должен быть целым числом")
    if task_id <= 0:
        raise ValueError("Номер задачи должен быть положительным")
    return task_id
