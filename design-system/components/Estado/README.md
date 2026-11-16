# Estado

Mensajes breves del sistema: `.estado` sobre el compositor (neutro o `.error`) y `.aviso` dentro de un turno.

## Variantes

- `.estado`: `hoja`, borde `regla`, `radio-12`, 15px. Confirma algo que pasó ("Tus archivos se borraron del servidor.").
- `.estado.error`: texto y borde 1.5px `error` sobre `error-fondo`. Dice qué hacer, no solo qué falló ("Elegí al menos un archivo en la columna de la izquierda antes de preguntar.").
- `.aviso`: nota con línea izquierda de 3px `regla-fuerte`, texto `texto-suave` y un enlace opcional en 700. Explica un límite de la demo.

## Qué provee quien lo usa

El texto, en voseo, y `role="status"` en `.estado` para que se anuncie. Se oculta con `hidden` cuando no hay nada que decir.
