"""Almacenamiento en memoria del proyecto ficticio."""


TASKS: dict[int, dict] = {}


def save_task(task_id: int, task: dict) -> None:
    """Guarda una tarea en el almacenamiento usando su identificador."""
    TASKS[task_id] = task


def load_task(task_id: int) -> dict | None:
    """Recupera una tarea por identificador desde el almacenamiento."""
    return TASKS.get(task_id)
