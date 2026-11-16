# Etapas

El progreso de un turno como registro vertical de tres pasos (Recuperar, Armar el contexto, Responder con citas), plegado en una línea `.proceso` que se abre para ver el detalle.

## Estados (`data-state`)

- `idle`: aro `regla-fuerte`, texto `grafito`.
- `active`: giro en `tinta` sobre carril `pista`.
- `done`: círculo `tinta` con check blanco que se traza; la línea hacia el paso siguiente se llena de `tinta`.
- `waiting`: círculo `resaltador` con borde `tinta` y texto 700: espera una decisión de la persona (un permiso).
- `skipped`: aro punteado.
- `abstained`: círculo `grafito` con guion blanco: el modelo no respondió por falta de evidencia.

`.proceso` usa los mismos estados en su ícono de 18px y resume la etapa actual en su `<summary>`.

## Qué provee quien lo usa

Un `<details class="proceso">` con `<ol class="etapas">`; cada `<li class="etapa">` lleva la marca con los tres glifos (check, guion, giro) y un cuerpo con nombre en `<strong>` y `.etapa-texto` que describe el resultado en concreto ("3 fragmentos encontrados, en este servidor").
