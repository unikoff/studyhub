def create_task(task_id, title, priority):
    return {
        "id": task_id,
        "title": title,
        "priority": priority,
        "is_done": False,
    }


def normalize_title(title):
    return title.strip()


def read_title():
    while True:
        title = normalize_title(input("Название задачи: "))
        if title == "":
            print("Название не может быть пустым")
            continue
        return title


def read_priority():
    while True:
        raw_value = input("Приоритет от 1 до 5: ")
        try:
            priority = int(raw_value)
        except ValueError:
            print("Введите целое число")
            continue
        if 1 <= priority <= 5:
            return priority
        print("Приоритет должен быть от 1 до 5")


def read_task_id():
    while True:
        raw_value = input("Номер задачи: ")
        try:
            task_id = int(raw_value)
        except ValueError:
            print("Введите целое число")
            continue
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
        state = "открыта"
    return f"[{task['id']}] {task['title']} | приоритет: {task['priority']} | {state}"


def show_menu():
    print()
    print("StudyHub Planner")
    print("list - показать задачи")
    print("exit - завершить работу")


def show_tasks(tasks):
    if len(tasks) == 0:
        print("Список задач пока пуст.")
    else:
        print(f"Задач в списке: {len(tasks)}")


def run():
    tasks = []
    while True:
        show_menu()
        command = input("Команда: ").strip().lower()
        if command not in ("list", "exit"):
            print("Неизвестная команда")
            continue
        if command == "exit":
            print("Работу завершили")
            break
        show_tasks(tasks)


run()
