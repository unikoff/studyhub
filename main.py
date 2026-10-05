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

command = input("Команда calc или exit: ").strip().lower()

if command == "calc":
    title = input("Название сессии: ").strip()
    raw_lessons = input("Количество занятий: ")
    lesson_count = int(raw_lessons)
    has_title = bool(title)
    count_is_nonnegative = lesson_count >= 0

    if has_title and count_is_nonnegative:
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
        print("Расчёт отменён: название или количество не подходят")
elif command == "exit":
    print("Работу завершили")
else:
    print(f"Неизвестная команда: {command}")
# Экран StudyHub проверен перед записью
# Версия StudyHub проверена перед публикацией
