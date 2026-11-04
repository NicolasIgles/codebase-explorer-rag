"""Recuperación léxica sobre una colección de fragmentos preparada."""

import math
import re
import unicodedata

from fragmentos import se_superponen
from ingesta_codigo import obtener_fragmentos


PALABRAS_COMUNES = {
    "a", "al", "algo", "alguien", "como", "con", "cual", "cuales", "cuando",
    "de", "del", "donde", "el", "en", "es", "esta", "este", "funcion",
    "hay", "la", "las", "lo", "los", "para", "por", "que", "quien", "se",
    "si", "su", "un", "una", "y",
    "an", "and", "are", "by", "class", "does", "for", "from", "function",
    "how", "in", "into", "is", "method", "of", "the", "to", "where", "which",
    "with",
}
ALIAS_TECNICOS = {
    "entero": "int",
    "enteros": "int",
    "integer": "int",
    "integers": "int",
    "urls": "url",
    "timed": "timestamp",
    "timestamps": "timestamp",
}
MARCAS_ESPANOL = {
    "archivo", "archivos", "como", "cual", "cuando", "donde", "funcion",
    "metodo", "para", "pregunta", "que", "quien", "tarea", "una",
}
MAX_FUENTES = 5


def separar_palabras(texto):
    """Normaliza tildes y separa nombres como can_edit_task o canEditTask."""
    texto = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", texto)
    texto = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", texto).replace("_", " ")
    texto = "".join(
        letra for letra in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(letra) != "Mn"
    )
    return [
        ALIAS_TECNICOS.get(palabra, palabra)
        for palabra in re.findall(r"[a-z0-9]+", texto)
        if len(palabra) >= 3 and palabra not in PALABRAS_COMUNES
    ]


def parece_espanol(pregunta):
    """Reconoce indicios simples de español para no traducir preguntas inglesas."""
    if "¿" in pregunta:
        return True
    normalizado = "".join(
        letra for letra in unicodedata.normalize("NFD", pregunta.lower())
        if unicodedata.category(letra) != "Mn"
    )
    palabras = set(re.findall(r"[a-z]+", normalizado))
    return bool(palabras & MARCAS_ESPANOL)


def similitud_palabras(pregunta, codigo):
    """Compara palabras exactas y variantes simples: tarea/tareas, crea/crear."""
    if pregunta == codigo:
        return 1.0
    if len(pregunta) >= 5 and len(codigo) >= 5 and pregunta[:5] == codigo[:5]:
        return 0.7
    return 0.0


def nombre_en_orden(terminos, nombre):
    """Detecta si las partes de un símbolo aparecen en el mismo orden en la pregunta."""
    partes = separar_palabras(nombre)
    if len(partes) < 2:
        return False
    posicion = 0
    for termino in terminos:
        if similitud_palabras(termino, partes[posicion]) > 0:
            posicion += 1
            if posicion == len(partes):
                return True
    return False


def ordenar_fragmentos(fragmentos, pregunta, limite=MAX_FUENTES):
    """Ordena una colección ya extraída sin volver a leer el proyecto."""
    if limite < 1:
        raise ValueError("El límite de fuentes debe ser mayor que cero.")
    terminos = list(dict.fromkeys(separar_palabras(pregunta)))
    if not terminos or not fragmentos:
        return []

    campos = []
    for fragmento in fragmentos:
        partes = {
            "simbolo": separar_palabras(
                fragmento["contenedor"] + " " + fragmento["simbolo"]
            ),
            "descripcion": separar_palabras(fragmento["descripcion"]),
            "codigo": separar_palabras(fragmento["codigo"]),
            "ruta": separar_palabras(fragmento["ruta"]),
        }
        campos.append(partes)

    puntuaciones = [0.0] * len(fragmentos)
    aciertos = [0] * len(fragmentos)
    for termino in terminos:
        frecuencia = sum(
            any(
                similitud_palabras(termino, palabra) > 0
                for palabras in partes.values() for palabra in palabras
            )
            for partes in campos
        )
        importancia = 1 + math.log((len(fragmentos) + 1) / (frecuencia + 1))
        for indice, partes in enumerate(campos):
            valor = max(
                (
                    peso * similitud_palabras(termino, palabra)
                    for campo, peso in (("simbolo", 5), ("descripcion", 3), ("codigo", 1), ("ruta", 1))
                    for palabra in partes[campo]
                ),
                default=0.0,
            )
            puntuaciones[indice] += importancia * valor
            if valor > 0:
                aciertos[indice] += 1

    pregunta_minuscula = pregunta.lower()
    pide_funcion = any(
        palabra in pregunta_minuscula for palabra in ("method", "método", "metodo", "function", "función")
    )
    pide_metodo = any(
        palabra in pregunta_minuscula for palabra in ("method", "método", "metodo")
    )
    pide_clase = not pide_funcion and any(
        palabra in pregunta_minuscula
        for palabra in ("class", "clase", "interface", "interfaz", "exception", "excepción", "serializer", "serializador")
    )
    for indice, fragmento in enumerate(fragmentos):
        if pide_funcion:
            puntuaciones[indice] *= 1.1 if fragmento["tipo"] == "funcion" else 0.4
        elif pide_clase:
            puntuaciones[indice] *= 1.5 if fragmento["tipo"] == "clase" else 0.6
        if nombre_en_orden(terminos, fragmento["simbolo"]):
            puntuaciones[indice] += 3
        partes_simbolo = separar_palabras(fragmento["simbolo"])
        if (
            pide_funcion and not pide_metodo
            and fragmento["tipo"] == "funcion" and not fragmento["contenedor"]
            and len(partes_simbolo) >= 2
            and all(
                any(similitud_palabras(termino, parte) > 0 for termino in terminos)
                for parte in partes_simbolo
            )
        ):
            puntuaciones[indice] += 15
        if pide_metodo and fragmento["tipo"] == "funcion" and fragmento["contenedor"]:
            puntuaciones[indice] *= 1.4
        if fragmento["contenedor"] and re.search(
            rf"(?<!\w){re.escape(fragmento['contenedor'])}(?!\w)", pregunta, re.I
        ):
            puntuaciones[indice] += 15
        simbolo = fragmento["simbolo"].lower()
        if (
            any(termino.startswith("encod") for termino in terminos)
            and "decode" in simbolo
        ) or (
            any(termino.startswith("decod") for termino in terminos)
            and "encode" in simbolo
        ):
            puntuaciones[indice] *= 0.5
        ruta = fragmento["ruta"].lower()
        if not any(palabra in pregunta_minuscula for palabra in ("test", "prueba")) and (
            "tests/" in ruta or ruta.split("/")[-1].startswith("test_")
        ):
            puntuaciones[indice] *= 0.55

    minimo = 1 if len(terminos) <= 2 else 2
    ordenados = sorted(
        (fragmento | {"puntuacion": puntuacion}
         for fragmento, puntuacion, cantidad in zip(fragmentos, puntuaciones, aciertos)
         if puntuacion > 0 and cantidad >= minimo),
        key=lambda fragmento: (
            -fragmento["puntuacion"],
            fragmento["fin"] - fragmento["inicio"],
            fragmento["ruta"],
            fragmento["inicio"],
        ),
    )

    if not ordenados:
        return []

    elegidos = []

    def agregar_sin_superponer(fragmento):
        # Una clase y uno de sus métodos pueden cubrir las mismas líneas.
        if len(elegidos) >= limite:
            return
        if any(se_superponen(fragmento, anterior) for anterior in elegidos):
            return
        elegidos.append(fragmento)

    agregar_sin_superponer(ordenados[0])
    principal = ordenados[0]
    if principal["tipo"] == "funcion" and principal["contenedor"]:
        for candidato in ordenados[1:]:
            if (
                candidato["ruta"] == principal["ruta"]
                and candidato["contenedor"] == principal["contenedor"]
                and principal["simbolo"] in candidato["metodos_llamados"]
            ):
                agregar_sin_superponer(candidato)
                break
    for nombre in principal["llamadas"]:
        if len(elegidos) >= limite:
            break
        posibles = [
            fragmento for fragmento in fragmentos
            if fragmento["simbolo"] == nombre
            and fragmento["tipo"] == "funcion"
            and fragmento["ruta"] != principal["ruta"]
        ]
        if len(posibles) == 1:
            agregar_sin_superponer(posibles[0])

    for fragmento in ordenados[1:]:
        if len(elegidos) >= limite:
            break
        agregar_sin_superponer(fragmento)
    return elegidos



def buscar_en_carpeta(carpeta, pregunta, limite=MAX_FUENTES, avisos=None):
    """Adaptador para evaluadores existentes."""
    return ordenar_fragmentos(obtener_fragmentos(carpeta, avisos), pregunta, limite)
