# Cita

El chip que dice de dónde salió una afirmación: archivo y líneas en `mono`, con borde 1.5px `tinta`. Al aparecer, el `resaltador` lo cubre de izquierda a derecha (clase `.marcada`), escalonado 120ms por cita.

## Cuándo usarla

- Bajo el texto de la respuesta, en `.citas` precedidas por "Fuente" o "Fuentes".
- Cada cita abre el fragmento correspondiente en el panel de evidencia.

## Qué provee quien la usa

Un `<button class="cita">` con el nombre de archivo (sin carpetas) y el rango de líneas o la página, un `aria-label` completo ("Cita 1: sample_project/permissions.py, líneas 4 a 6. Mostrar el fragmento") y `--i` con su índice para el escalonado. Agregá `.marcada` en el cuadro siguiente para que corra el resaltado.

## Evitá

- Resaltar en amarillo algo que no sea una cita o una línea citada.
