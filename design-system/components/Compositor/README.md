# Compositor

La caja donde se escribe la pregunta, fija al pie del chat, con el botón enviar en `resaltador`: el único botón amarillo, porque es el que sale a buscar evidencia.

## Anatomía

- `.compositor-caja`: `hoja`, borde 1.5px `regla-fuerte` (pasa a `tinta` con foco dentro), `radio-20`, `sombra-compositor`.
- `#question`: textarea de 1 fila que crece hasta 200px, `mensaje` (17px; 16px en pantallas chicas). El estilo se aplica por id.
- `.boton-enviar`: 46px, `resaltador` con borde 1.5px `tinta`, texto 800 "Buscar" y el ícono `buscar`. Hover `resaltador-hondo`, al presionar escala .97.
- `.compositor-pie`: ayuda y contador en `detalle`, `grafito`, números tabulares. Se oculta si no tiene hijos visibles.

## Qué provee quien lo usa

Un `<label>` (puede ser `sr-only`), el textarea con `maxlength`, el texto de ayuda y el contador. Un mensaje de `Estado` va encima de la caja.
