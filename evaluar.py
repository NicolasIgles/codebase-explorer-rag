"""Evalúa la recuperación de código sin hacer llamadas a OpenAI."""

import argparse
import json
import statistics
import time
from pathlib import Path

from recuperacion_local import buscar_en_carpeta


def coincide(fragmento, caso):
    archivo = caso["expected_file"].replace("\\", "/")
    ruta = fragmento["ruta"]
    return (
        fragmento["simbolo"] == caso["expected_symbol"]
        and (ruta == archivo or ruta.endswith("/" + archivo))
    )


def evaluar(carpeta, archivo_preguntas):
    casos = json.loads(Path(archivo_preguntas).read_text(encoding="utf-8"))
    if not isinstance(casos, list) or not casos:
        raise ValueError("El archivo de preguntas debe contener una lista no vacía.")
    tiempos = []
    top_1 = 0
    top_3 = 0
    sin_respuesta_correctos = 0
    sin_respuesta_total = 0
    avisos_total = 0

    for numero, caso in enumerate(casos, start=1):
        if not isinstance(caso, dict) or not isinstance(caso.get("question"), str):
            raise ValueError(f"El caso {numero} no contiene una pregunta válida.")
        if caso.get("expected_symbol") is not None and not caso.get("expected_file"):
            raise ValueError(f"El caso {numero} necesita expected_file.")
        avisos = []
        comienzo = time.perf_counter()
        resultados = buscar_en_carpeta(carpeta, caso["question"], avisos=avisos)
        tiempos.append((time.perf_counter() - comienzo) * 1000)
        avisos_total += len(avisos)

        if caso.get("expected_symbol") is None:
            sin_respuesta_total += 1
            correcto = not resultados
            sin_respuesta_correctos += correcto
        else:
            correcto = bool(resultados) and coincide(resultados[0], caso)
            top_1 += correcto
            top_3 += any(coincide(fragmento, caso) for fragmento in resultados[:3])

        estado = "OK" if correcto else "REVISAR"
        primero = resultados[0]["simbolo"] if resultados else "sin resultados"
        ruta_primero = resultados[0]["ruta"] if resultados else ""
        print(f"{numero:02d} {estado}: {caso['question']}")
        print(f"   Primer resultado: {primero} ({ruta_primero})")
        if not correcto and caso.get("expected_symbol") is not None:
            print(f"   Esperado: {caso['expected_symbol']} ({caso['expected_file']})")

    positivas = len(casos) - sin_respuesta_total
    print(f"\nUbicación correcta en primer lugar: {top_1}/{positivas}")
    print(f"Ubicación correcta entre tres: {top_3}/{positivas}")
    print(f"Preguntas sin respuesta detectadas: {sin_respuesta_correctos}/{sin_respuesta_total}")
    print(f"Mediana de búsqueda local: {statistics.median(tiempos):.2f} ms")
    print(f"Avisos de lectura: {avisos_total}")


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("carpeta", help="Carpeta del proyecto")
    analizador.add_argument("preguntas", help="JSON con preguntas y respuestas esperadas")
    opciones = analizador.parse_args()
    try:
        evaluar(opciones.carpeta, opciones.preguntas)
    except (OSError, ValueError) as error:
        analizador.exit(2, f"Error de evaluación: {error}\n")


if __name__ == "__main__":
    main()
