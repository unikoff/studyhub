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
    if not isinstance(priority, int):
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


class TaskNotFoundError(Exception):
    pass


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


def read_title():
    while True:
        title = normalize_title(input("Название задачи: "))
        if title == "":
            print("Название не может быть пустым")
            continue
        return title


def read_int(prompt):
    while True:
        raw_value = input(prompt)
        try:
            value = int(raw_value)
        except ValueError:
            print("Введите целое число")
            continue
        return value


def read_priority():
    while True:
        priority = read_int("Приоритет от 1 до 5: ")
        if 1 <= priority <= 5:
            return priority
        print("Приоритет должен быть от 1 до 5")


def read_task_id():
    while True:
        task_id = read_int("Номер задачи: ")
        if task_id > 0:
            return task_id
        print("Номер должен быть положительным")


def calculate_study_minutes(durations):
    total = 0
    for duration in durations:
        total = total + duration
    return total


def format_task(task):
    if task["is_done"]:
        state = "выполнена"
    else:
        state = "не завершена"
    return f"[{task['id']}] {task['title']} | приоритет: {task['priority']} | {state}"


def make_trace(operation, prefix):
    def wrapper(*args, **kwargs):
        print(f"{prefix} START")
        result = operation(*args, **kwargs)
        print(f"{prefix} DONE {result}")
        return result
    return wrapper


traced_format_task = make_trace(format_task, "TRACE")

def handle_add(tasks):
    title = read_title()
    priority = read_priority()
    try:
        task = add_task(tasks, title, priority)
    except ValueError as error:
        print(error)
    else:
        print(format_task(task))


def handle_find(tasks):
    try:
        task = get_task(tasks, read_task_id())
    except TaskNotFoundError:
        print("Задача не найдена")
    else:
        print(format_task(task))


def handle_done(tasks):
    try:
        mark_task_done(tasks, read_task_id())
    except TaskNotFoundError:
        print("Задача не найдена")
    else:
        print("Задача выполнена")


def handle_search(tasks):
    query = input("Фрагмент названия: ")
    if query.strip() == "":
        print("Введите непустой фрагмент")
        return
    matches = search_tasks(tasks, query)
    if len(matches) == 0:
        print("Совпадений не найдено")
    else:
        show_tasks(matches)


def handle_stats(tasks):
    statistics = build_statistics(tasks)
    percent = completion_percent(statistics)
    print(f"Всего: {statistics['total']}")
    print(f"Выполнено: {statistics['completed']}")
    print(f"Осталось: {statistics['left']}")
    print(f"Процент выполнения: {percent}%")


def handle_list(tasks):
    show_tasks(tasks)


def show_menu():
    print()
    print("StudyHub Planner")
    print("add - добавить задачу")
    print("list - показать задачи")
    print("find - найти задачу по id")
    print("done - завершить задачу")
    print("search - искать по названию")
    print("stats - показать статистику")
    print("exit - завершить работу")


def show_tasks(tasks):
    if len(tasks) == 0:
        print("Список задач пока пуст.")
        return
    for task in tasks:
        print(format_task(task))


def run(tasks=None):
    if tasks is None:
        tasks = []

    handlers = {
        "add": handle_add,
        "list": handle_list,
        "find": handle_find,
        "done": handle_done,
        "search": handle_search,
        "stats": handle_stats,
    }

    while True:
        show_menu()
        command = input("Команда: ").strip().lower()
        if command == "exit":
            print("Работу завершили")
            break
        if command not in handlers:
            print("Неизвестная команда")
            continue
        handlers[command](tasks)
    return tasks


run()
