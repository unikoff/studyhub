# Проверка пути при смене cwd — занятие 34

Проверка сделана в одноразовой временной копии пакета `project/studyhub`, чтобы не создавать `app/storage.py` или рабочие данные Planner. В ней `storage.py` вычислял `DATA_FILE = Path(__file__).resolve().parent / "data" / "tasks.txt"`. После эксперимента временная папка была удалена.

## Первый запуск из `project`

Текущая папка: временный `.../project`, где доступен пакет `studyhub`.

```powershell
& 'C:\Project Python\studyhub\.venv\Scripts\python.exe' -c "from studyhub.storage import DATA_FILE; print(DATA_FILE.resolve())"
```

Полученный путь:

```text
C:\Temp\studyhub-lesson34-utb1tm62\project\studyhub\data\tasks.txt
```

## Повтор из `project-parent`

Текущая папка: временный каталог на уровень выше `project`. Чтобы отделить поиск пакета от пути данных, на время команды `PYTHONPATH` указывал на `project`:

```powershell
$project = (Get-Location).Path + '\project'
$env:PYTHONPATH = $project
& 'C:\Project Python\studyhub\.venv\Scripts\python.exe' -c "from studyhub.storage import DATA_FILE; print(DATA_FILE.resolve())"
Remove-Item Env:PYTHONPATH
```

Полученный путь:

```text
C:\Temp\studyhub-lesson34-utb1tm62\project\studyhub\data\tasks.txt
```

Оба абсолютных адреса совпали. Контрольный `Path("relative.txt").resolve()` дал разные адреса из двух cwd, значит относительный путь зависит от текущей папки, а `DATA_FILE` от `__file__` — от расположения модуля. `PYTHONPATH` только помог найти пакет и не менял `DATA_FILE`.

## Вывод

`cwd` определяет основу относительного пути; `PYTHONPATH` определяет, где Python ищет импортируемый пакет. Это разные настройки. Адрес, построенный от `__file__`, сохранился при смене cwd.

Проверка была проведена на временном примере; указанный путь `C:\Temp\...` существовал только во время эксперимента и не является путём данных StudyHub.