"""Colección única de fragmentos de código y documentación."""

from pathlib import Path
from uuid import uuid4

from fragmentos import normalizar
from ingesta_codigo import obtener_fragmentos as obtener_codigo
from ingesta_documentos import obtener_fragmentos_documentos


def obtener_fragmentos(carpeta, avisos=None, coleccion_id=None):
    carpeta = Path(carpeta).expanduser().resolve()
    identificador = coleccion_id or uuid4().hex
    codigo = obtener_codigo(carpeta, avisos)
    documentos = obtener_fragmentos_documentos(carpeta, avisos)
    return [normalizar(fragmento, identificador) for fragmento in codigo + documentos]
