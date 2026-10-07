from app.errors import TaskNotFoundError
from app.validators import validate_task_id


class PlannerService:
    def __init__(self, storage):
        self.storage = storage

    def list_tasks(self):
        return self.storage.load()

    def get_task(self, task_id):
        if type(task_id) is not int:
            raise ValueError("Номер задачи должен быть целым числом")
        task_id = validate_task_id(task_id)
        for task in self.storage.load():
            if task.id == task_id:
                return task
        raise TaskNotFoundError(f"Задача с номером {task_id} не найдена")

    def search_tasks(self, query):
        query = query.strip().lower()
        if not query:
            return []
        return [task for task in self.storage.load() if query in task.title.lower()]

    def get_statistics(self):
        tasks = self.storage.load()
        done = sum(task.is_done for task in tasks)
        total = len(tasks)
        return {"all": total, "open": total - done, "done": done}
