# Permiso

La tarjeta que pide autorización antes de que algo salga del servidor. Todo lo que se envía a OpenAI pasa por una de estas.

## Anatomía

- `.permiso`: `hoja`, borde 1.5px `tinta`, `radio-16`, ancho máximo 40em.
- `.permiso-texto`: qué se envía y a quién, en `tinta`. El resto del texto va en `texto-suave`.
- `.paquete` (opcional): bloque `papel` con filas rótulo/valor (`paquete-rotulo` en `grafito`), la pregunta en 700 y las `Ficha`s.
- `.botonera`: `boton-principal` con el verbo de lo que autoriza ("Enviar a OpenAI y responder", "Autorizar y buscar") y `boton-texto` para ver el detalle o cancelar.

## Qué provee quien lo usa

Una frase exacta sobre lo que sale ("Solo se envía tu pregunta, ningún archivo."), el paquete si hay fragmentos, y cuánto dura la autorización.

## Evitá

- Esconder el permiso en un diálogo modal: va en el hilo, en el turno que lo necesita.
