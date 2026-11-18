"""Extracción de Markdown, TXT y PDF sin ejecutar archivos."""

import os
import re
from io import BytesIO
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextContainer
from pdfminer.pdfparser import PDFSyntaxError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from rag.ingesta_codigo import CARPETAS_IGNORADAS, registrar_aviso


EXTENSIONES_DOCUMENTO = {".md", ".markdown", ".txt", ".pdf"}
MAX_BYTES_DOCUMENTO = 10_000_000
MAX_PAGINAS_PDF = 100
MAX_LINEAS_BLOQUE = 30
MAX_CARACTERES_BLOQUE = 1600


def archivos_documento(carpeta, avisos=None):
    def avisar(error):
        registrar_aviso(avisos, f"No se pudo recorrer {error.filename}: {error.strerror}")

    for actual, subcarpetas, archivos in os.walk(carpeta, onerror=avisar):
        subcarpetas[:] = sorted(
            nombre for nombre in subcarpetas
            if nombre not in CARPETAS_IGNORADAS and not nombre.startswith(".")
        )
        for nombre in sorted(archivos):
            if Path(nombre).suffix.lower() in EXTENSIONES_DOCUMENTO:
                yield Path(actual) / nombre


def titulo_en_mayusculas(linea):
    """Títulos de plantillas PDF: un renglón corto todo en mayúsculas, como EXPERIENCIA o SKILLS."""
    texto = linea.strip()
    letras = [c for c in texto if c.isalpha()]
    return (
        3 <= len(texto) <= 40 and len(letras) >= 3
        and all(c.isupper() for c in letras)
        and not texto.endswith((".", ":", ",")) and not texto.startswith(("•", "-", "*"))
    )


def bloques(lineas, titulo_inicial, titulos_mayusculas=False):
    """Entrega bloques con ubicación estable dentro de secciones.

    Los renglones en blanco no cuentan para el límite de renglones de un bloque.
    """
    secciones = []
    titulo = titulo_inicial
    inicio = 1
    for numero, linea in enumerate(lineas, start=1):
        encabezado = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", linea)
        if not encabezado and titulos_mayusculas and titulo_en_mayusculas(linea):
            encabezado = re.match(r"^\s*(.+?)\s*$", linea)
        if encabezado:
            if numero > inicio:
                secciones.append((inicio, numero - 1, titulo))
            titulo = encabezado.group(1).strip()
            inicio = numero
    if inicio <= len(lineas):
        secciones.append((inicio, len(lineas), titulo))
    for primero, ultimo, titulo in secciones:
        actual = primero
        while actual <= ultimo:
            fin = actual
            caracteres = 0
            renglones = 0
            while fin <= ultimo and renglones < MAX_LINEAS_BLOQUE:
                largo = len(lineas[fin - 1]) + 1
                if fin > actual and caracteres + largo > MAX_CARACTERES_BLOQUE:
                    break
                caracteres += largo
                renglones += bool(lineas[fin - 1].strip())
                fin += 1
            yield actual, fin - 1, titulo
            actual = fin


def fragmentos_textuales(texto, ruta, extension, pagina=None, desplazamiento=0):
    lineas = texto.splitlines()
    resultado = []
    if not any(linea.strip() for linea in lineas):
        return resultado
    for inicio_local, fin_local, titulo in bloques(lineas, Path(ruta).stem, titulos_mayusculas=extension == ".pdf"):
        contenido = "\n".join(lineas[inicio_local - 1:fin_local]).strip()
        if not contenido:
            continue
        inicio = desplazamiento + inicio_local
        fin = desplazamiento + fin_local
        segmentos = [(contenido, None, None)]
        if inicio_local == fin_local and len(lineas[inicio_local - 1]) > MAX_CARACTERES_BLOQUE:
            linea = lineas[inicio_local - 1]
            segmentos = [
                (linea[columna:columna + MAX_CARACTERES_BLOQUE], columna + 1,
                 min(columna + MAX_CARACTERES_BLOQUE, len(linea)))
                for columna in range(0, len(linea), MAX_CARACTERES_BLOQUE)
            ]
        for texto_segmento, columna_inicio, columna_fin in segmentos:
            ubicacion = (
                {"tipo": "pagina", "pagina": pagina, "inicio": inicio_local, "fin": fin_local}
                if pagina is not None else
                {"tipo": "lineas", "inicio": inicio, "fin": fin}
            )
            if columna_inicio is not None:
                ubicacion.update({"columna_inicio": columna_inicio, "columna_fin": columna_fin})
            codigo = (
                f"{inicio}: {texto_segmento}" if columna_inicio is not None else
                "\n".join(
                    f"{desplazamiento + numero}: {lineas[numero - 1]}"
                    for numero in range(inicio_local, fin_local + 1)
                )
            )
            resultado.append({
                "ruta": ruta, "inicio": inicio, "fin": fin, "pagina": pagina,
                "ubicacion": ubicacion, "simbolo": titulo, "contenedor": "",
                "tipo": "documento", "tipo_fuente": "documento",
                "lenguaje": extension.lstrip("."), "titulo": titulo,
                "descripcion": texto_segmento[:300], "texto": texto_segmento,
                "codigo": codigo,
                "metadatos": {"formato": extension.lstrip(".")},
                "llamadas": [], "metodos_llamados": [], "atributos_llamados": [],
            })
    return resultado


GLIFO_SIN_MAPA = re.compile(r"\(cid:\d+\)")


def unir_letras_espaciadas(linea):
    """Convierte "E X P E R I E N C I A   L A B O R A L" en "EXPERIENCIA LABORAL".

    Con espaciado entre letras (tracking), pdfminer separa cada carácter con un espacio y deja
    tres o más entre palabras. Solo se toca un renglón cuando casi todo son caracteres sueltos.
    """
    piezas = [pieza for pieza in linea.split(" ") if pieza]
    if len(piezas) < 3 or sum(len(pieza) == 1 for pieza in piezas) < 0.9 * len(piezas):
        return linea
    palabras = re.split(r" {2,}", linea.strip())
    return " ".join(palabra.replace(" ", "") for palabra in palabras)


def limpiar_texto_pdf(texto):
    """Repara artefactos típicos de plantillas: letras espaciadas y viñetas sin mapa Unicode."""
    texto = GLIFO_SIN_MAPA.sub("•", texto)
    return "\n".join(unir_letras_espaciadas(linea) for linea in texto.split("\n"))


def textos_por_pagina(contenido, maximo):
    """Reconstruye renglones por posición, también cuando el PDF dibuja cada palabra por separado.

    pypdf sigue el orden del archivo y, en PDFs exportados por editores visuales, entrega una palabra
    por renglón. pdfminer agrupa caracteres por cercanía y separa columnas en bloques.
    Devuelve None si pdfminer no puede leer el archivo, para volver a pypdf.
    """
    try:
        paginas = []
        for pagina in extract_pages(BytesIO(contenido), maxpages=maximo, laparams=LAParams()):
            bloques_texto = [
                elemento.get_text().strip("\n")
                for elemento in pagina if isinstance(elemento, LTTextContainer)
            ]
            paginas.append(limpiar_texto_pdf("\n\n".join(b for b in bloques_texto if b.strip())))
        return paginas
    except (PDFSyntaxError, OSError, ValueError, KeyError, TypeError, AssertionError, IndexError):
        return None


def fragmentos_desde_bytes(nombre, contenido, avisos=None):
    """Extrae una carga ya limitada en tamaño; nombre debe ser relativo y seguro."""
    extension = Path(nombre).suffix.lower()
    if extension not in EXTENSIONES_DOCUMENTO:
        raise ValueError(f"Formato documental no permitido: {extension}")
    if len(contenido) > MAX_BYTES_DOCUMENTO:
        raise ValueError(f"{nombre}: supera {MAX_BYTES_DOCUMENTO} bytes")
    if extension == ".pdf":
        try:
            lector = PdfReader(BytesIO(contenido), strict=False)
            if lector.is_encrypted:
                registrar_aviso(avisos, f"{nombre}: PDF cifrado; no se pudo extraer texto")
                return []
            resultado = []
            desplazamiento = 0
            reconstruidos = textos_por_pagina(contenido, MAX_PAGINAS_PDF) or []
            for numero, pagina in enumerate(lector.pages, start=1):
                if numero > MAX_PAGINAS_PDF:
                    registrar_aviso(avisos, f"{nombre}: se omitieron páginas después de {MAX_PAGINAS_PDF}")
                    break
                texto = reconstruidos[numero - 1] if numero <= len(reconstruidos) else ""
                if not texto.strip():
                    texto = limpiar_texto_pdf(pagina.extract_text() or "")
                resultado.extend(
                    fragmentos_textuales(texto, nombre, extension, numero, desplazamiento)
                )
                desplazamiento += max(1, len(texto.splitlines()))
            if not resultado:
                registrar_aviso(
                    avisos,
                    f"{nombre}: PDF sin texto seleccionable; puede ser escaneado (OCR no disponible)",
                )
            return resultado
        except (PdfReadError, OSError, ValueError, KeyError, TypeError) as error:
            registrar_aviso(avisos, f"{nombre}: PDF no utilizable ({error})")
            return []
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeError:
        texto = contenido.decode("utf-8", errors="replace")
        registrar_aviso(avisos, f"{nombre}: caracteres no UTF-8 reemplazados")
    return fragmentos_textuales(texto, nombre, extension)


def fragmentos_de_documento(ruta, carpeta, avisos=None):
    nombre = ruta.relative_to(carpeta).as_posix()
    try:
        if ruta.is_symlink():
            registrar_aviso(avisos, f"{nombre}: se omitió un enlace a otro archivo")
            return []
        if ruta.stat().st_size > MAX_BYTES_DOCUMENTO:
            registrar_aviso(avisos, f"{nombre}: se omitió por superar {MAX_BYTES_DOCUMENTO} bytes")
            return []
        return fragmentos_desde_bytes(nombre, ruta.read_bytes(), avisos)
    except OSError as error:
        registrar_aviso(avisos, f"{nombre}: no se pudo leer ({error})")
        return []


def obtener_fragmentos_documentos(carpeta, avisos=None):
    carpeta = Path(carpeta).expanduser().resolve()
    if not carpeta.is_dir():
        raise ValueError(f"No existe la carpeta: {carpeta}")
    resultado = []
    for cantidad, ruta in enumerate(archivos_documento(carpeta, avisos), start=1):
        if cantidad > 2000:
            registrar_aviso(avisos, "Se detuvo la lectura al llegar a 2000 documentos.")
            break
        resultado.extend(fragmentos_de_documento(ruta, carpeta, avisos))
    return resultado
