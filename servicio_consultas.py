"""Núcleo de consultas compartido por la CLI y una futura API."""

import os
import time
from threading import Lock
from pathlib import Path

from openai import OpenAI

from fragmentos import identidad
from ingesta_fuentes import obtener_fragmentos
from privacidad import filtrar_indice_remoto
from recuperacion_local import MAX_FUENTES, ordenar_fragmentos, parece_espanol
from semantica import CACHE, buscar_con_embeddings, texto_para_embedding
from validar_evidencia import responder_con_evidencia


MODOS = {"local", "acotado", "completo"}
BLOQUEO_INDICE = Lock()


class RespuestaModeloInvalida(ValueError):
    """El modelo respondió sin respetar el contrato de evidencia."""


def preparar_coleccion(carpeta, modo="local", coleccion_id=None):
    """Lee el proyecto una vez y filtra lo que podría salir del equipo."""
    if modo not in MODOS:
        raise ValueError(f"Modo de privacidad desconocido: {modo}")
    carpeta = Path(carpeta).expanduser().resolve()
    avisos = []
    fragmentos = obtener_fragmentos(carpeta, avisos, coleccion_id)
    excluidos = {}
    if modo != "local":
        fragmentos, excluidos = filtrar_indice_remoto(fragmentos)
        if modo == "acotado":
            avisos.extend(
                f"{ruta}: excluido de envíos externos ({motivo})"
                for ruta, motivo in sorted(excluidos.items())
            )
    return {
        "carpeta": carpeta,
        "modo": modo,
        "fragmentos": fragmentos,
        "excluidos": excluidos,
        "avisos": avisos,
    }


def alcance_indexacion(coleccion):
    """Datos que deben mostrarse antes de solicitar INDEXAR."""
    if coleccion["modo"] != "completo":
        raise ValueError("El alcance de indexación requiere modo completo.")
    fragmentos = coleccion["fragmentos"]
    rutas = sorted({fragmento["ruta"] for fragmento in fragmentos})
    return {
        "carpeta": str(coleccion["carpeta"]),
        "cantidad_fragmentos": len(fragmentos),
        "rutas": rutas,
        "bytes_aproximados": sum(
            len(texto_para_embedding(fragmento).encode("utf-8"))
            for fragmento in fragmentos
        ),
        "excluidos": coleccion["excluidos"],
    }


def exigir_autorizacion(modo, accion, autorizacion):
    """Cada operación externa comprueba su autorización explícita."""
    esperada = "INDEXAR" if modo == "completo" else "ENVIAR"
    if modo == "local" or autorizacion != esperada:
        raise PermissionError(f"Se requiere {esperada} antes de {accion}.")


def cliente_openai(cliente=None, timeout=30.0, antes_envio=None):
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Falta OPENAI_API_KEY en las variables de entorno; no se llamó al modelo.")
    return cliente if cliente is not None else OpenAI(
        timeout=timeout, max_retries=0 if antes_envio else 1
    )


def traducir_pregunta(coleccion, pregunta, autorizacion=None, cliente=None, antes_envio=None):
    """Envía solo la pregunta tras ENVIAR; nunca envía fragmentos aquí."""
    if coleccion["modo"] != "acotado":
        raise ValueError("La traducción solo está disponible en modo acotado.")
    exigir_autorizacion("acotado", "traducir la pregunta", autorizacion)
    cliente = cliente_openai(cliente, antes_envio=antes_envio)
    if antes_envio:
        antes_envio()
    respuesta = cliente.responses.create(
        model="gpt-6-luna",
        store=False,
        instructions=(
            "Traducí esta pregunta al inglés para buscar en código fuente. "
            "Conservá los identificadores y términos técnicos. "
            "No respondas la pregunta ni inventes nombres de funciones o archivos. "
            "Devolvé solo una línea con la pregunta traducida."
        ),
        input=pregunta,
    )
    consulta = (respuesta.output_text or "").strip()
    return consulta if consulta and "\n" not in consulta and len(consulta) <= 300 else ""


def recuperar_fuentes(coleccion, pregunta, autorizacion=None, cliente=None, antes_envio=None):
    """Recupera sobre los fragmentos preparados, sin volver a recorrer la carpeta."""
    inicio = time.perf_counter()
    fragmentos = coleccion["fragmentos"]
    if coleccion["modo"] == "completo":
        if fragmentos:
            exigir_autorizacion("completo", "indexar código", autorizacion)
            cliente = cliente_openai(cliente, timeout=60.0, antes_envio=antes_envio)
            with BLOQUEO_INDICE:
                _, fuentes = buscar_con_embeddings(
                    coleccion["carpeta"], pregunta, cliente,
                    limite=MAX_FUENTES, fragmentos=fragmentos,
                    cache_dir=coleccion.get("cache_dir", CACHE),
                    guardar_pregunta=coleccion.get("origen") != "ejemplo",
                    cache_key=coleccion.get("cache_key"),
                    antes_envio=antes_envio,
                )
        else:
            fuentes = []
    else:
        fuentes = ordenar_fragmentos(fragmentos, pregunta, MAX_FUENTES)
    return {
        "fuentes": fuentes[:MAX_FUENTES],
        "avisos": list(coleccion["avisos"]),
        "segundos": time.perf_counter() - inicio,
    }


def generar_respuesta(coleccion, pregunta, fuentes, autorizacion=None, cliente=None,
                     antes_envio=None):
    """Valida el permiso justo antes de enviar fuentes y validar evidencia."""
    if coleccion["modo"] == "local":
        raise PermissionError("El modo local no envía código a OpenAI.")
    if not fuentes:
        return {
            "juicio": {"hay_evidencia": False, "respuesta": "", "fuentes": []},
            "segundos": 0.0,
        }
    exigir_autorizacion(coleccion["modo"], "enviar fragmentos", autorizacion)
    originales_por_ubicacion = {
        identidad(fragmento): fragmento
        for fragmento in coleccion["fragmentos"]
    }
    if len(fuentes) > MAX_FUENTES:
        raise ValueError("Se excedió el límite de fuentes.")
    originales = []
    for fragmento in fuentes:
        clave = identidad(fragmento)
        if clave not in originales_por_ubicacion:
            raise ValueError("Las fuentes no pertenecen a la colección preparada.")
        originales.append(originales_por_ubicacion[clave])
    permitidos, excluidos = filtrar_indice_remoto(originales)
    if excluidos or len(permitidos) != len(originales):
        raise ValueError("Las fuentes contienen código excluido por privacidad.")
    inicio = time.perf_counter()
    cliente = cliente_openai(cliente, antes_envio=antes_envio)
    try:
        juicio = responder_con_evidencia(
            cliente, pregunta, originales, antes_envio=antes_envio
        )
    except ValueError as error:
        raise RespuestaModeloInvalida(str(error)) from error
    return {"juicio": juicio, "segundos": time.perf_counter() - inicio}
