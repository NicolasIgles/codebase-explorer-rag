"""Recuperación léxica sobre una colección de fragmentos preparada."""

import math
import re
import unicodedata

from rag.fragmentos import se_superponen
from rag.ingesta_codigo import obtener_fragmentos


PALABRAS_COMUNES = {
    "a", "al", "algo", "alguien", "como", "con", "cual", "cuales", "cuando",
    "de", "del", "donde", "el", "en", "es", "esta", "este", "funcion",
    "hay", "la", "las", "lo", "los", "para", "por", "que", "quien", "se",
    "si", "su", "un", "una", "y",
    "an", "and", "are", "by", "class", "does", "for", "from", "function",
    "how", "in", "into", "is", "method", "of", "the", "to", "where", "which",
    "with",
    # Relleno frecuente en preguntas sobre personas o documentos: no identifica contenido.
    "algun", "alguna", "alguno", "cuanta", "cuantas", "cuanto", "cuantos", "fue", "habla",
    "hizo", "mas", "maneja", "sabe", "saben", "son", "sus", "tenia", "tiene", "tienen", "tuvo",
    "trabajo",  # "¿Trabajó con pandas?": como verbo de la pregunta arrastra cualquier "trabajo en…"
    "any", "did", "had", "has", "have", "her", "him", "his", "know", "knows", "she", "they",
    "was", "were", "what", "who",
}
# Palabras de dos letras que sí distinguen: siglas como BI, JS, UX, CI, CD, QA o ML.
CORTAS_COMUNES = {
    "al", "de", "el", "en", "es", "la", "le", "lo", "me", "mi", "ni", "no", "se", "si", "su",
    "te", "tu", "un", "ya", "yo",
    "am", "an", "as", "at", "be", "by", "do", "he", "if", "in", "is", "it", "my", "of", "on",
    "or", "so", "to", "up", "us", "we",
}
# Grupos de sinónimos para documentos: secciones típicas en español e inglés y datos de contacto.
GRUPOS_SINONIMOS = [
    {"email", "correo", "mail"},
    {"telefono", "celular", "movil", "phone", "mobile", "whatsapp"},
    {"estudio", "estudios", "estudiar", "formacion", "educacion", "universidad", "titulo",
     "carrera", "licenciatura", "grado", "study", "studied", "education", "university", "degree"},
    {"idiomas", "idioma", "lenguas", "languages", "language"},
    {"experiencia", "laboral", "empleo", "experience", "employment"},
    {"habilidades", "conocimientos", "tecnologias", "herramientas", "competencias", "skills", "tools"},
    {"premio", "premios", "reconocimiento", "mencion", "award", "awards"},
    {"actualmente", "actualidad", "actual", "presente", "present", "current", "currently"},
]
SINONIMOS = {
    palabra: tuple(sorted(grupo - {palabra}))
    for grupo in GRUPOS_SINONIMOS for palabra in grupo
}
PATRON_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PATRON_TELEFONO = re.compile(r"\+?\d[\d ().-]{7,}\d")
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


def palabra_util(palabra, sueltas=frozenset()):
    """Las palabras de dos letras solo valen si estaban escritas sueltas (BI, CI/CD, Node.js),
    no si salieron de partir un nombre como URLs o iOS."""
    if palabra in PALABRAS_COMUNES:
        return False
    if len(palabra) == 2:
        return palabra in sueltas and not palabra.isdigit() and palabra not in CORTAS_COMUNES
    return len(palabra) >= 3


def separar_palabras(texto, unir=False):
    """Normaliza tildes y separa nombres como can_edit_task o canEditTask.

    Con unir=True también conserva la forma unida de nombres como JavaScript, PostgreSQL,
    Node.js o CI/CD, para que "javascript" o "nodejs" escritos de corrido los encuentren.
    """
    texto = "".join(
        letra for letra in unicodedata.normalize("NFD", texto)
        if unicodedata.category(letra) != "Mn"
    )
    unidas = []
    if unir:
        for coincidencia in re.finditer(r"[A-Za-z][A-Za-z0-9]*(?:[./][A-Za-z0-9]+)*", texto):
            nombre = coincidencia.group()
            if re.search(r"[a-z][A-Z]|[./]", nombre):
                junta = re.sub(r"[^a-z0-9]", "", nombre.lower())
                if 3 <= len(junta) <= 30:
                    unidas.append(junta)
    # Siglas en plural (LLMs, APIs, URLs): se toman en singular en vez de partirlas en "LL" + "Ms".
    texto = re.sub(r"(?<![A-Za-z0-9])([A-Z]{2,})s(?![A-Za-z0-9])", r"\1", texto)
    sueltas = frozenset(re.findall(r"(?<![A-Za-z0-9])[A-Za-z0-9]{2}(?![A-Za-z0-9])", texto.lower()))
    texto = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", texto)
    texto = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", texto).replace("_", " ")
    return [
        ALIAS_TECNICOS.get(palabra, palabra)
        for palabra in re.findall(r"[a-z0-9]+", texto.lower())
        if palabra_util(palabra, sueltas)
    ] + unidas


def marcas_de_contacto(texto):
    """Agrega términos para datos que no se nombran: un correo o un teléfono escritos sin rótulo."""
    marcas = []
    if PATRON_EMAIL.search(texto):
        marcas.append("email")
    if any(
        numero.group().startswith("+") or sum(c.isdigit() for c in numero.group()) >= 9
        for numero in PATRON_TELEFONO.finditer(texto)
    ):
        marcas.append("telefono")
    return marcas


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


def coincidencia_documento(termino, palabra):
    """Como similitud_palabras, pero acepta sinónimos con algo menos de peso."""
    valor = similitud_palabras(termino, palabra)
    if valor < 1.0:
        for sinonimo in SINONIMOS.get(termino, ()):
            valor = max(valor, 0.8 * similitud_palabras(sinonimo, palabra))
    return valor


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
    comparadores = []
    for fragmento in fragmentos:
        documento = fragmento.get("tipo_fuente", fragmento.get("tipo")) == "documento"
        partes = {
            "simbolo": separar_palabras(
                fragmento["contenedor"] + " " + fragmento["simbolo"]
            ),
            "descripcion": separar_palabras(fragmento["descripcion"], unir=documento),
            "codigo": separar_palabras(fragmento["codigo"], unir=documento)
            + (marcas_de_contacto(fragmento.get("texto", fragmento["codigo"])) if documento else []),
            "ruta": separar_palabras(fragmento["ruta"]),
        }
        campos.append(partes)
        comparadores.append(coincidencia_documento if documento else similitud_palabras)

    puntuaciones = [0.0] * len(fragmentos)
    aciertos = [0] * len(fragmentos)
    presentes = 0
    for termino in terminos:
        frecuencia = sum(
            any(
                comparar(termino, palabra) > 0
                for palabras in partes.values() for palabra in palabras
            )
            for partes, comparar in zip(campos, comparadores)
        )
        presentes += frecuencia > 0
        importancia = 1 + math.log((len(fragmentos) + 1) / (frecuencia + 1))
        for indice, partes in enumerate(campos):
            comparar = comparadores[indice]
            valor = max(
                (
                    peso * comparar(termino, palabra)
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

    # En una colección hecha solo de documentos (un CV, un informe), los términos que no aparecen
    # en ninguna fuente ("nivel", "empresa") no cuentan para el mínimo: la pregunta casi nunca repite
    # las palabras del texto. Si hay código se mantiene la exigencia original, que ayuda a abstenerse
    # y a ofrecer la traducción cuando una pregunta en español no encuentra nada.
    solo_documentos = all(comparar is coincidencia_documento for comparar in comparadores)
    minimo = 1 if (presentes if solo_documentos else len(terminos)) <= 2 else 2
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
