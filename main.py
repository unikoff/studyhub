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

minutes_per_lesson = 40
break_minutes = 10
title = input("Название сессии: ").strip()
raw_lessons = input("Количество занятий: ")
lesson_count = int(raw_lessons)
study_minutes = lesson_count * minutes_per_lesson
total_minutes = study_minutes + break_minutes
full_hours = total_minutes // 60
minutes_left = total_minutes % 60

print(f"Сессия: {title}; всего {total_minutes} минут ({full_hours} ч {minutes_left} мин)")

# Экран StudyHub проверен перед записью
# Версия StudyHub проверена перед публикацией
