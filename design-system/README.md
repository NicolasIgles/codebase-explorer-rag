Codebase Explorer es un laboratorio de RAG: preguntás algo sobre un proyecto de código y la interfaz muestra qué fragmentos encontró la búsqueda, qué se le envía al modelo y qué líneas sostienen cada afirmación. La metáfora visual tiene dos superficies y un marcador: **la columna es el expediente del proyecto, en tinta; el chat es la mesa de lectura, en papel; el amarillo de resaltador significa una sola cosa: evidencia** (y el botón que sale a buscarla).

## Contenido y voz

- Escribí en español rioplatense, con voseo: "Escribí tu pregunta", "Elegí archivos", "Soltá los archivos para preguntarles", "revisá las líneas citadas".
- Tratá a la persona de vos y hablá del sistema en tercera persona: "Encontró 3 fragmentos", "Usó 1 de los 2 fragmentos que encontró", "El modelo prefirió no responder en lugar de inventar".
- Mayúscula solo al inicio de la frase y en nombres propios ("Enviar a OpenAI y responder", "Cómo funciona RAG"). La marca va toda en minúscula: "codebase explorer".
- Los botones empiezan con un verbo y dicen qué pasa: "Autorizar y buscar", "Traducir y buscar de nuevo", "Ver qué se envía", "Borrar mis archivos del servidor".
- Sé honesto sobre los límites, sin dramatizar: "Una cita dice de dónde salió algo, no garantiza que esté bien: revisá las líneas citadas." "Se borran del servidor en menos de 24 horas."
- Antes de que algo salga del servidor, decí exactamente qué sale: "Para responder, se envían a OpenAI tu pregunta y los 3 fragmentos encontrados." "Solo se envía tu pregunta, ningún archivo."
- Números con el formato `es-AR` (`6.586`), plurales completos ("1 fragmento", "3 fragmentos"). Sin emoji, sin signos de exclamación.

## Fundamentos visuales

### Color

- Dos superficies. La columna lateral es `tinta` con texto `nieve` y secundario `niebla`; lo elevado dentro de ella es `tinta-alta` y sus bordes `tinta-borde`. El chat es `papel`; las tarjetas encima son `hoja` con borde `regla`.
- Texto sobre papel u hoja: principal en `tinta`, lectura secundaria en `texto-suave`, metadatos en `grafito`. Nada más claro que `grafito` para texto.
- `resaltador` es evidencia y nada más: citas marcadas, líneas citadas, la insignia "Citado", el botón enviar y el foco dentro de la columna. Nunca lo uses como decoración ni como color de marca genérico. El texto sobre `resaltador` siempre va en `tinta`.
- Los tres modos de búsqueda tienen color propio y siempre van con su nombre al lado: `palabras` (lexical), `significado` (semántica), `hibrida` (combinada). Se muestran como un punto cuadrado de 10px con `radio-3`, una barra o un borde, nunca como relleno de texto largo.
- Error: texto y borde `error` sobre `error-fondo`. No hay color de éxito: lo terminado se marca con un check sobre `tinta`.
- Los controles con borde `regla-fuerte` quedan por debajo de 3:1 sobre `hoja`; los sostiene su texto en `tinta` y, al hover o con foco, el borde pasa a `tinta`. Mantené ese patrón al crear controles nuevos.

### Tipografía

- Una familia para todo, `texto` (Atkinson Hyperlegible Next, 400/700/800), y `mono` (Atkinson Hyperlegible Mono, 400/500) para código, rutas, citas y fichas.
- Jerarquía por peso: 800 para títulos (`titular`, `titulo-guia`, `titulo-seccion`, `titulo-panel`), 700 para etiquetas y botones (`etiqueta`), 400 para leer. Los títulos grandes llevan tracking negativo.
- La respuesta del modelo se lee en `respuesta` (18px, interlineado 1.65) con un ancho máximo de 40em. El mínimo de la interfaz es `detalle` (14px): no bajes de ahí.
- Números que se comparan (pesos, contadores, posiciones) con `font-variant-numeric: tabular-nums`.

### Espaciado, radios y layout

- La grilla es de tres columnas: `lateral`, el chat (hilo centrado de hasta `hilo`) y el panel de evidencia (`panel`). Bajo 1240px la evidencia flota a la derecha; bajo 900px la columna pasa a ser un cajón con velo.
- Los espacios son los de la escala `espacio-*`: tarjetas con `espacio-14`/`espacio-16` de padding, gaps de `espacio-10` a `espacio-12` entre elementos hermanos, `espacio-32` entre turnos.
- Radios: `radio-8` para chips de código (citas, fichas), `radio-12` para botones, `radio-14` a `radio-18` para tarjetas, `radio-20` para el compositor y el mensaje del usuario, `radio-pill` para acciones e insignias.
- Bordes antes que sombras. Las tarjetas se separan con `regla`; lo que pide decisión (permiso, cita, botón enviar) lleva borde de 1.5px en `tinta`. La única sombra en reposo es `sombra-compositor`; las demás son de capas que flotan (`sombra-dialogo`, `sombra-panel-derecho`, `sombra-cajon`), siempre con velo `rgba(18, 26, 48, .45)`.

### Estados

- Foco de teclado: outline sólido de 3px en `foco` con 2px de separación; dentro de la columna, en `resaltador`.
- Hover: los controles con borde `regla-fuerte` pasan a borde `tinta`; `boton-principal` pasa a `#26335A`; el botón enviar pasa a `resaltador-hondo`.
- Deshabilitado: opacidad .55 y cursor `not-allowed`.
- Seleccionado o expandido: fondo `tinta` y texto blanco (acción de evidencia abierta, métrica activa) o `tinta-alta` con `marca-seleccion` en la columna.

### Movimiento

- Una sola curva de salida: `cubic-bezier(.2, .7, .2, 1)` (`--salida` en el código), con duraciones de .15s (hover) a .8s (barras).
- El gesto propio del sistema es el resaltador que pasa sobre la evidencia: el fondo amarillo crece de 0% a 100% de ancho sobre citas y líneas, escalonado 55 a 120ms por elemento.
- Las tarjetas entran con una subida de 6px y fundido; los paneles se deslizan 16 a 40px desde la derecha.
- Con `prefers-reduced-motion: reduce`, todo movimiento queda instantáneo.

## Iconografía

- Íconos de trazo propios, dibujados inline en el HTML con `stroke="currentColor"`, trazo de 1.8 a 2.2, extremos redondeados, en cajas de 16, 18, 20 o 28px. Copiados en el grupo de assets Icons, con la tinta resuelta a `tinta`.
- El ícono va a la izquierda del texto con un gap de `espacio-8` a `espacio-10` y hereda el color del control. En la columna se pintan en `niebla`.
- Los estados de etapa usan tres glifos: check (trazo blanco sobre `tinta`), guion (abstención, sobre `grafito`) y un giro de carga.
- La marca es un rectángulo redondeado en `resaltador` (lo resaltado) bajo dos líneas de texto: va junto al nombre "codebase explorer" en `texto` 800, 18px. Ver el grupo Logos.
- No hay emoji ni ilustraciones.

## Componentes

Los componentes son clases de CSS de `components/bundle.css` (el `styles.css` de la app), sin JavaScript de componentes: cada vista previa es una versión estática con el HTML que arma la app. Para usarlos, cargá `tokens.css`, las fuentes y `bundle.css`, y escribí el mismo marcado.

---

**No sincronizado** (desde `NicolasIgles/codebase-explorer-rag` en `main@0182b0f`): el repositorio no tiene una biblioteca de componentes, así que no hay `bundle.js`: los componentes se muestran como versiones estáticas de su marcado, con `styles.css` como `bundle.css` (sin sus `@font-face`, que ya declaran los tokens). `--texto`, `--mono` pasaron a `type.families`; `--lateral` y `--panel` a `anchos`; `--salida` (curva de movimiento) quedó documentada aquí porque el formato no tiene familia de movimiento. Los colores literales que no son variables (`#26335A` hover del botón principal, `#3DD6B0` punto de modelo conectado, `#6A7487` placeholder, `rgba(255, 255, 255, .05)` hover en la columna) quedan en `bundle.css` sin token. El espaciado y los radios no son variables en el código: son los valores repetidos de `styles.css`, con nombre por valor. No se sincronizaron el diálogo de fragmento, la guía, la comparación de búsquedas ni la tabla comparativa.
