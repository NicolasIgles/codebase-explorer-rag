"""Compara búsqueda local, semántica e híbrida; la semántica usa la API."""

import argparse
import json
from pathlib import Path

from openai import OpenAI

from evaluar import coincide
from recuperacion_local import buscar_en_carpeta
from semantica import buscar_con_embeddings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("carpeta")
    parser.add_argument("preguntas")
    parser.add_argument("--sin-importaciones", action="store_true",
                        help="Compara con embeddings que omiten el contexto de importaciones")
    args = parser.parse_args()
    casos = json.loads(Path(args.preguntas).read_text(encoding="utf-8"))
    cliente = OpenAI(timeout=60.0, max_retries=1)
    aciertos = {nombre: [0, 0] for nombre in ("local", "semantica", "hibrida")}
    positivas = 0
    for numero, caso in enumerate(casos, start=1):
        local = buscar_en_carpeta(args.carpeta, caso["question"])
        semantica, hibrida = buscar_con_embeddings(
            args.carpeta, caso["question"], cliente,
            usar_importaciones=not args.sin_importaciones,
        )
        print(f"{numero:02d} {caso['question']}")
        for nombre, resultados in (("local", local), ("semantica", semantica), ("hibrida", hibrida)):
            primero = resultados[0]["simbolo"] if resultados else "sin resultados"
            print(f"   {nombre}: {primero}")
            if caso["expected_symbol"] is not None:
                aciertos[nombre][0] += bool(resultados) and coincide(resultados[0], caso)
                aciertos[nombre][1] += any(coincide(f, caso) for f in resultados[:5])
        if caso["expected_symbol"] is not None:
            positivas += 1
    print(f"\nPreguntas con respuesta: {positivas}")
    for nombre, (top_1, top_5) in aciertos.items():
        print(f"{nombre}: primer lugar {top_1}/{positivas}, entre cinco {top_5}/{positivas}")
    print("Los resultados semánticos siempre contienen candidatos: aún no detectan ausencia de respuesta.")


if __name__ == "__main__":
    main()
