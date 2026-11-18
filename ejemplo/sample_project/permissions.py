"""Reglas de acceso del proyecto ficticio."""


def can_edit_task(user: dict, task: dict) -> bool:
    """Comprueba si el usuario puede editar la tarea por ser responsable o administrador."""
    return user.get("role") == "admin" or task.get("owner_id") == user.get("id")


def can_view_project(user: dict, project: dict) -> bool:
    """Verifica si el proyecto es visible para un usuario miembro."""
    return user.get("id") in project.get("member_ids", [])
