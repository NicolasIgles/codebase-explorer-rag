"""Mensajes del proyecto ficticio."""


def build_assignment_message(task: dict) -> str:
    """Arma el mensaje para avisar la asignación de una tarea."""
    return f"Te asignaron la tarea: {task['title']}"
