# Accion

Píldora de 38px bajo una respuesta para abrir lo que la sostiene: la evidencia, la comparación con la búsqueda híbrida.

## Cuándo usarla

- Acciones secundarias de un turno, dentro de `.acciones-turno` (flex, gap `espacio-8`). El contenedor se oculta solo si todas sus acciones están `hidden`.
- `accion-evidencia` abre el panel de evidencia: lleva el ícono `panel` y `aria-expanded`. Expandida, se rellena de `tinta` con texto blanco.

## Qué provee quien la usa

`<button class="accion">` con texto (`etiqueta`, 15px 700), opcionalmente un ícono de 16px antes. Borde `regla-fuerte`, que pasa a `tinta` al hover; `radio-pill`.

## Evitá

- Usarla para la acción principal del turno: para eso está `boton-principal`.
