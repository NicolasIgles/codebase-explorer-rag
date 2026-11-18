"""Filtros conservadores para revisar código antes de indexarlo fuera del equipo."""

import re
from pathlib import PurePosixPath


NOMBRES_SENSIBLES = {"secrets", "secret", "credentials", "credential", "private_keys", "private_key", "private"}
NOMBRE_SENSIBLE = re.compile(r"(?:^|[._-])(?:secrets?|credentials?|private[_-]?keys?)(?:$|[._-])", re.IGNORECASE)
PATRONES_CREDENCIALES = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk-|gh[pousr]_|xox[baprs]-)[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]",
        re.IGNORECASE,
    ),
)


def motivo_exclusion(fragmento):
    ruta = PurePosixPath(fragmento["ruta"])
    partes = {parte.lower() for parte in ruta.parts}
    if (partes & NOMBRES_SENSIBLES or any(parte.startswith(".") for parte in partes)
            or any(NOMBRE_SENSIBLE.search(parte) for parte in partes)):
        return "nombre de archivo o carpeta sensible"
    contenido = fragmento["codigo"] + "\n" + "\n".join(fragmento.get("importaciones", []))
    if any(patron.search(contenido) for patron in PATRONES_CREDENCIALES):
        return "posible credencial en el código"
    return None


def filtrar_indice_remoto(fragmentos):
    """Omite archivos completos si algún fragmento de ellos parece sensible."""
    excluidos = {}
    for fragmento in fragmentos:
        motivo = motivo_exclusion(fragmento)
        if motivo:
            excluidos[fragmento["ruta"]] = motivo
    permitidos = [f for f in fragmentos if f["ruta"] not in excluidos]
    return permitidos, excluidos
