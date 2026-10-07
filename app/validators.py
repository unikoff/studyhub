TASK_FIELDS = {"id", "title", "priority", "is_done"}


def validate_task_record(record, location="record"):
    if not isinstance(record, dict):
        raise ValueError(f"{location}: ожидается словарь")
    if set(record) != TASK_FIELDS:
        raise ValueError(f"{location}: неверный набор полей")
    return record


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


def validate_tags(tags):
    if not isinstance(tags, list):
        raise ValueError("Метки должны быть списком")

    normalized = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError("Каждая метка должна быть строкой")
        tag = tag.strip()
        if not tag:
            raise ValueError("Метка не может быть пустой")
        normalized.append(tag)
    return normalized
