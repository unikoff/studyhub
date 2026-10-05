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


project_name = "StudyHub 2"
version = 1
progress_percent = 0.0
is_ready = False

print(project_name)
print("Продолжаем обучение")
print("Версия обновлена")
print(project_name)
print(version)
print(progress_percent)
print(is_ready)

while True:
    raw_command = input("Команда calc или exit: ")
    command = raw_command.strip().lower()

    if command == "calc":
        title = normalize_title(input("Название сессии: "))
        while title == "":
            print("Название не должно быть пустым")
            title = normalize_title(input("Название сессии: "))

        raw_lessons = input("Количество занятий: ")
        lesson_count = int(raw_lessons)
        count_is_nonnegative = lesson_count >= 0

        if count_is_nonnegative:
            durations = []
            for number in range(lesson_count):
                print(f"Занятие {number + 1}: {title}")
                duration_text = input(f"Длительность занятия {number + 1} в минутах: ")
                duration_minutes = int(duration_text)
                durations.append(duration_minutes)

            print("Длительности:", durations)
            study_minutes = calculate_study_minutes(durations)
            break_minutes = 10
            total_minutes = study_minutes + break_minutes
            full_hours = total_minutes // 60
            minutes_left = total_minutes % 60
            print(f"Сессия: {title}; всего {total_minutes} минут ({full_hours} ч {minutes_left} мин)")
        else:
            print("Расчёт отменён: количество не подходит")
    elif command == "exit":
        break
    else:
        print(f"Неизвестная команда: {command}")

print("Работу завершили")
# Экран StudyHub проверен перед записью
# Версия StudyHub проверена перед публикацией
