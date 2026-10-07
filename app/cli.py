from app.errors import TaskNotFoundError
from app.services import PlannerService
from app.validators import normalize_title


def read_title(read=input, write=print):
    while True:
        title = normalize_title(read("Название задачи: "))
        if title == "":
            write("Название не может быть пустым")
            continue
        return title


def read_int(prompt, read=input, write=print):
    while True:
        raw_value = read(prompt)
        try:
            value = int(raw_value)
        except ValueError:
            write("Введите целое число")
            continue
        return value


def read_priority(read=input, write=print):
    while True:
        priority = read_int("Приоритет от 1 до 5: ", read, write)
        if 1 <= priority <= 5:
            return priority
        write("Приоритет должен быть от 1 до 5")


def read_task_id(read=input, write=print):
    while True:
        task_id = read_int("Номер задачи: ", read, write)
        if task_id > 0:
            return task_id
        write("Номер должен быть положительным")


def format_task(task):
    return (
        f"[{task.id}] {task.title} | "
        f"приоритет: {task.priority} | {task.status_label}"
    )


def handle_add(service, read=input, write=print):
    title = read_title(read, write)
    priority = read_priority(read, write)
    try:
        task = service.add_task(title, priority)
    except ValueError as error:
        write(error)
    else:
        write(format_task(task))


def handle_find(service, read=input, write=print):
    try:
        task = service.get_task(read_task_id(read, write))
    except ValueError as error:
        write(error)
    except TaskNotFoundError:
        write("Задача не найдена")
    else:
        write(format_task(task))


def handle_done(service, read=input, write=print):
    try:
        task = service.mark_done(read_task_id(read, write))
    except ValueError as error:
        write(error)
    except TaskNotFoundError:
        write("Задача не найдена")
    else:
        write(f"Задача {task.id} выполнена")


def handle_delete(service, read=input, write=print):
    try:
        task_id = read_task_id(read, write)
        service.delete_task(task_id)
    except ValueError as error:
        write(error)
    except TaskNotFoundError:
        write("Задача не найдена")
    else:
        write("Задача удалена")


def handle_search(service, read=input, write=print):
    query = read("Фрагмент названия: ")
    if query.strip() == "":
        write("Введите непустой фрагмент")
        return
    matches = service.search_tasks(query)
    if len(matches) == 0:
        write("Совпадений не найдено")
    else:
        show_tasks(matches, write)


def handle_stats(service, read=input, write=print):
    statistics = service.get_statistics()
    total = statistics["all"]
    percent = 0.0 if total == 0 else round(statistics["done"] / total * 100, 1)
    write(f"Всего: {total}")
    write(f"Выполнено: {statistics['done']}")
    write(f"Осталось: {statistics['open']}")
    write(f"Процент выполнения: {percent}%")


def handle_list(service, read=input, write=print):
    show_tasks(service.list_tasks(), write)


def show_menu(write=print):
    write("")
    write("StudyHub Planner")
    write("add - добавить задачу")
    write("list - показать задачи")
    write("find - найти задачу по id")
    write("done - завершить задачу")
    write("delete - удалить задачу")
    write("search - искать по названию")
    write("stats - показать статистику")
    write("exit - завершить работу")


def show_tasks(tasks, write=print):
    if len(tasks) == 0:
        write("Список задач пока пуст.")
        return
    for task in tasks:
        write(format_task(task))


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "find": handle_find,
    "done": handle_done,
    "delete": handle_delete,
    "search": handle_search,
    "stats": handle_stats,
}


def execute_command(service, command, read=input, write=print):
    normalized = command.strip().lower()
    if normalized == "exit":
        write("Работу завершили")
        return False

    handler = COMMAND_HANDLERS.get(normalized)
    if handler is None:
        write("Неизвестная команда")
        return True

    handler(service, read=read, write=write)
    return True


def run(service, read=input, write=print):
    while True:
        show_menu(write)
        command = read("Команда: ")
        if not execute_command(service, command, read=read, write=write):
            break
    return service
