# StudyHub Planner

StudyHub Planner — консольный менеджер задач и HTTP API на FastAPI. CLI и API используют одну SQLite-базу через общий PlannerService; каждая команда и каждый запрос получают отдельную SQLAlchemy Session.

## Требования

- Python 3.12; проект проверен на Python 3.12.10.
- Git для получения копии проекта.
- Runtime-зависимости перечислены в `requirements.txt`, инструменты тестирования — в `requirements-dev.txt`.

## Чистая установка в Windows PowerShell

Выполняйте команды из корня проекта:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Набор версий закреплён в requirements-файлах: FastAPI 0.142.2, Starlette 1.7.0, Uvicorn 0.54.0, pytest 8.4.2 и httpx2 2.13.1. Starlette TestClient использует httpx2; отдельная установка httpx не нужна и оставляет устаревший путь с предупреждением.

Пакеты приложения и проверок устанавливаются в отдельное `.venv`. Активировать окружение не нужно: каждая команда явно использует его Python.

## Запуск CLI

Перед первым запуском после переноса подготовьте локальную базу по инструкции ниже. Обычный запуск CLI и API не создаёт схему и не импортирует JSON автоматически.

```powershell
.\.venv\Scripts\python.exe -m app.main
```

CLI предлагает добавить, просмотреть, найти, изменить статус, удалить и искать задачи, а также показать статистику. Изменения сохраняются в базе, указанной через `DATABASE_URL`.

## Запуск API

Откройте второй терминал в корне проекта и запустите:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --reload
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Health: <http://127.0.0.1:8000/health>

CLI и API используют один файл SQLite из `DATABASE_URL`. Каждый новый запрос и запуск CLI читает ранее подтверждённые изменения из общей базы.

## Однократный перенос существующих задач

Перед переносом остановите API и CLI. Сохраните копию актуального `data/tasks.json` в локальный архив, проверьте адрес базы и убедитесь, что целевой файл базы новый или его таблица `tasks` пуста. Архивы и SQLite-файлы в `data/` игнорируются Git. Используйте один и тот же `DATABASE_URL` для инициализации, импорта, API и CLI; пример ниже соответствует настройке из `.env.example`.

```powershell
$databaseUrl = "sqlite:///data/studyhub.sqlite3"  # Тот же адрес, что в .env
$snapshot = "data/archives/tasks-before-sqlite-$(Get-Date -Format 'yyyyMMdd-HHmmss-fff').json"
New-Item -ItemType Directory -Force data/archives
Copy-Item -NoClobber data/tasks.json $snapshot
\.venv\Scripts\python.exe -m app.DBase.init_db
\.venv\Scripts\python.exe -m app.DBase.import_tasks --source $snapshot --database-url $databaseUrl
```

Импортёр откажется записывать снимок в непустую базу и после записи сверит все задачи независимым чтением. Не запускайте его повторно после успешного переноса; новые изменения сразу сохраняются в SQLite. Архивный JSON после переключения остаётся снимком до начала работы через SQL и не является актуальной резервной копией SQLite.

## HTTP API

| Метод | Путь | Назначение | Успешный ответ |
|---|---|---|---|
| `GET` | `/health` | Проверить доступность | `200` |
| `GET` | `/tasks` | Получить задачи; поддерживает `is_done`, `sort_desc`, `limit` | `200` |
| `GET` | `/tasks/{task_id}` | Получить задачу | `200` |
| `GET` | `/stats` | Получить число всех, открытых и завершённых задач | `200` |
| `POST` | `/tasks` | Создать задачу | `201` |
| `PUT` | `/tasks/{task_id}` | Полностью заменить поля задачи | `200` |
| `PATCH` | `/tasks/{task_id}` | Изменить переданные поля | `200` |
| `DELETE` | `/tasks/{task_id}` | Удалить задачу | пустой `204` |

Задачи имеют публичные поля `id`, `title`, `priority` и `is_done`. Некорректные входные данные дают `422`, а обращение к отсутствующей задаче — `404`. Формы запросов и ответы можно посмотреть в `/docs`.

## Автоматические проверки и Postman

Полный набор запускается из корня проекта:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Набор включает unit-проверки Task, MemoryStorage и PlannerService, проверки CLI и JSON-хранилища, а также HTTP API. В `tests/test_workflow.py` несколько запросов используют одно изолированное временное хранилище; автоматические тесты не очищают и не изменяют рабочий `data/tasks.json`. Состав проверок описан в [матрице](docs/test-matrix.md).

Для ручной проверки запустите Uvicorn, затем импортируйте `postman/planner-api.postman_collection.json` и `postman/local.postman_environment.json`. Выберите environment `Local` и отправляйте запросы на `http://127.0.0.1:8000`. Ручные запросы меняют общий локальный SQLite-файл.

## Хранение и ограничения

`Task` задаёт правила задачи, `PlannerService` координирует операции, а SQL-репозиторий сохраняет их в SQLite. FastAPI получает отдельную Session на запрос; CLI — на известную команду. JSON остаётся форматом явного однократного импорта до его удаления в следующем занятии.

SQLite хранится локально, без авторизации и развёртывания в production. Архивный JSON не синхронизируется с базой после импорта; храните резервную копию текущей SQLite отдельно.
