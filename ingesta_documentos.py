"""Extracción de Markdown, TXT y PDF sin ejecutar archivos."""

import os
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ingesta_codigo import CARPETAS_IGNORADAS, registrar_aviso


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


def bloques(lineas, titulo_inicial):
    """Entrega bloques con ubicación estable dentro de secciones."""
    secciones = []
    titulo = titulo_inicial
    inicio = 1
    for numero, linea in enumerate(lineas, start=1):
        encabezado = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", linea)
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
            while fin <= ultimo and fin - actual < MAX_LINEAS_BLOQUE:
                largo = len(lineas[fin - 1]) + 1
                if fin > actual and caracteres + largo > MAX_CARACTERES_BLOQUE:
                    break
                caracteres += largo
                fin += 1
            yield actual, fin - 1, titulo
            actual = fin


def fragmentos_textuales(texto, ruta, extension, pagina=None, desplazamiento=0):
    lineas = texto.splitlines()
    resultado = []
    if not any(linea.strip() for linea in lineas):
        return resultado
    for inicio_local, fin_local, titulo in bloques(lineas, Path(ruta).stem):
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
            for numero, pagina in enumerate(lector.pages, start=1):
                if numero > MAX_PAGINAS_PDF:
                    registrar_aviso(avisos, f"{nombre}: se omitieron páginas después de {MAX_PAGINAS_PDF}")
                    break
                texto = pagina.extract_text() or ""
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
