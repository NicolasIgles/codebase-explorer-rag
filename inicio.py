"""Interfaz de consola para consultar código en modos local, acotado y completo."""

import argparse
import os
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

from fragmentos import lugar
from servicio_consultas import (
    alcance_indexacion,
    generar_respuesta,
    preparar_coleccion,
    recuperar_fuentes,
    traducir_pregunta,
)
from recuperacion_local import parece_espanol


def mensaje_error_api(error):
    if isinstance(error, AuthenticationError):
        return "La API rechazó OPENAI_API_KEY. Revisá la clave configurada."
    if isinstance(error, RateLimitError):
        return "La API alcanzó un límite de uso. Probá de nuevo más tarde."
    if isinstance(error, APITimeoutError):
        return "La API tardó demasiado en responder."
    if isinstance(error, APIConnectionError):
        return "No se pudo conectar con la API. Revisá la conexión."
    if isinstance(error, APIStatusError):
        return f"La API devolvió el estado HTTP {error.status_code}."
    return "No se pudo consultar el modelo."


def mostrar_fuentes(fuentes):
    print("Fragmentos candidatos:")
    for numero, fragmento in enumerate(fuentes, start=1):
        nombre = ".".join(filter(None, (fragmento["contenedor"], fragmento["simbolo"])))
        print(f"[{numero}] {lugar(fragmento)} ({nombre})")


def main(modo="local"):
    if modo not in {"local", "acotado", "completo"}:
        print(f"Modo de privacidad desconocido: {modo}")
        return 1
    carpeta = input("Carpeta del proyecto: ").strip().strip('"')
    pregunta = input("Pregunta sobre el código: ").strip()
    if not pregunta:
        print("Escribí una pregunta para buscar en el proyecto.")
        return 1

    inicio_busqueda = time.perf_counter()
    try:
        coleccion = preparar_coleccion(carpeta, modo)
    except (ValueError, OSError) as error:
        print(error)
        return 1

    autorizacion = None
    if modo == "completo":
        alcance = alcance_indexacion(coleccion)
        print(f'Carpeta: {alcance["carpeta"]}')
        print(
            f'Se enviarán {alcance["cantidad_fragmentos"]} fragmentos de '
            f'{len(alcance["rutas"])} archivos '
            f'({alcance["bytes_aproximados"]} bytes de texto aproximados):'
        )
        for ruta in alcance["rutas"]:
            print(f"  {ruta}")
        if alcance["excluidos"]:
            print("Archivos excluidos:")
            for ruta, motivo in sorted(alcance["excluidos"].items()):
                print(f"  {ruta}: {motivo}")
        if not coleccion["fragmentos"]:
            print("No hay fragmentos permitidos para indexar.")
            return 0
        autorizacion = input(
            "Enviar estos archivos a OpenAI para indexar y hasta cinco fuentes para responder? "
            "Escribí INDEXAR: "
        ).strip()
        if autorizacion != "INDEXAR":
            print("Indexación cancelada; no se envió código.")
            return 0
        if not os.getenv("OPENAI_API_KEY"):
            print("Falta OPENAI_API_KEY; no se envió código.")
            return 1
        inicio_busqueda = time.perf_counter()

    try:
        resultado = recuperar_fuentes(coleccion, pregunta, autorizacion)
    except OpenAIError as error:
        print(mensaje_error_api(error))
        return 1
    except (PermissionError, ValueError, OSError) as error:
        print(error)
        return 1
    fuentes = resultado["fuentes"]
    intento_traduccion = False
    if modo == "acotado" and not fuentes and parece_espanol(pregunta) and os.getenv("OPENAI_API_KEY"):
        autorizacion_traduccion = input(
            "Enviar solo la pregunta a OpenAI para traducirla? Escribí ENVIAR: "
        ).strip()
        if autorizacion_traduccion != "ENVIAR":
            print("Consulta cancelada; no se envió la pregunta.")
            return 0
        intento_traduccion = True
        try:
            consulta_ingles = traducir_pregunta(coleccion, pregunta, autorizacion_traduccion)
            if consulta_ingles:
                fuentes = recuperar_fuentes(coleccion, consulta_ingles)["fuentes"]
                print(f"Consulta ampliada al inglés: {consulta_ingles}")
            else:
                print("Aviso: no se obtuvo una consulta inglesa utilizable.")
        except OpenAIError as error:
            print(mensaje_error_api(error))
            return 1
        except (PermissionError, ValueError, OSError) as error:
            print(error)
            return 1

    segundos_busqueda = time.perf_counter() - inicio_busqueda
    for aviso in coleccion["avisos"][:5]:
        print(f"Aviso: {aviso}")
    if len(coleccion["avisos"]) > 5:
        print(f'Aviso: hay {len(coleccion["avisos"]) - 5} avisos adicionales.')

    etiqueta = (
        "Recuperación híbrida" if modo == "completo"
        else "Recuperación con traducción" if intento_traduccion
        else "Búsqueda local"
    )
    if not fuentes:
        print("No encontré código relacionado con la pregunta.")
        print(f"{etiqueta}: {segundos_busqueda:.3f} s")
        return 0

    mostrar_fuentes(fuentes)
    print(f"{etiqueta}: {segundos_busqueda:.3f} s")
    if modo == "local":
        print("Modo local: se mostraron fuentes sin enviar código a OpenAI.")
        return 0
    if not os.getenv("OPENAI_API_KEY"):
        print("Falta OPENAI_API_KEY en las variables de entorno; no se llamó al modelo.")
        return 1
    if modo == "acotado":
        autorizacion = input("Enviar estos fragmentos a OpenAI? Escribí ENVIAR: ").strip()
        if autorizacion != "ENVIAR":
            print("Consulta cancelada; no se enviaron fragmentos.")
            return 0

    try:
        respuesta = generar_respuesta(coleccion, pregunta, fuentes, autorizacion)
    except OpenAIError as error:
        print(mensaje_error_api(error))
        return 1
    except ValueError as error:
        if "fuentes" in str(error).lower() or "respuesta" in str(error).lower() or "modelo" in str(error).lower():
            print(f"No se pudo validar la respuesta del modelo: {error}")
        else:
            print(error)
        return 1
    except PermissionError as error:
        print(error)
        return 1
    juicio = respuesta["juicio"]
    if juicio["hay_evidencia"]:
        citas = " ".join(f"[{numero}]" for numero in juicio["fuentes"])
        print(f'Respuesta: {juicio["respuesta"]} {citas}')
    else:
        print("Respuesta: No encontré evidencia suficiente en las fuentes recuperadas.")
    print(f'Modelo: {respuesta["segundos"]:.3f} s')
    return 0


if __name__ == "__main__":
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--privacidad", choices=("local", "acotado", "completo"), default="local")
    opciones = analizador.parse_args()
    raise SystemExit(main(opciones.privacidad))
