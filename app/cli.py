from app.errors import TaskNotFoundError
from app.operations import add_task, build_statistics, completion_percent
from app.operations import get_task, mark_task_done, search_tasks
from app.validators import normalize_title


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

def handle_add(tasks, on_change=None):
    title = read_title()
    priority = read_priority()
    try:
        task = add_task(tasks, title, priority)
    except ValueError as error:
        print(error)
    else:
        if on_change is not None:
            on_change(tasks)
        print(format_task(task))


def handle_find(tasks, on_change=None):
    try:
        task = get_task(tasks, read_task_id())
    except TaskNotFoundError:
        print("Задача не найдена")
    else:
        print(format_task(task))


def handle_done(tasks, on_change=None):
    try:
        task = get_task(tasks, read_task_id())
        was_done = task["is_done"]
        mark_task_done(tasks, task["id"])
    except TaskNotFoundError:
        print("Задача не найдена")
    else:
        if not was_done and on_change is not None:
            on_change(tasks)
        print("Задача выполнена")


def handle_search(tasks, on_change=None):
    query = input("Фрагмент названия: ")
    if query.strip() == "":
        print("Введите непустой фрагмент")
        return
    matches = search_tasks(tasks, query)
    if len(matches) == 0:
        print("Совпадений не найдено")
    else:
        show_tasks(matches)


def handle_stats(tasks, on_change=None):
    statistics = build_statistics(tasks)
    percent = completion_percent(statistics)
    print(f"Всего: {statistics['total']}")
    print(f"Выполнено: {statistics['completed']}")
    print(f"Осталось: {statistics['left']}")
    print(f"Процент выполнения: {percent}%")


def handle_list(tasks, on_change=None):
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


def run(tasks=None, on_change=None):
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
        handlers[command](tasks, on_change)
    return tasks
