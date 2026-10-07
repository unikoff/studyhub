# Матрица проверок

| Риск | Уровень | Проверка в проекте | Наблюдаемый результат |
|---|---|---|---|
| Некорректные поля, изменение названия/приоритета, tags и представление Task | Unit | `tests/test_models.py` | Ошибочные значения дают ожидаемый `ValueError`; невалидное изменение не портит прежнее состояние |
| Потеря или неожиданное разделение состояния MemoryStorage | Unit | `tests/test_storage.py` | Входной и возвращённый контейнеры независимы; вложенные Task остаются общими ссылками по договору |
| Операция сервиса меняет не то состояние или сохраняет отказ | Unit | `tests/test_services.py` | Add/select/replace/patch/done/delete согласованы с состоянием; чтение, no-op и ошибки не вызывают лишний `save` |
| Старый JSON перестал загружаться после добавления tags | Integration | `tests/test_persistence.py` | Запись без tags восстанавливает Task с пустым списком и не переписывается при чтении |
| Файловое состояние теряется при перезапуске | Integration | `tests/test_persistence.py` | Новый `PlannerService` на том же `tmp_path` восстанавливает id, поля и статус |
| Неизвестный id изменяет сохранённый набор | Integration | `tests/test_persistence.py` | `TaskNotFoundError`, исходный JSON не меняется |
| Неверная JSON-схема или ошибка файловой системы маскируется под пустую базу | Integration | `tests/test_persistence.py` | `StorageError`; исходные данные не переписываются |
| Команда показывает неверный ответ, меняет не те данные или сохраняет лишний раз | CLI regression | `tests/test_cli.py` | Сообщения, состояние Task и количество вызовов `save` соответствуют действию |
| Сборка делает IO или импорт запускает меню | CLI boundary | `tests/test_cli.py` | Переданный storage не вызывается при сборке; default выбирает JsonStorage; subprocess import без вывода |
| HTTP API contract | Integration | `tests/test_api.py` | Маршруты, публичная схема, ошибки 404/422, PUT/PATCH и DELETE проверяются через ASGI без рабочей JSON-базы |
| Несогласованность операций в одном жизненном цикле задачи | Workflow integration | `tests/test_workflow.py` | Создание, чтение, PUT/PATCH, отказ, удаление и stats проходят через один TestClient и изолированный JsonStorage |

`tests/conftest.py` предоставляет каждому тесту новые Task, MemoryStorage и `PlannerService` по умолчанию. Параметризованные случаи проверяют варианты одного правила; файловые сценарии используют отдельные пути `tmp_path`. Пользовательский `data/tasks.json` не является фикстурой.

Запуск полного набора из корня: `python -m pytest -q`.
