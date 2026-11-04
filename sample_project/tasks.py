"""Operaciones con tareas del proyecto ficticio."""


def create_task(title: str, owner_id: int) -> dict:
    """Crea una tarea nueva con título, responsable y estado pendiente."""
    return {"title": title, "owner_id": owner_id, "status": "pending"}


def complete_task(task: dict) -> dict:
    """Marca una tarea como terminada y devuelve una copia actualizada."""
    return {**task, "status": "completed"}


def assign_task(task: dict, owner_id: int) -> dict:
    """Cambia la persona asignada como responsable de una tarea."""
    return {**task, "owner_id": owner_id}
