# Guía del proyecto de tareas

Este proyecto ficticio muestra cómo se crean, guardan, asignan y completan tareas. El código vive en los módulos Python del mismo directorio. Esta guía describe el flujo esperado; el código citado permite comprobar cada paso.

## Crear una tarea

Una solicitud de creación recibe identificador, título y responsable. La función create_task_request usa create_task para crear una tarea con estado pending y después llama a save_task para guardarla por identificador.

## Completar una tarea

complete_task_request carga la tarea con load_task. Si no existe o can_edit_task rechaza al usuario, devuelve None y no guarda cambios. Si está autorizada, complete_task devuelve una copia con estado completed y save_task la conserva.

## Permisos

La edición corresponde al administrador o a la persona responsable de la tarea. La visibilidad de un proyecto depende de que el identificador del usuario aparezca entre los miembros del proyecto. Estas reglas se comprueban en permissions.py.

## Reportes

count_pending_tasks cuenta tareas cuyo estado es pending. group_tasks_by_owner agrupa tareas por owner_id; no calcula prioridades ni fechas de vencimiento.
