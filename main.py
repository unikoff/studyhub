def create_task(task_id, title, priority):
    return {
        "id": task_id,
        "title": title,
        "priority": priority,
        "is_done": False,
    }


def normalize_title(title):
    return title.strip()


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
