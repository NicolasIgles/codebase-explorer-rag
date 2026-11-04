"""API HTTP para el ejemplo público; rutas arbitrarias solo con habilitación local."""

import asyncio
import ipaddress
import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field
from ingesta_documentos import EXTENSIONES_DOCUMENTO
from cargas_temporales import (
    AlmacenCargas, MAX_ARCHIVOS, MAX_ARCHIVO_BYTES, MAX_FRAGMENTOS_CARGA, MAX_TOTAL_BYTES,
    VIDA_SEGUNDOS, validar_nombre,
)

from recuperacion_local import parece_espanol
from semantica import CACHE, ruta_cache
from servicio_consultas import (
    RespuestaModeloInvalida,
    alcance_indexacion,
    exigir_autorizacion,
    generar_respuesta,
    preparar_coleccion,
    recuperar_fuentes,
    traducir_pregunta,
)


EJEMPLO = Path(__file__).resolve().parent / "sample_project"
CACHE_EJEMPLO = Path(__file__).resolve().parent / "index_ejemplo"
STATIC_DIR = Path(__file__).resolve().parent / "static"
PREGUNTAS_EJEMPLO = Path(__file__).resolve().parent / "preguntas_ejemplo.json"


def entero_positivo(nombre, predeterminado):
    valor = int(os.getenv(nombre, str(predeterminado)))
    if valor < 1:
        raise ValueError(f"{nombre} debe ser mayor que cero.")
    return valor


def origen_peticion(request):
    """Solo interpreta cabeceras de cliente si el par TCP es un proxy confiable."""
    par = request.client.host if request.client else "desconocido"
    redes = os.getenv("RAG_PROXY_TRUSTED_CIDRS", "")
    try:
        ip_par = ipaddress.ip_address(par)
        confiable = any(
            ip_par in ipaddress.ip_network(cidr.strip(), strict=False)
            for cidr in redes.split(",") if cidr.strip()
        )
    except ValueError:
        confiable = False
    if not confiable:
        return par
    real = request.headers.get("x-real-ip", "")
    try:
        if real:
            return str(ipaddress.ip_address(real.strip()))
    except ValueError:
        return par
    cadena = request.headers.get("x-forwarded-for", "")
    try:
        direcciones = [ipaddress.ip_address(valor.strip()) for valor in cadena.split(",")]
    except ValueError:
        return par
    if not direcciones:
        return par
    # El proxy agrega el cliente real al extremo derecho. Ignorar prefijos falsos.
    return str(direcciones[-1])


@dataclass(frozen=True)
class LimitesApi:
    caracteres_pregunta: int = 500
    consultas_coleccion: int = 20
    colecciones_activas: int = 8
    peticiones_origen: int = 20
    ventana_segundos: int = 60
    vida_segundos: int = 1800

    @classmethod
    def desde_entorno(cls):
        return cls(
            caracteres_pregunta=entero_positivo("RAG_MAX_CARACTERES_PREGUNTA", 500),
            consultas_coleccion=entero_positivo("RAG_MAX_CONSULTAS", 20),
            colecciones_activas=entero_positivo("RAG_MAX_COLECCIONES", 8),
            peticiones_origen=entero_positivo("RAG_MAX_PETICIONES_ORIGEN", 20),
            ventana_segundos=entero_positivo("RAG_VENTANA_SEGUNDOS", 60),
            vida_segundos=entero_positivo("RAG_VIDA_COLECCION_SEGUNDOS", 1800),
        )


class NuevaColeccionEjemplo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modo: Literal["local", "acotado", "completo"] = "local"


class NuevaColeccionLocal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    carpeta: str = Field(min_length=1)
    modo: Literal["local", "acotado", "completo"] = "local"


class NuevaConsulta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pregunta: str = Field(min_length=1)
    autorizacion: str | None = None


class Confirmacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    autorizacion: str | None = None


class ColeccionesTemporales:
    """Sesiones y consultas aisladas, con vencimiento comprobado en cada solicitud."""

    def __init__(self, limites, reloj, cargas=None):
        self.limites = limites
        self.reloj = reloj
        self._datos = {}
        self._lock = Lock()
        self.cargas = cargas

    def _limpiar(self):
        ahora = self.reloj()
        for identificador, registro in list(self._datos.items()):
            if registro["vence"] <= ahora:
                del self._datos[identificador]
                if self.cargas:
                    self.cargas.borrar(identificador)

    def limpiar(self):
        with self._lock:
            self._limpiar()

    def _registro(self, identificador):
        self._limpiar()
        registro = self._datos.get(identificador)
        if registro is None:
            raise HTTPException(status_code=404, detail="Colección no encontrada o vencida.")
        return registro

    def reservar_coleccion(self, vida_segundos=None):
        with self._lock:
            self._limpiar()
            if len(self._datos) >= self.limites.colecciones_activas:
                raise HTTPException(
                    status_code=429,
                    detail="Se alcanzó el límite de colecciones activas.",
                )
            identificador = uuid4().hex
            self._datos[identificador] = {
                "coleccion": None,
                "consultas": {},
                "vence": self.reloj() + (vida_segundos or self.limites.vida_segundos),
            }
            return identificador

    def completar_coleccion(self, identificador, coleccion):
        with self._lock:
            registro = self._registro(identificador)
            registro["coleccion"] = coleccion

    def descartar_coleccion(self, identificador):
        with self._lock:
            self._datos.pop(identificador, None)
            if self.cargas:
                self.cargas.borrar(identificador)

    def obtener(self, identificador):
        with self._lock:
            coleccion = self._registro(identificador)["coleccion"]
            if coleccion is None:
                raise HTTPException(status_code=409, detail="La colección se está preparando.")
            return coleccion

    def reservar_consulta(self, identificador, pregunta):
        with self._lock:
            registro = self._registro(identificador)
            if len(registro["consultas"]) >= self.limites.consultas_coleccion:
                raise HTTPException(
                    status_code=429,
                    detail="Se alcanzó el límite de consultas de esta colección.",
                )
            consulta_id = uuid4().hex
            registro["consultas"][consulta_id] = {
                "estado": "preparando",
                "pregunta": pregunta,
                "fuentes": [],
                "segundos_recuperacion": 0.0,
                "segundos_traduccion": 0.0,
                "consulta_ingles": "",
                "traduccion_estado": "pendiente",
                "respuesta_estado": "pendiente",
            }
            return consulta_id

    def completar_consulta(self, identificador, consulta_id, resultado):
        with self._lock:
            consulta = self._registro(identificador)["consultas"][consulta_id]
            consulta.update({
                "fuentes": resultado["fuentes"],
                "segundos_recuperacion": resultado["segundos"],
                "estado": "lista",
            })

    def fallar_consulta(self, identificador, consulta_id):
        with self._lock:
            registro = self._datos.get(identificador)
            if registro and consulta_id in registro["consultas"]:
                registro["consultas"][consulta_id]["estado"] = "fallida"

    def obtener_consulta(self, identificador, consulta_id):
        with self._lock:
            consulta = self._registro(identificador)["consultas"].get(consulta_id)
            if consulta is None:
                raise HTTPException(status_code=404, detail="Consulta no encontrada.")
            if consulta["estado"] != "lista":
                raise HTTPException(status_code=409, detail="La consulta no está lista.")
            return dict(consulta)

    def iniciar_operacion(self, identificador, consulta_id, operacion):
        clave_estado = operacion + "_estado"
        clave_resultado = operacion + "_resultado"
        with self._lock:
            consulta = self._registro(identificador)["consultas"].get(consulta_id)
            if consulta is None:
                raise HTTPException(status_code=404, detail="Consulta no encontrada.")
            if operacion == "respuesta" and consulta["traduccion_estado"] == "en_proceso":
                raise HTTPException(
                    status_code=409,
                    detail="Esperá a que termine la traducción antes de responder.",
                )
            if operacion == "traduccion" and consulta["respuesta_estado"] != "pendiente":
                raise HTTPException(
                    status_code=409,
                    detail="La respuesta ya se inició para esta consulta.",
                )
            estado = consulta[clave_estado]
            if estado == "lista":
                return consulta[clave_resultado]
            if estado != "pendiente":
                raise HTTPException(
                    status_code=409,
                    detail=f"La {operacion} ya está en curso o falló; iniciá otra consulta.",
                )
            consulta[clave_estado] = "en_proceso"
            return None

    def terminar_operacion(self, identificador, consulta_id, operacion, resultado, cambios=None):
        with self._lock:
            consulta = self._registro(identificador)["consultas"][consulta_id]
            if cambios:
                consulta.update(cambios)
            consulta[operacion + "_resultado"] = resultado
            consulta[operacion + "_estado"] = "lista"

    def fallar_operacion(self, identificador, consulta_id, operacion):
        with self._lock:
            registro = self._datos.get(identificador)
            if registro and consulta_id in registro["consultas"]:
                registro["consultas"][consulta_id][operacion + "_estado"] = "fallida"

    def eliminar(self, identificador):
        with self._lock:
            self._limpiar()
            if self._datos.pop(identificador, None) is None:
                raise HTTPException(status_code=404, detail="Colección no encontrada o vencida.")
            if self.cargas:
                self.cargas.borrar(identificador)


class LimitadorRafagas:
    def __init__(self, limites, reloj):
        self.limites = limites
        self.reloj = reloj
        self._origenes = {}
        self._lock = Lock()

    def aceptar(self, origen):
        ahora = self.reloj()
        minimo = ahora - self.limites.ventana_segundos
        with self._lock:
            for clave, momentos in list(self._origenes.items()):
                while momentos and momentos[0] <= minimo:
                    momentos.popleft()
                if not momentos:
                    del self._origenes[clave]
            momentos = self._origenes.setdefault(origen, deque())
            if len(momentos) >= self.limites.peticiones_origen:
                return False
            momentos.append(ahora)
            return True


class CuerpoExcesivo(Exception):
    pass


class LimiteCuerpoCarga:
    """Detiene el flujo antes de que el parser acumule cargas demasiado grandes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/cargas/colecciones":
            return await self.app(scope, receive, send)
        total = 0

        async def recibir_limitado():
            nonlocal total
            mensaje = await receive()
            total += len(mensaje.get("body", b""))
            if total > MAX_TOTAL_BYTES + 100_000:
                raise CuerpoExcesivo
            return mensaje

        try:
            await self.app(scope, recibir_limitado, send)
        except CuerpoExcesivo:
            respuesta = JSONResponse(status_code=413, content={"detail": "La carga supera 50 MB."})
            await respuesta(scope, receive, send)


def crear_app(limites=None, permitir_rutas_locales=None, reloj=None, upload_dir=None, reloj_cargas=None):
    limites = limites or LimitesApi.desde_entorno()
    if permitir_rutas_locales is None:
        permitir_rutas_locales = os.getenv("RAG_HABILITAR_RUTAS_LOCALES") == "1"
    reloj = reloj or time.monotonic
    app = FastAPI(title="Codebase Explorer", version="1.2.0")
    app.add_middleware(LimiteCuerpoCarga)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
    cargas = AlmacenCargas(upload_dir, reloj_cargas)
    almacen = ColeccionesTemporales(limites, reloj, cargas)
    rafagas = LimitadorRafagas(limites, reloj)
    bloqueo_carga = asyncio.Lock()

    @app.get("/", include_in_schema=False)
    def pagina_inicial():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/preguntas-ejemplo")
    def preguntas_sugeridas():
        import json
        return json.loads(PREGUNTAS_EJEMPLO.read_text(encoding="utf-8-sig"))

    @app.get("/estado")
    def estado_publico():
        return {
            "modelo_disponible": bool(os.getenv("OPENAI_API_KEY")),
            "indice_ejemplo_preparado": ruta_cache(
                EJEMPLO, CACHE_EJEMPLO, "ejemplo-v1"
            ).is_file(),
        }

    @app.middleware("http")
    async def limites_y_limpieza(request: Request, siguiente):
        almacen.limpiar()
        cargas.limpiar()
        if request.url.path == "/cargas/colecciones":
            largo = request.headers.get("content-length")
            try:
                exceso = largo is not None and int(largo) > MAX_TOTAL_BYTES + 100_000
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Content-Length inválido."})
            if exceso:
                return JSONResponse(status_code=413, content={"detail": "La carga supera 50 MB."})
        if request.url.path.startswith(("/colecciones", "/ejemplo")):
            origen = origen_peticion(request)
            if not rafagas.aceptar(origen):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Demasiadas solicitudes desde este origen."},
                    headers={"Retry-After": str(limites.ventana_segundos)},
                )
        if request.url.path == "/cargas/colecciones" and request.method == "POST":
            if bloqueo_carga.locked():
                return JSONResponse(status_code=429, content={"detail": "Hay otra carga en proceso; reintentá."})
            async with bloqueo_carga:
                return await siguiente(request)
        return await siguiente(request)

    @app.exception_handler(PermissionError)
    async def permiso_denegado(_request, error):
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(RespuestaModeloInvalida)
    async def respuesta_invalida(_request, error):
        return JSONResponse(status_code=502, content={"detail": str(error)})

    @app.exception_handler(ValueError)
    async def valor_invalido(_request, error):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(OSError)
    async def error_archivo(_request, error):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(OpenAIError)
    async def error_modelo(_request, _error):
        return JSONResponse(status_code=502, content={"detail": "No se pudo consultar OpenAI."})

    def alcance_visible(coleccion):
        alcance = alcance_indexacion(coleccion)
        if coleccion["origen"] == "ejemplo":
            alcance["carpeta"] = "ejemplo"
        elif coleccion["origen"] == "carga":
            alcance["carpeta"] = "archivos subidos"
        return alcance

    def crear_coleccion(carpeta, modo, origen):
        identificador = almacen.reservar_coleccion()
        inicio = time.perf_counter()
        try:
            coleccion = preparar_coleccion(carpeta, modo, identificador)
            coleccion["origen"] = origen
            if origen == "ejemplo":
                coleccion["cache_dir"] = CACHE_EJEMPLO
                coleccion["cache_key"] = "ejemplo-v1"
            alcance = alcance_visible(coleccion) if modo == "completo" else None
            almacen.completar_coleccion(identificador, coleccion)
        except Exception:
            almacen.descartar_coleccion(identificador)
            raise
        return {
            "coleccion_id": identificador,
            "origen": origen,
            "modo": modo,
            "cantidad_fragmentos": len(coleccion["fragmentos"]),
            "avisos": coleccion["avisos"],
            "alcance": alcance,
            "tiempos": {"preparacion": time.perf_counter() - inicio},
        }

    @app.post("/ejemplo/colecciones", status_code=201)
    def crear_ejemplo(entrada: NuevaColeccionEjemplo):
        return crear_coleccion(EJEMPLO, entrada.modo, "ejemplo")

    @app.post("/cargas/colecciones", status_code=201)
    async def crear_carga(
        modo: Literal["local", "acotado", "completo"] = Form("local"),
        archivos: list[UploadFile] = File(...),
    ):
        if not 1 <= len(archivos) <= MAX_ARCHIVOS:
            raise HTTPException(413, f"Se admiten entre 1 y {MAX_ARCHIVOS} archivos.")
        nombres = [validar_nombre(archivo.filename) for archivo in archivos]
        if len({nombre.casefold() for nombre in nombres}) != len(nombres):
            raise HTTPException(422, "Los nombres de archivo deben ser únicos.")
        identificador = almacen.reservar_coleccion(VIDA_SEGUNDOS)
        inicio = time.perf_counter()
        try:
            contenidos = []
            total = 0
            for nombre, archivo in zip(nombres, archivos):
                contenido = await archivo.read(MAX_ARCHIVO_BYTES + 1)
                if len(contenido) > MAX_ARCHIVO_BYTES:
                    raise HTTPException(413, f"{nombre} supera 10 MB.")
                total += len(contenido)
                if total > MAX_TOTAL_BYTES:
                    raise HTTPException(413, "La carga supera 50 MB.")
                contenidos.append(contenido)
            texto_entrada = 0
            bloques_documento_estimados = 0
            for nombre, contenido in zip(nombres, contenidos):
                extension = Path(nombre).suffix.lower()
                if extension == ".pdf":
                    continue
                texto_entrada += len(contenido)
                if texto_entrada > 8_000_000:
                    raise HTTPException(413, "El texto de entrada supera 8 MB.")
                if contenido.count(b"\n") > 5000:
                    raise HTTPException(413, f"{nombre}: demasiadas líneas para una carga temporal.")
                if extension in EXTENSIONES_DOCUMENTO:
                    bloques_documento_estimados += (len(contenido) + 1599) // 1600
                elif any(len(linea) > 10_000 for linea in contenido.splitlines()):
                    raise HTTPException(413, f"{nombre}: contiene una línea de código demasiado extensa.")
            if bloques_documento_estimados > MAX_FRAGMENTOS_CARGA:
                raise HTTPException(413, "Los documentos generarían demasiados fragmentos.")
            carpeta = cargas.reservar(identificador, total)
            for nombre, contenido in zip(nombres, contenidos):
                (carpeta / nombre).write_bytes(contenido)
            coleccion = preparar_coleccion(carpeta, modo, identificador)
            coleccion["origen"] = "carga"
            coleccion["cache_dir"] = carpeta / "vectores"
            if len(coleccion["fragmentos"]) > MAX_FRAGMENTOS_CARGA:
                raise HTTPException(413, "La carga genera demasiados fragmentos.")
            if sum(len(f["texto"].encode("utf-8")) for f in coleccion["fragmentos"]) > 8_000_000:
                raise HTTPException(413, "El texto extraído supera 8 MB.")
            alcance = alcance_visible(coleccion) if modo == "completo" else None
            almacen.completar_coleccion(identificador, coleccion)
            cargas.confirmar(identificador)
        except Exception:
            almacen.descartar_coleccion(identificador)
            raise
        finally:
            for archivo in archivos:
                await archivo.close()
        return {
            "coleccion_id": identificador, "origen": "carga", "modo": modo,
            "cantidad_fragmentos": len(coleccion["fragmentos"]),
            "avisos": coleccion["avisos"], "alcance": alcance,
            "vence_en_segundos": VIDA_SEGUNDOS,
            "tiempos": {"preparacion": time.perf_counter() - inicio},
        }

    if permitir_rutas_locales:
        @app.post("/colecciones", status_code=201)
        def crear_local(entrada: NuevaColeccionLocal):
            return crear_coleccion(entrada.carpeta, entrada.modo, "local_desarrollo")

    @app.get("/colecciones/{coleccion_id}/alcance")
    def ver_alcance(coleccion_id: str):
        return alcance_visible(almacen.obtener(coleccion_id))

    @app.post("/colecciones/{coleccion_id}/consultas", status_code=201)
    def crear_consulta(coleccion_id: str, entrada: NuevaConsulta):
        coleccion = almacen.obtener(coleccion_id)
        pregunta = entrada.pregunta.strip()
        if not pregunta:
            raise HTTPException(status_code=422, detail="Escribí una pregunta.")
        if len(pregunta) > limites.caracteres_pregunta:
            raise HTTPException(
                status_code=413,
                detail=f"La pregunta supera {limites.caracteres_pregunta} caracteres.",
            )
        if coleccion["modo"] == "completo":
            exigir_autorizacion("completo", "indexar código", entrada.autorizacion)
        consulta_id = almacen.reservar_consulta(coleccion_id, pregunta)
        try:
            resultado = recuperar_fuentes(coleccion, pregunta, entrada.autorizacion)
            almacen.completar_consulta(coleccion_id, consulta_id, resultado)
        except Exception:
            almacen.fallar_consulta(coleccion_id, consulta_id)
            raise
        return {
            "consulta_id": consulta_id,
            "pregunta": pregunta,
            "fuentes": resultado["fuentes"],
            "avisos": resultado["avisos"],
            "tiempos": {"recuperacion": resultado["segundos"]},
        }

    @app.get("/colecciones/{coleccion_id}/consultas/{consulta_id}/fuentes/{numero}")
    def ver_fuente(coleccion_id: str, consulta_id: str, numero: int):
        consulta = almacen.obtener_consulta(coleccion_id, consulta_id)
        if numero < 1 or numero > len(consulta["fuentes"]):
            raise HTTPException(status_code=404, detail="Fuente no encontrada.")
        return {"numero": numero, "fuente": consulta["fuentes"][numero - 1]}

    @app.post("/colecciones/{coleccion_id}/consultas/{consulta_id}/traduccion")
    def traducir(coleccion_id: str, consulta_id: str, entrada: Confirmacion):
        coleccion = almacen.obtener(coleccion_id)
        consulta = almacen.obtener_consulta(coleccion_id, consulta_id)
        if coleccion["modo"] != "acotado" or consulta["fuentes"] or not parece_espanol(consulta["pregunta"]):
            raise HTTPException(
                status_code=409,
                detail="La traducción solo corresponde a una búsqueda acotada sin fuentes en español.",
            )
        exigir_autorizacion("acotado", "traducir la pregunta", entrada.autorizacion)
        guardado = almacen.iniciar_operacion(coleccion_id, consulta_id, "traduccion")
        if guardado is not None:
            return guardado
        inicio = time.perf_counter()
        try:
            consulta_ingles = traducir_pregunta(
                coleccion, consulta["pregunta"], entrada.autorizacion
            )
            segundos_traduccion = time.perf_counter() - inicio
            if consulta_ingles:
                resultado = recuperar_fuentes(coleccion, consulta_ingles)
            else:
                resultado = {
                    "fuentes": [],
                    "avisos": list(coleccion["avisos"]) + ["No se obtuvo una consulta inglesa utilizable."],
                    "segundos": 0.0,
                }
            respuesta = {
                "consulta_id": consulta_id,
                "consulta_ingles": consulta_ingles,
                "fuentes": resultado["fuentes"],
                "avisos": resultado["avisos"],
                "tiempos": {
                    "recuperacion": consulta["segundos_recuperacion"] + resultado["segundos"],
                    "traduccion": segundos_traduccion,
                },
            }
            almacen.terminar_operacion(
                coleccion_id, consulta_id, "traduccion", respuesta,
                {
                    "fuentes": resultado["fuentes"],
                    "segundos_recuperacion": consulta["segundos_recuperacion"] + resultado["segundos"],
                    "segundos_traduccion": segundos_traduccion,
                    "consulta_ingles": consulta_ingles,
                },
            )
            return respuesta
        except Exception:
            almacen.fallar_operacion(coleccion_id, consulta_id, "traduccion")
            raise

    @app.post("/colecciones/{coleccion_id}/consultas/{consulta_id}/respuesta")
    def responder(coleccion_id: str, consulta_id: str, entrada: Confirmacion):
        coleccion = almacen.obtener(coleccion_id)
        consulta = almacen.obtener_consulta(coleccion_id, consulta_id)
        if coleccion["modo"] == "local":
            raise PermissionError("El modo local no envía código a OpenAI.")
        if consulta["fuentes"]:
            exigir_autorizacion(coleccion["modo"], "enviar fragmentos", entrada.autorizacion)
        guardado = almacen.iniciar_operacion(coleccion_id, consulta_id, "respuesta")
        if guardado is not None:
            return guardado
        try:
            resultado = generar_respuesta(
                coleccion, consulta["pregunta"], consulta["fuentes"], entrada.autorizacion
            )
            juicio = resultado["juicio"]
            respuesta = {
                "consulta_id": consulta_id,
                "fuentes": consulta["fuentes"],
                "hay_evidencia": juicio["hay_evidencia"],
                "respuesta": juicio["respuesta"],
                "citas": juicio["fuentes"],
                "abstencion": not juicio["hay_evidencia"],
                "avisos": coleccion["avisos"],
                "tiempos": {
                    "recuperacion": consulta["segundos_recuperacion"],
                    "traduccion": consulta["segundos_traduccion"],
                    "modelo": resultado["segundos"],
                },
            }
            almacen.terminar_operacion(coleccion_id, consulta_id, "respuesta", respuesta)
            return respuesta
        except Exception:
            almacen.fallar_operacion(coleccion_id, consulta_id, "respuesta")
            raise

    @app.delete("/colecciones/{coleccion_id}", status_code=204)
    def eliminar_coleccion(coleccion_id: str):
        almacen.eliminar(coleccion_id)
        return Response(status_code=204)

    return app


app = crear_app()
