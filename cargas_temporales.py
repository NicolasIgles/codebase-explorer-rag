"""Archivos de visitantes: cuotas, aislamiento y borrado al vencer."""

import os
import re
import shutil
import time
import tempfile
from pathlib import Path
from threading import RLock

from fastapi import HTTPException

from ingesta_documentos import EXTENSIONES_DOCUMENTO
from lenguajes_js import EXTENSIONES as EXTENSIONES_JS


EXTENSIONES_PERMITIDAS = EXTENSIONES_DOCUMENTO | set(EXTENSIONES_JS) | {".py"}
MAX_ARCHIVOS = 5
MAX_ARCHIVO_BYTES = 10_000_000
MAX_TOTAL_BYTES = 50_000_000
MAX_DISCO_BYTES = 100_000_000
MAX_FRAGMENTOS_CARGA = 1000
RESERVA_INDICE_BYTES = 8_000_000
VIDA_SEGUNDOS = 24 * 60 * 60
PATRON_ID = re.compile(r"^[0-9a-f]{32}$")


class AlmacenCargas:
    def __init__(self, raiz=None, reloj=None):
        self.raiz = Path(raiz or os.getenv("RAG_UPLOAD_DIR") or
                         Path(tempfile.gettempdir()) / "codebase-explorer-cargas").resolve()
        self.reloj = reloj or time.time
        self._lock = RLock()
        self._reservas = {}
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.limpiar()

    def _ruta(self, identificador):
        if not PATRON_ID.fullmatch(identificador):
            raise ValueError("Identificador de colección inválido.")
        ruta = self.raiz / identificador
        if ruta.resolve().parent != self.raiz:
            raise ValueError("Ruta de carga fuera del almacenamiento permitido.")
        return ruta

    def _borrar(self, ruta):
        if ruta.is_symlink() or ruta.resolve().parent != self.raiz:
            return
        shutil.rmtree(ruta)

    def limpiar(self):
        with self._lock:
            ahora = self.reloj()
            for ruta in self.raiz.iterdir():
                if ruta.is_dir() and PATRON_ID.fullmatch(ruta.name):
                    marca = ruta / ".creado"
                    try:
                        creado = float(marca.read_text(encoding="ascii"))
                    except (OSError, ValueError):
                        creado = ruta.stat().st_mtime
                    if ahora - creado >= VIDA_SEGUNDOS:
                        self._borrar(ruta)
                        self._reservas.pop(ruta.name, None)

    def bytes_ocupados(self):
        total = 0
        for carpeta in self.raiz.iterdir():
            if not carpeta.is_dir() or carpeta.is_symlink():
                continue
            for actual, subcarpetas, archivos in os.walk(carpeta):
                subcarpetas[:] = [nombre for nombre in subcarpetas
                                  if not (Path(actual) / nombre).is_symlink()]
                total += sum((Path(actual) / nombre).stat().st_size for nombre in archivos
                             if not (Path(actual) / nombre).is_symlink())
        return total

    def reservar(self, identificador, bytes_entrantes):
        with self._lock:
            carpetas = sum(ruta.is_dir() and not ruta.is_symlink()
                           for ruta in self.raiz.iterdir())
            previsto = (self.bytes_ocupados() + sum(self._reservas.values()) +
                        bytes_entrantes + RESERVA_INDICE_BYTES * (carpetas + 1))
            if previsto > MAX_DISCO_BYTES:
                raise HTTPException(429, "El almacenamiento temporal está completo; probá más tarde.")
            ruta = self._ruta(identificador)
            ruta.mkdir(mode=0o700, exist_ok=False)
            self._reservas[identificador] = bytes_entrantes
            (ruta / ".creado").write_text(str(self.reloj()), encoding="ascii")
            return ruta

    def confirmar(self, identificador):
        with self._lock:
            self._reservas.pop(identificador, None)

    def borrar(self, identificador):
        with self._lock:
            ruta = self._ruta(identificador)
            if ruta.exists():
                self._borrar(ruta)
            self._reservas.pop(identificador, None)


def validar_nombre(nombre):
    if not nombre or len(nombre) > 120 or nombre in {".", ".."}:
        raise HTTPException(422, "Nombre de archivo inválido.")
    if "/" in nombre or "\\" in nombre or ":" in nombre or "\x00" in nombre:
        raise HTTPException(422, "No se permiten rutas en los nombres de archivo.")
    if Path(nombre).suffix.lower() not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(422, f"Formato no permitido: {nombre}")
    return nombre
