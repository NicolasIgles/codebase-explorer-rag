"""Funciones que coordinan operaciones del proyecto ficticio."""

from .permissions import can_edit_task
from .storage import load_task, save_task
from .tasks import complete_task, create_task


def create_task_request(task_id: int, title: str, owner_id: int) -> dict:
    """Procesa una solicitud para crear y guardar una tarea nueva."""
    task = create_task(title, owner_id)
    save_task(task_id, task)
    return task


def complete_task_request(user: dict, task_id: int) -> dict | None:
    """Procesa la solicitud de completar una tarea y comprueba los permisos."""
    task = load_task(task_id)
    if task is None or not can_edit_task(user, task):
        return None
    updated = complete_task(task)
    save_task(task_id, updated)
    return updated
