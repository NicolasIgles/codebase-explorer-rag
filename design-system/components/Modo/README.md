# Modo

Cómo se nombra y se colorea cada forma de buscar: `palabras` (acotado), `significado` (semántica) y `hibrida` (completo). El color siempre acompaña al nombre, nunca lo reemplaza.

## Variantes

- `.modo-etiqueta`: punto cuadrado de 10px (`radio-3`) y el nombre en `texto-suave`; `data-mode="acotado"` o `"completo"`.
- `.modo-tarjeta`: tarjeta `hoja` de la guía con borde izquierdo de 4px en el color del modo (`--color-modo`) y punto junto al título; `data-mode` acotado, semantica o completo.

## Qué provee quien lo usa

El atributo `data-mode` y el nombre del modo. Los mismos colores pintan las barras del gráfico comparativo (`.barra-fila[data-mode]`).
