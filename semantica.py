"""Búsqueda semántica experimental con embeddings y caché JSON local."""

import hashlib
import json
import math
from pathlib import Path

from fragmentos import identidad, se_superponen
from ingesta_codigo import obtener_fragmentos
from recuperacion_local import ordenar_fragmentos


MODELO = "text-embedding-3-small"
DIMENSIONES = 256
TAMANO_LOTE = 64
CACHE = Path(__file__).parent / "cache_embeddings"


def texto_para_embedding(fragmento, usar_importaciones=True):
    nombre = ".".join(filter(None, (fragmento["contenedor"], fragmento["simbolo"])))
    importaciones = "\n".join(fragmento.get("importaciones", []))[:1200] if usar_importaciones else ""
    contexto = f"Importaciones usadas:\n{importaciones}\n" if importaciones else ""
    return (
        f"Archivo: {fragmento['ruta']}\nSímbolo: {nombre}\n"
        f"Descripción: {fragmento['descripcion'][:700]}\n"
        f"{contexto}"
        f"Código:\n{fragmento['codigo'][:2500]}"
    )


def similitud_coseno(a, b):
    producto = sum(x * y for x, y in zip(a, b))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    return producto / (norma_a * norma_b) if norma_a and norma_b else 0.0


def ruta_cache(carpeta, cache_dir=CACHE, cache_key=None):
    identificador = cache_key or hashlib.sha256(str(Path(carpeta).resolve()).encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / f"{identificador}.json"


def vectores(cliente, carpeta, textos, cache_dir=CACHE, cache_key=None):
    """Reutiliza embeddings de textos idénticos y guarda los nuevos por lote."""
    archivo = ruta_cache(carpeta, cache_dir, cache_key)
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    if datos.get("modelo") != MODELO or datos.get("dimensiones") != DIMENSIONES:
        datos = {"modelo": MODELO, "dimensiones": DIMENSIONES, "vectores": {}}
    guardados = datos["vectores"]
    claves = [hashlib.sha256(texto.encode("utf-8")).hexdigest() for texto in textos]
    faltantes = [(clave, texto) for clave, texto in dict(zip(claves, textos)).items() if clave not in guardados]
    for inicio in range(0, len(faltantes), TAMANO_LOTE):
        lote = faltantes[inicio:inicio + TAMANO_LOTE]
        respuesta = cliente.embeddings.create(
            model=MODELO,
            dimensions=DIMENSIONES,
            encoding_format="float",
            input=[texto for _, texto in lote],
        )
        for elemento in respuesta.data:
            guardados[lote[elemento.index][0]] = elemento.embedding
        archivo.parent.mkdir(parents=True, exist_ok=True)
        temporal = archivo.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos), encoding="utf-8")
        temporal.replace(archivo)
    return [guardados[clave] for clave in claves]


def seleccionar(fragmentos, limite=5):
    """Prefiere símbolos distintos y evita superposiciones de líneas."""
    elegidos = []
    simbolos = set()
    for permitir_repetidos in (False, True):
        for fragmento in fragmentos:
            identidad = (fragmento["ruta"], fragmento["contenedor"], fragmento["simbolo"])
            if not permitir_repetidos and identidad in simbolos:
                continue
            if any(se_superponen(fragmento, anterior) for anterior in elegidos):
                continue
            elegidos.append(fragmento)
            simbolos.add(identidad)
            if len(elegidos) >= limite:
                return elegidos
    return elegidos


def implementacion_desde_pruebas(fragmentos, semanticos):
    """Relaciona pruebas destacadas con el método que llaman en su módulo."""
    indice = {}
    for fragmento in fragmentos:
        ruta = Path(fragmento["ruta"])
        if ruta.name.startswith("test_") or fragmento["tipo"] != "funcion":
            continue
        clase = fragmento["contenedor"].split(".")[-1]
        clave = (ruta.stem, clase, fragmento["simbolo"])
        indice.setdefault(clave, []).append(fragmento)

    candidatos = {}
    for prueba in semanticos[:5]:
        ruta = Path(prueba["ruta"])
        clase = prueba["contenedor"].split(".")[-1]
        if not ruta.name.startswith("test_") or not clase.startswith("Test"):
            continue
        modulo = ruta.stem.removeprefix("test_")
        clase_origen = clase.removeprefix("Test")
        for metodo in prueba.get("atributos_llamados", []):
            for fuente in indice.get((modulo, clase_origen, metodo), []):
                clave = (fuente["ruta"], fuente["inicio"], fuente["fin"])
                datos = candidatos.setdefault(clave, {"fuente": fuente, "pruebas": set(), "llamadas": 0})
                datos["pruebas"].add((prueba["ruta"], prueba["inicio"], prueba["fin"]))
                datos["llamadas"] += 1

    elegibles = [datos for datos in candidatos.values() if len(datos["pruebas"]) >= 2]
    if not elegibles:
        return None
    mejor = max(
        elegibles,
        key=lambda datos: (len(datos["pruebas"]), datos["llamadas"], datos["fuente"]["similitud"]),
    )
    return mejor["fuente"]


def buscar_con_embeddings(carpeta, pregunta, cliente=None, cache_dir=CACHE, limite=5,
                          usar_importaciones=True, fragmentos=None, guardar_pregunta=True,
                          cache_key=None):
    """Devuelve resultados semánticos y combinados para compararlos."""
    if cliente is None:
        raise ValueError("Se requiere un cliente autorizado para calcular embeddings.")
    fragmentos = obtener_fragmentos(carpeta) if fragmentos is None else fragmentos
    if not fragmentos:
        return [], []
    textos = [texto_para_embedding(fragmento, usar_importaciones) for fragmento in fragmentos]
    texto_pregunta = "Pregunta sobre código: " + pregunta
    if guardar_pregunta:
        lista = vectores(cliente, carpeta, textos + [texto_pregunta], cache_dir, cache_key)
        vectores_codigo, pregunta_vector = lista[:-1], lista[-1]
    else:
        vectores_codigo = vectores(cliente, carpeta, textos, cache_dir, cache_key)
        respuesta = cliente.embeddings.create(
            model=MODELO,
            dimensions=DIMENSIONES,
            encoding_format="float",
            input=[texto_pregunta],
        )
        pregunta_vector = respuesta.data[0].embedding
    puntuados = [
        fragmento | {"similitud": similitud_coseno(vector, pregunta_vector)}
        for fragmento, vector in zip(fragmentos, vectores_codigo)
    ]
    semanticos = sorted(puntuados, key=lambda f: -f["similitud"])
    claves_lexicas = {
        identidad(f): posicion
        for posicion, f in enumerate(ordenar_fragmentos(fragmentos, pregunta), start=1)
    }
    combinados = []
    for posicion, fragmento in enumerate(semanticos, start=1):
        clave = identidad(fragmento)
        rango_lexico = claves_lexicas.get(clave)
        puntuacion = 2 / (20 + posicion)
        if rango_lexico is not None:
            puntuacion += 1 / (20 + rango_lexico)
        combinados.append(fragmento | {"puntuacion_hibrida": puntuacion})
    combinados.sort(key=lambda f: -f["puntuacion_hibrida"])
    if "test" not in pregunta.lower() and "prueba" not in pregunta.lower():
        implementacion = implementacion_desde_pruebas(puntuados, semanticos)
        if implementacion is not None:
            combinados = [combinados[0], implementacion] + combinados[1:]
    return seleccionar(semanticos, limite), seleccionar(combinados, limite)
