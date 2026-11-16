# Origen

El selector de qué se consulta, en la columna lateral: el proyecto de ejemplo o archivos propios. Botones de alternancia con ícono, nombre y detalle.

## Estados

- Reposo: texto `niebla`, sin fondo; hover con velo blanco al 5% y texto `nieve`.
- `aria-pressed="true"`: fondo `tinta-alta`, texto blanco y `marca-seleccion` (inset de 3px en `resaltador`).

## Qué provee quien lo usa

Dentro de `.lateral` (fondo `tinta`), un `.origen` con `role="group"` y su etiqueta; cada `<button class="origen-boton" aria-pressed>` con un ícono de 20px, `.origen-nombre` (700) y `.origen-detalle` (`detalle`).
