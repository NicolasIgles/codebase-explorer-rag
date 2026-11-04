"""Mide respuestas con evidencia y abstenciones del modo híbrido experimental."""

import argparse
import json
from pathlib import Path

from openai import OpenAI, OpenAIError

from evaluar import coincide
from semantica import buscar_con_embeddings
from validar_evidencia import responder_con_evidencia


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("carpeta")
    parser.add_argument("positivas")
    parser.add_argument("negativas", nargs="?", help="Opcional si el JSON de positivas incluye casos negativos")
    args = parser.parse_args()
    casos = json.loads(Path(args.positivas).read_text(encoding="utf-8"))
    positivas = [c for c in casos if c["expected_symbol"]]
    datos_negativos = json.loads(Path(args.negativas).read_text(encoding="utf-8")) if args.negativas else casos
    negativas = [
        caso["question"] if isinstance(caso, dict) else caso
        for caso in datos_negativos
        if not isinstance(caso, dict) or caso.get("expected_symbol") is None
    ]
    cliente = OpenAI(timeout=30.0, max_retries=1)
    fuente_correcta = respuestas_dadas = abstenciones = 0

    for numero, caso in enumerate(positivas, start=1):
        try:
            _, fragmentos = buscar_con_embeddings(args.carpeta, caso["question"], cliente)
            juicio = responder_con_evidencia(cliente, caso["question"], fragmentos)
        except (OpenAIError, ValueError) as error:
            print(f"P{numero:02d} error: {error}", flush=True)
            continue
        respuestas_dadas += juicio["hay_evidencia"]
        correcto = juicio["hay_evidencia"] and any(
            coincide(fragmentos[indice - 1], caso) for indice in juicio["fuentes"]
        )
        fuente_correcta += correcto
        print(f"P{numero:02d} responde={juicio['hay_evidencia']} fuente_correcta={correcto}: {caso['question']}", flush=True)

    for numero, pregunta in enumerate(negativas, start=1):
        try:
            _, fragmentos = buscar_con_embeddings(args.carpeta, pregunta, cliente)
            juicio = responder_con_evidencia(cliente, pregunta, fragmentos)
        except (OpenAIError, ValueError) as error:
            print(f"N{numero:02d} error: {error}", flush=True)
            continue
        abstenciones += not juicio["hay_evidencia"]
        print(f"N{numero:02d} abstiene={not juicio['hay_evidencia']}: {pregunta}", flush=True)

    print(f"\nRespuestas dadas: {respuestas_dadas}/{len(positivas)}")
    print(f"Respuestas con fuente esperada: {fuente_correcta}/{len(positivas)}")
    print(f"Abstenciones correctas: {abstenciones}/{len(negativas)}")


if __name__ == "__main__":
    main()
