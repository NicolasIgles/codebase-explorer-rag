# Boton

Tres botones de texto para las decisiones dentro de un turno: `boton-principal` (relleno `tinta`, texto blanco, 46px de alto), `boton-secundario` (borde 1.5px `tinta` sobre `hoja`, 44px) y `boton-texto` (subrayado, sin caja, 40px).

## Cuándo usarlo

- `boton-principal`: la acción que hace avanzar el turno, una por bloque ("Enviar a OpenAI y responder", "Autorizar y buscar").
- `boton-secundario`: una alternativa que también actúa ("Traducir y buscar de nuevo", "Elegir archivos").
- `boton-texto`: ver más o cancelar sin salir del bloque ("Ver qué se envía", "Cancelar", "Ver el fragmento completo").
- Agrupalos en `.botonera` (flex, gap `espacio-12`): principal primero, texto al final.

## Qué provee quien lo usa

Un `<button type="button">` con la clase y un texto que empieza con verbo. Deshabilitado: atributo `disabled` (opacidad .55).

## Evitá

- Dos `boton-principal` en el mismo bloque.
- Usar `resaltador` en estos botones: el amarillo es solo para el botón enviar del compositor.
