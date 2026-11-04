"""Evalúa recuperación en un proyecto separado del ejemplo público."""

import argparse
import json
import os
import time
from pathlib import Path

from openai import OpenAI

from ingesta_fuentes import obtener_fragmentos
from recuperacion_local import ordenar_fragmentos
from semantica import buscar_con_embeddings
from servicio_consultas import generar_respuesta, preparar_coleccion


RAIZ = Path(__file__).resolve().parent
PROYECTO = RAIZ / "eval_heldout"
CASOS = PROYECTO / "casos.json"
CACHE_EVAL = PROYECTO / "index"


def identidad(fragmento):
    return f"{fragmento['ruta']}:{fragmento['simbolo']}"


def evaluar_lista(casos, resultados):
    filas = []
    for caso, (fuentes, segundos) in zip(casos, resultados):
        encontradas = [identidad(f) for f in fuentes]
        esperadas = set(caso["esperadas"])
        filas.append({
            "id": caso["id"], "pregunta": caso["pregunta"],
            "esperadas": sorted(esperadas), "recuperadas": encontradas,
            "acierto_primera": bool(encontradas and encontradas[0] in esperadas),
            "cobertura_cinco": bool(esperadas and esperadas.issubset(encontradas[:5])),
            "abstencion_sin_fuentes": not encontradas,
            "segundos": round(segundos, 5),
        })
    positivos = [fila for fila in filas if fila["esperadas"]]
    negativos = [fila for fila in filas if not fila["esperadas"]]
    return {
        "casos": filas,
        "resumen": {
            "positivos": len(positivos), "negativos": len(negativos),
            "acierto_primera": sum(f["acierto_primera"] for f in positivos),
            "cobertura_cinco": sum(f["cobertura_cinco"] for f in positivos),
            "negativos_sin_fuentes": sum(f["abstencion_sin_fuentes"] for f in negativos),
            "latencia_media_ms": round(1000 * sum(f["segundos"] for f in filas) / len(filas), 2),
        },
    }


class ClienteMedido:
    def __init__(self):
        self.cliente = OpenAI(timeout=60.0, max_retries=1)
        self.embeddings = self
        self.tokens = 0
        self.peticiones = 0

    def create(self, **parametros):
        respuesta = self.cliente.embeddings.create(**parametros)
        self.peticiones += 1
        self.tokens += getattr(getattr(respuesta, "usage", None), "total_tokens", 0) or 0
        return respuesta


class ClienteRespuestasMedido:
    def __init__(self):
        self.cliente = OpenAI(timeout=30.0, max_retries=1)
        self.responses = self
        self.peticiones = 0
        self.tokens_entrada = 0
        self.tokens_salida = 0

    def create(self, **parametros):
        respuesta = self.cliente.responses.create(**parametros)
        self.peticiones += 1
        uso = getattr(respuesta, "usage", None)
        self.tokens_entrada += getattr(uso, "input_tokens", 0) or 0
        self.tokens_salida += getattr(uso, "output_tokens", 0) or 0
        return respuesta


def evaluar_respuestas(casos, informe, fragmentos):
    cliente = ClienteRespuestasMedido()
    por_identidad = {identidad(f): f for f in fragmentos}
    resultados = {}
    for metodo, modo, permiso in (
        ("lexica", "acotado", "ENVIAR"),
        ("hibrida", "completo", "INDEXAR"),
    ):
        coleccion = preparar_coleccion(PROYECTO, modo)
        filas = []
        for caso, recuperacion in zip(casos, informe["metodos"][metodo]["casos"]):
            fuentes = [por_identidad[clave] for clave in recuperacion["recuperadas"]]
            resultado = generar_respuesta(
                coleccion, caso["pregunta"], fuentes, permiso, cliente
            )
            juicio = resultado["juicio"]
            citadas = [identidad(fuentes[numero - 1]) for numero in juicio["fuentes"]]
            filas.append({
                "id": caso["id"], "negativo": caso["negativo"],
                "respondio": juicio["hay_evidencia"], "respuesta": juicio["respuesta"],
                "fuentes_citadas": citadas,
                "cita_fuente_esperada": bool(set(citadas) & set(caso["esperadas"])),
                "segundos": round(resultado["segundos"], 3),
            })
            print(metodo, caso["id"], "respuesta" if juicio["hay_evidencia"] else "abstencion", flush=True)
        positivas = [fila for fila in filas if not fila["negativo"]]
        negativas = [fila for fila in filas if fila["negativo"]]
        resultados[metodo] = {
            "casos": filas,
            "resumen": {
                "positivas_respondidas": sum(f["respondio"] for f in positivas),
                "positivas_con_cita_esperada": sum(f["respondio"] and f["cita_fuente_esperada"] for f in positivas),
                "negativas_abstenidas": sum(not f["respondio"] for f in negativas),
                "latencia_media_modelo_s": round(sum(f["segundos"] for f in filas) / len(filas), 3),
            },
        }
    return resultados, {
        "peticiones_respuestas": cliente.peticiones,
        "tokens_entrada": cliente.tokens_entrada,
        "tokens_salida": cliente.tokens_salida,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--todos", action="store_true", help="Compara léxica, semántica e híbrida")
    parser.add_argument("--autorizar-indexar", action="store_true",
                        help="Confirma el envío del proyecto y las preguntas a OpenAI")
    parser.add_argument("--respuestas", action="store_true",
                        help="Evalúa respuesta y abstención con las fuentes guardadas")
    parser.add_argument("--autorizar-responder", action="store_true",
                        help="Confirma el envío de preguntas y hasta cinco fuentes a OpenAI")
    parser.add_argument("--salida", type=Path, default=RAIZ / "evaluacion_holdout.json")
    args = parser.parse_args()
    if args.todos and (not args.autorizar_indexar or not os.getenv("OPENAI_API_KEY")):
        parser.error("--todos exige --autorizar-indexar y OPENAI_API_KEY")
    if args.respuestas and (not args.autorizar_responder or not os.getenv("OPENAI_API_KEY")):
        parser.error("--respuestas exige --autorizar-responder y OPENAI_API_KEY")
    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    fragmentos = obtener_fragmentos(PROYECTO, coleccion_id="evaluacion-holdout")
    resultados = []
    for caso in casos:
        inicio = time.perf_counter()
        fuentes = ordenar_fragmentos(fragmentos, caso["pregunta"])
        resultados.append((fuentes, time.perf_counter() - inicio))
    informe = {
        "proyecto": "eval_heldout", "cantidad_fragmentos": len(fragmentos),
        "metodos": {"lexica": evaluar_lista(casos, resultados)},
        "limites": "Muestra pequeña de un proyecto sintético. Una cita no verifica por sí sola la respuesta.",
    }
    if args.todos:
        cliente = ClienteMedido()
        semanticos, hibridos = [], []
        for caso in casos:
            inicio = time.perf_counter()
            sem, hib = buscar_con_embeddings(
                PROYECTO, caso["pregunta"], cliente, cache_dir=CACHE_EVAL,
                fragmentos=fragmentos, guardar_pregunta=False, cache_key="holdout-v1",
            )
            segundos = time.perf_counter() - inicio
            semanticos.append((sem, segundos))
            hibridos.append((hib, segundos))
        informe["metodos"]["semantica"] = evaluar_lista(casos, semanticos)
        informe["metodos"]["hibrida"] = evaluar_lista(casos, hibridos)
        informe["api"] = {"peticiones_embeddings": cliente.peticiones,
                          "tokens_embeddings": cliente.tokens}
    elif args.respuestas:
        anterior = json.loads(args.salida.read_text(encoding="utf-8"))
        if "hibrida" not in anterior.get("metodos", {}):
            parser.error("Primero ejecutá --todos para guardar la recuperación híbrida")
        informe = anterior
    if args.respuestas:
        respuestas, uso = evaluar_respuestas(casos, informe, fragmentos)
        informe["respuestas"] = respuestas
        informe.setdefault("api", {}).update(uso)
        informe["revision_manual"] = "Pendiente: las citas existentes no prueban la verdad de cada afirmación."
    args.salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    for nombre, datos in informe["metodos"].items():
        print(nombre, datos["resumen"])
    print("Informe:", args.salida)


if __name__ == "__main__":
    main()
