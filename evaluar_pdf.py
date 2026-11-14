"""Evalúa la recuperación léxica sobre PDFs (por ejemplo, currículums).

Cada PDF se prepara como una colección propia, igual que una carga de "Mis archivos" en modo acotado,
y cada pregunta se busca con ordenar_fragmentos. Un acierto es que un fragmento devuelto contenga alguno
de los textos esperados; se comparan sin espacios ni mayúsculas para tolerar cortes de línea del PDF.
Los casos con "esperado": [] son negativos: lo correcto es no devolver fragmentos.

Uso:
  python evaluar_pdf.py                       # CVs sintéticos de eval_pdf/cvs
  python evaluar_pdf.py --detalle             # muestra términos y fragmentos de cada fallo
  python evaluar_pdf.py --cvs mis_pdfs --casos mis_casos.json   # tus propios PDFs
"""

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

from recuperacion_local import MAX_FUENTES, ordenar_fragmentos, separar_palabras
from servicio_consultas import preparar_coleccion


RAIZ = Path(__file__).resolve().parent / "eval_pdf"


def compacto(texto):
    return re.sub(r"\s+", "", texto).lower()


def contiene(fragmento, esperados):
    texto = compacto(fragmento["texto"])
    return any(compacto(esperado) in texto for esperado in esperados)


def colecciones(carpeta_cvs, archivos):
    """Prepara cada PDF solo, como lo haría la API con una carga de un archivo."""
    resultado = {}
    for nombre in sorted(archivos):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(Path(carpeta_cvs) / nombre, Path(tmp) / nombre)
            resultado[nombre] = preparar_coleccion(tmp, "acotado")
    return resultado


def evaluar(casos, preparadas, limite=MAX_FUENTES):
    filas = []
    for caso in casos:
        fragmentos = preparadas[caso["archivo"]]["fragmentos"]
        fuentes = ordenar_fragmentos(fragmentos, caso["pregunta"], limite)
        posiciones = [i for i, f in enumerate(fuentes, 1) if caso["esperado"] and contiene(f, caso["esperado"])]
        en_coleccion = not caso["esperado"] or any(contiene(f, caso["esperado"]) for f in fragmentos)
        filas.append({
            "id": caso["id"], "archivo": caso["archivo"], "pregunta": caso["pregunta"],
            "negativo": not caso["esperado"],
            "terminos": list(dict.fromkeys(separar_palabras(caso["pregunta"]))),
            "posicion": posiciones[0] if posiciones else None,
            "devueltos": len(fuentes),
            "esperado_extraido": en_coleccion,
            "fuentes": fuentes,
        })
    return filas


def resumen(filas, preparadas):
    positivos = [f for f in filas if not f["negativo"]]
    negativos = [f for f in filas if f["negativo"]]
    return {
        "fragmentos_por_pdf": {n: len(c["fragmentos"]) for n, c in preparadas.items()},
        "positivos": len(positivos),
        "acierto_1": sum(f["posicion"] == 1 for f in positivos),
        "acierto_3": sum(bool(f["posicion"]) and f["posicion"] <= 3 for f in positivos),
        "acierto_5": sum(bool(f["posicion"]) for f in positivos),
        "sin_resultados": sum(f["devueltos"] == 0 for f in positivos),
        "esperado_no_extraido": sum(not f["esperado_extraido"] for f in positivos),
        "negativos": len(negativos),
        "negativos_sin_fuentes": sum(f["devueltos"] == 0 for f in negativos),
    }


def imprimir(filas, datos, detalle=False):
    print(f"{'caso':22} {'pos':>4} {'dev':>4}  pregunta")
    for f in filas:
        if f["negativo"]:
            marca = "ok" if f["devueltos"] == 0 else "FP"
        else:
            marca = str(f["posicion"]) if f["posicion"] else ("—" if f["devueltos"] else "vacío")
        print(f"{f['id']:22} {marca:>4} {f['devueltos']:>4}  {f['pregunta']}")
        fallo = (f["negativo"] and f["devueltos"]) or (not f["negativo"] and f["posicion"] != 1)
        if detalle and fallo:
            print(f"{'':28}términos: {f['terminos']}"
                  + ("" if f["esperado_extraido"] else "  [el texto esperado no está en ningún fragmento]"))
            for i, fuente in enumerate(f["fuentes"][:3], 1):
                muestra = " ".join(fuente["texto"].split())[:110]
                print(f"{'':28}{i}. {fuente['puntuacion']:.1f}  {muestra}")
    print()
    print(json.dumps(datos, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cvs", default=RAIZ / "cvs", type=Path)
    parser.add_argument("--casos", default=RAIZ / "casos.json", type=Path)
    parser.add_argument("--detalle", action="store_true")
    parser.add_argument("--json", type=Path, help="Guarda el resultado completo en este archivo")
    args = parser.parse_args()

    casos = json.loads(args.casos.read_text(encoding="utf-8"))
    preparadas = colecciones(args.cvs, {caso["archivo"] for caso in casos})
    filas = evaluar(casos, preparadas)
    datos = resumen(filas, preparadas)
    imprimir(filas, datos, args.detalle)
    if args.json:
        salida = [{k: v for k, v in f.items() if k != "fuentes"} for f in filas]
        args.json.write_text(json.dumps({"resumen": datos, "casos": salida}, ensure_ascii=False, indent=2),
                             encoding="utf-8")


if __name__ == "__main__":
    main()
