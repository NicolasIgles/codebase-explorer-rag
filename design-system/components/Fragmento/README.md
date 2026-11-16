# Fragmento

La tarjeta de un resultado de la búsqueda en el panel de evidencia: de dónde viene, qué dice, por qué apareció y cuánto pesa frente a los demás.

## Anatomía

- Cabecera: `.fragmento-ruta` (`ruta`, 15px mono 500) con las líneas en `grafito`, e `Insignia`s a la derecha.
- `.fragmento-simbolo`: "Fragmento n." más el tipo y el símbolo (función, clase, sección).
- `.codigo`: bloque `papel`, `radio-10`, `codigo` (14px mono, interlineado 1.65), con número de línea en `grafito`. Las líneas citadas llevan `.marcada` y se cubren de `resaltador`, escalonadas 55ms (`--j`). Para documentos, `.codigo-texto` usa `texto` en 15px.
- `.razon`: "Por qué apareció: coincide con …" y cada término en `mark.termino` (700, subrayado `regla-fuerte`).
- `.relevancia`: barra `tinta` sobre carril `pista`, ancho relativo al mejor resultado; bajo 30% pasa a `regla-fuerte` (`.baja`).

## Variantes

- `.citado`: borde `tinta` e inset de 4px en `resaltador`.
- `.no-citado`: fondo transparente, borde punteado.

## Qué provee quien lo usa

Ruta, rango, símbolo, líneas (6 de código o 3 de texto en la vista previa), términos coincidentes y puntuación relativa. La tarjeta entra con subida y fundido, escalonada 60ms (`--i`).
