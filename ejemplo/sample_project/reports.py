"""Reportes del proyecto ficticio."""


def count_pending_tasks(tasks: list[dict]) -> int:
    """Cuenta cuántas tareas siguen pendientes."""
    return sum(task.get("status") == "pending" for task in tasks)


def group_tasks_by_owner(tasks: list[dict]) -> dict[int, list[dict]]:
    """Agrupa las tareas por la persona responsable."""
    groups: dict[int, list[dict]] = {}
    for task in tasks:
        groups.setdefault(task["owner_id"], []).append(task)
    return groups
