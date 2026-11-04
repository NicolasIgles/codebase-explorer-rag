# Codebase Explorer

Una demo RAG para hacer preguntas sobre código y documentación y abrir las fuentes de cada resultado. Permite probar un proyecto ficticio sin cargar nada o crear una colección temporal con archivos propios. La interfaz muestra hasta cinco fragmentos con archivo y líneas o página; cuando la evidencia no alcanza, se abstiene.

**Demo pública:** [codebase-explorer-rag.onrender.com](https://codebase-explorer-rag.onrender.com/). El ejemplo y las cargas propias funcionan en **Solo fuentes**, sin clave de OpenAI. Las respuestas y la búsqueda híbrida públicas siguen deshabilitadas hasta configurar la clave y los límites de gasto del proveedor.

## Probar en local

Se requiere Python 3.12 o posterior. Desde esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B -m uvicorn api_http:app --host 127.0.0.1 --port 8000
```

Abrí [http://127.0.0.1:8000/](http://127.0.0.1:8000/) para la web o [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) para el contrato HTTP. La búsqueda **Solo fuentes** funciona sin clave de API. Para respuestas e indexación, definí `OPENAI_API_KEY` en el entorno del servidor; nunca la agregues al repositorio. El usuario de la web confirma qué se envía antes de cada operación con OpenAI.

La CLI usa el mismo núcleo:

```powershell
.\.venv\Scripts\python.exe inicio.py
.\.venv\Scripts\python.exe inicio.py --privacidad acotado
.\.venv\Scripts\python.exe inicio.py --privacidad completo
```

## Qué puede consultar

- Código Python, JavaScript, JSX, TypeScript y TSX mediante `ast` y Tree-sitter.
- Markdown y TXT por secciones y bloques con líneas originales.
- PDF con texto seleccionable por página. Un PDF vacío, escaneado o ilegible genera un aviso; no hay OCR.
- El ejemplo fijo en `sample_project/` incluye código y documentación. `preguntas_ejemplo.json` contiene casos de código, documento, cruce y falta de evidencia.

El contrato común de fragmento está en `fragmentos.py`. `ingesta_fuentes.py` reúne código y documentos; `recuperacion_local.py` ordena por coincidencias; `semantica.py` calcula y combina embeddings; `servicio_consultas.py` aplica privacidad, permisos y validación; `api_http.py` expone esas operaciones. La interfaz es HTML, CSS y JavaScript sin framework.

## Modos y privacidad

| En la web | Servicio | OpenAI |
| --- | --- | --- |
| **Solo fuentes** | Extrae y busca en el servidor. | No recibe datos. No genera respuesta. |
| **Respuesta con fuentes** | Filtra archivos sensibles, recupera y muestra hasta cinco fragmentos. | Tras confirmar `ENVIAR`, recibe pregunta y fragmentos para responder. Si la búsqueda española no encuentra fuentes, una confirmación aparte permite enviar solo la pregunta para traducirla. |
| **Búsqueda híbrida** | Muestra alcance y exclusiones; combina ranking léxico y semántico. | Tras confirmar `INDEXAR`, recibe los fragmentos permitidos para embeddings si faltan en la caché, y la pregunta para su embedding. Una confirmación posterior permite enviar hasta cinco fuentes para responder. |

Una **carga propia llega a este servidor en los tres modos**. “Solo fuentes” significa que no se envía a OpenAI, no que el archivo permanezca en el dispositivo del visitante. El filtro de secretos es heurístico: se debe revisar el alcance antes de indexar. Las respuestas usan `store=false`; eso no equivale a ausencia total de registros del proveedor. Una cita comprueba la ubicación de un fragmento consultado, pero no demuestra que toda la respuesta sea correcta.

## Cargas temporales

`POST /cargas/colecciones` acepta de uno a cinco archivos individuales de código, Markdown, TXT o PDF, cada uno hasta 10 MB. No acepta ZIP ni rutas dentro del nombre. Los archivos se leen como datos y el código no se ejecuta. Cada colección usa un ID aleatorio de 128 bits; las consultas y fuentes se consultan bajo ese ID. Quien tenga el ID puede acceder a esa colección: no hay cuentas de usuario. Para publicación se requiere HTTPS.

Los archivos, índices y metadatos de una colección cargada se eliminan **como máximo a las 24 horas**, o antes con `DELETE /colecciones/{id}`. El servidor limpia al arrancar y en cada solicitud. Las sesiones del ejemplo duran **30 minutos** por defecto. Las sesiones están en memoria: un reinicio las termina antes. En Render Free, el servicio se duerme tras 15 minutos sin tráfico y pierde también los archivos cargados; por lo tanto, una colección propia solo está disponible mientras esa instancia siga activa. El directorio de cargas se configura con `RAG_UPLOAD_DIR` (por defecto, un directorio temporal del sistema).

El backend limita 500 caracteres por pregunta, 20 consultas por colección, 8 colecciones simultáneas y 20 solicitudes por origen cada 60 segundos. Las cargas tienen un límite agregado de 50 MB por solicitud, 100 MB de almacenamiento temporal (con reserva para vectores), 1000 fragmentos y 8 MB de texto de entrada o extraído por colección. Se rechazan documentos que generarían más de 1000 bloques y código con más de 5000 líneas o una línea de más de 10 000 bytes. Por eso un archivo de menos de 10 MB también puede ser rechazado. Solo se procesa una carga por vez. Estos topes contienen recursos, pero no sustituyen alertas ni límites de gasto del proveedor. Detrás de un proxy se debe verificar cómo llega la IP real antes de configurar `RAG_PROXY_TRUSTED_CIDRS`; por defecto se ignoran `X-Real-IP` y `X-Forwarded-For`.

## Índice del ejemplo

`index_ejemplo/ejemplo-v1.json` contiene los vectores de los 19 fragmentos actuales del ejemplo. Se incluye en la imagen o el repositorio para evitar reindexar en cada arranque. Las preguntas nuevas generan un vector en vivo y no se guardan en esa caché. Si cambian los archivos o el modelo, reconstruí el índice con:

```powershell
.\.venv\Scripts\python.exe -B preparar_indice_ejemplo.py
```

El script muestra el alcance y exige escribir `INDEXAR` antes de enviar los fragmentos a OpenAI. El Dockerfile instala dependencias y copia el índice, sin usar la clave en la construcción.

## Evaluación y pruebas

`eval_heldout/` es un proyecto sintético separado del ejemplo público y de los conjuntos usados para ajustar reglas. El conjunto actual tiene **7 preguntas respondibles y 2 negativas**. En la última ejecución, la búsqueda léxica colocó una fuente esperada primera en **6/7**, recuperó todas las esperadas entre cinco en **5/7** y dejó sin fuentes **2/2** negativas. Semántica e híbrida lograron **6/7** primeras y **7/7** coberturas; ambas devolvieron candidatos en las dos negativas. La latencia media de recuperación fue 0,94 ms local y 609 ms semántica/híbrida con el índice ya preparado. Son pocos casos sintéticos; no estiman precisión en proyectos reales.

Reproducir la medición sin API:

```powershell
.\.venv\Scripts\python.exe -B evaluar_holdout.py
```

Para comparar los mismos casos con búsqueda semántica e híbrida, el evaluador exige `OPENAI_API_KEY` y `--todos --autorizar-indexar`. Para evaluar respuestas y abstenciones, sumá `--respuestas --autorizar-responder`. En la última ejecución, los modos léxico e híbrido respondieron **6/7** positivas con una cita esperada y se abstuvieron en **2/2** negativas. Se hicieron 9 peticiones de embeddings (171 tokens con índice caliente) y 15 de respuesta (6586 tokens de entrada y 848 de salida). Los 12 textos afirmativos se revisaron contra sus fragmentos y no se detectaron afirmaciones sin respaldo; esta revisión es pequeña y no sustituye una evaluación externa. La pregunta sobre pagos estaba mal etiquetada en la primera versión: `docs/correccion_evaluacion.md` conserva la explicación y la medición inicial. El conjunto ya fue inspeccionado, por lo que dejó de ser ciego para ajustes futuros. Los experimentos previos se resumen en `docs/experimentos_previos.md`.

Las pruebas automatizadas simulan OpenAI y verifican CLI, ingesta, privacidad, citas, API, aislamiento, vencimiento y límites:

```powershell
.\.venv\Scripts\python.exe -B -m unittest -q test_inicio.py test_semantica.py test_validar_evidencia.py test_multistack.py test_servicio_consultas.py test_api_http.py test_ingesta_documentos.py test_cargas_temporales.py
```

En la última ejecución local pasaron **72 pruebas**. También se verificó en navegador una respuesta del ejemplo con cita a `permissions.py`, una abstención sin fuentes y la carga de código y Markdown con borrado manual.

En una medición local de Windows sin OpenAI, cinco TXT sintéticos (625 fragmentos) tardaron 0,216 s en cargarse y alcanzaron 83,9 MiB de memoria residente del proceso. Un PDF sintético de 100 páginas (100 fragmentos) tardó 0,075 s y alcanzó 81,9 MiB. Estos casos no cubren un PDF de 10 MB malicioso, concurrencia ni el límite real de un contenedor de 0,5 GB.

## Contenedor y despliegue

El `Dockerfile` usa Python y un solo proceso Uvicorn. La imagen escucha en `PORT` (8080 por defecto) y usa `/data/cargas` para archivos temporales; ese directorio necesita un volumen si se desea conservarlos durante reinicios. El índice del ejemplo viaja en la imagen. No se necesita una base vectorial administrada.

```powershell
docker build -t codebase-explorer .
docker run --rm -p 8000:8080 --memory=512m -e OPENAI_API_KEY -v rag-cargas:/data/cargas codebase-explorer
```

Docker no está instalado en el entorno local, pero Render Free construyó la imagen desde este repositorio y el despliegue quedó activo. Desde la URL pública se verificaron una fuente de código con ubicación, una abstención sin fuentes, una carga de Python y Markdown y su borrado manual. `/estado` indicó que el índice del ejemplo está preparado y que no hay clave de OpenAI en el servidor. La memoria observada estuvo aproximadamente entre 60 y 80 MB, por debajo de los 512 MB del plan; no se han probado cargas máximas ni concurrencia en ese contenedor.

Render Free [duerme el servicio tras 15 minutos sin tráfico y pierde los archivos locales](https://render.com/docs/free). Una sesión o colección cargada puede desaparecer antes de las 24 horas, y el primer acceso posterior puede tardar alrededor de un minuto. El límite por origen se aplica hoy al par del proxy (`127.0.0.1` en los registros), por lo que se comparte entre visitantes; no se confía en cabeceras de IP reenviadas sin verificar su tratamiento. Antes de habilitar respuestas públicas hay que configurar en OpenAI un límite de gasto efectivo y una alerta, guardar una clave de proyecto solo en las variables de Render y volver a probar consentimiento, citas y costos reales. No habilites `RAG_HABILITAR_RUTAS_LOCALES=1` en una instancia pública; esa opción expone `POST /colecciones` para elegir carpetas del servidor y está reservada al desarrollo local.
