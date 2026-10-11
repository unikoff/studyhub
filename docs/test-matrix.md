# Матрица проверок

| Риск | Слой | Проверка | Ожидаемый результат |
| --- | --- | --- | --- |
| Неверная SQL-модель или отображение задачи | Unit / integration | `tests/test_dbase_models.py`, `tests/test_dbase_read_mapping.py` | Ограничения таблицы и преобразование ORM-строк в `Task` соответствуют контракту |
| Ошибка CRUD, фильтрации или поиска | Repository / service | `tests/test_sql_repository.py` | Операции, сортировка, фильтры, лимит, статистика и поиск согласованы с контрактом Planner |
| Несоответствие HTTP-контракта | API integration | `tests/test_api.py`, `tests/test_contract.py` | Статусы, схема ответов, валидация и отсутствие побочных изменений проверяются через TestClient |
| Разделение API и CLI состояния | Workflow integration | `tests/test_workflow.py`, `tests/test_sql_repository.py` | Обе границы читают и меняют одну изолированную SQLite-базу |
| Незакрытая транзакция или сессия | Database integration | `tests/test_dbase_sessions.py`, `tests/test_dbase_transactions.py` | Сессии закрываются, изменения коммитятся или откатываются в ожидаемых границах |
| Ошибка или потеря исходного JSON-снимка при импорте | Import integration | `tests/test_import_tasks.py` | Импортер валидирует источник, записывает только в пустую БД и оставляет JSON байт-в-байт неизменным |

Фикстуры создают отдельную временную SQLite-базу на тест. Rehearsal импорта копирует `data/tasks.json` в `tmp_path`; источник не изменяется и не используется как тестовая база. JSON поддерживается только для одноразового импорта снимка, не как backend приложения.
