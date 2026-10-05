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
        title = input("Название сессии: ").strip()
        while title == "":
            print("Название не должно быть пустым")
            title = input("Название сессии: ").strip()

        raw_lessons = input("Количество занятий: ")
        lesson_count = int(raw_lessons)
        count_is_nonnegative = lesson_count >= 0

        if count_is_nonnegative:
            study_minutes = 0
            for number in range(lesson_count):
                print(f"Занятие {number + 1}: {title}")
                duration_text = input(f"Длительность занятия {number + 1} в минутах: ")
                duration_minutes = int(duration_text)
                study_minutes = study_minutes + duration_minutes

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
