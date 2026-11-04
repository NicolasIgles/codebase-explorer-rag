# Experimentos anteriores

Estos resultados guiaron cambios en la recuperación y **no son evaluación independiente**.

- En el proyecto de ejemplo Python, la recuperación local ubicó 10/10 fuentes esperadas en primer lugar y detectó 2/2 preguntas sin respuesta.
- En un repositorio Python usado durante el ajuste, se observaron 25/28 fuentes en primer lugar y 26/28 entre las tres primeras.
- En dos repositorios web públicos usados para ajustar la búsqueda híbrida, se observaron 18/24 fuentes en primer lugar y 23/24 entre cinco. En dos repositorios adicionales, 9/13 y 13/13 respectivamente.
- Las pruebas de respuesta sobre esos conjuntos validaron citas y abstenciones puntuales, pero no establecen precisión general. Una cita válida puede acompañar una afirmación incorrecta.

Los scripts `evaluar.py`, `evaluar_semantica.py` y `evaluar_evidencia.py` permiten repetir partes de estos experimentos con sus conjuntos de preguntas. El proyecto `eval_heldout/` se reservó después para una medición separada.
