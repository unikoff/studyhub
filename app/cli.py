from app.errors import TaskNotFoundError
from app.operations import add_task, completion_percent, mark_task_done
from app.services import PlannerService
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
    return (
        f"[{task.id}] {task.title} | "
        f"приоритет: {task.priority} | {task.status_label}"
    )


def make_trace(operation, prefix):
    def wrapper(*args, **kwargs):
        print(f"{prefix} START")
        result = operation(*args, **kwargs)
        print(f"{prefix} DONE {result}")
        return result
    return wrapper


traced_format_task = make_trace(format_task, "TRACE")

def handle_add(storage):
    title = read_title()
    priority = read_priority()
    try:
        task = add_task(storage, title, priority)
    except ValueError as error:
        print(error)
    else:
        print(format_task(task))


def handle_find(service):
    try:
        task = service.get_task(read_task_id())
    except ValueError as error:
        print(error)
    except TaskNotFoundError:
        print("Задача не найдена")
    else:
        print(format_task(task))


def handle_done(storage):
    try:
        mark_task_done(storage, read_task_id())
    except TaskNotFoundError:
        print("Задача не найдена")
    else:
        print("Задача выполнена")


def handle_search(service):
    query = input("Фрагмент названия: ")
    if query.strip() == "":
        print("Введите непустой фрагмент")
        return
    matches = service.search_tasks(query)
    if len(matches) == 0:
        print("Совпадений не найдено")
    else:
        show_tasks(matches)


def handle_stats(service):
    statistics = service.get_statistics()
    percent = completion_percent(statistics)
    print(f"Всего: {statistics['all']}")
    print(f"Выполнено: {statistics['done']}")
    print(f"Осталось: {statistics['open']}")
    print(f"Процент выполнения: {percent}%")


def handle_list(service):
    show_tasks(service.list_tasks())


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


def run(storage):
    service = PlannerService(storage)
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
        if command in {"add", "done"}:
            handlers[command](storage)
        else:
            handlers[command](service)
    return storage
