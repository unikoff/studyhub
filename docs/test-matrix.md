# Матрица проверок

| Риск | Уровень | Проверка в проекте | Наблюдаемый результат |
|---|---|---|---|
| Команда показывает неверный ответ или меняет не те данные | CLI regression | `tests/test_cli.py` | Сообщения и состояние Task после add/list/find/search/done/delete/stats |
| Чтение или отказ вызывает лишнюю запись | CLI regression | `tests/test_cli.py` | Наблюдательная обёртка фиксирует `save`; read-only, exit, неверный id и повторный done его не вызывают |
| Мутация не сохраняет либо сохраняет повторно | CLI regression | `tests/test_cli.py` | Успешные add/done/delete вызывают ровно один `save` |
| Несовместимость сервиса с JSON или потеря состояния при перезапуске | Integration | `tests/test_persistence.py` | Новый `PlannerService` на том же `tmp_path` восстанавливает id, поля и статус |
| Неизвестный id изменяет сохранённый набор | Integration | `tests/test_persistence.py` | `TaskNotFoundError`, исходный JSON не меняется |
| Повреждённый JSON маскируется под пустую базу | Integration | `tests/test_persistence.py` | `StorageError`, исходные байты сохраняются |
| Сборка делает IO или импорт запускает меню | CLI boundary | `tests/test_cli.py` | Переданный storage не вызывается при сборке; default выбирает JsonStorage; subprocess import без вывода |
| Инварианты Task и копирование MemoryStorage | Unit | Не покрыто автоматическими тестами этого checkout | Этапы 41–41.2 отсутствуют; эти правила остаются известной областью без unit-регрессий |

Запуск полного имеющегося набора из корня: `python -m pytest -q`. Тесты используют `MemoryStorage` и `tmp_path`; пользовательский `data/tasks.json` не является фикстурой.
