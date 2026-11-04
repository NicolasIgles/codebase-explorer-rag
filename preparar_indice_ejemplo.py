"""Prepara una vez el índice del ejemplo fijo; nunca se ejecuta en Docker build."""

from api_http import CACHE_EJEMPLO, EJEMPLO
from semantica import ruta_cache, texto_para_embedding, vectores
from servicio_consultas import alcance_indexacion, cliente_openai, preparar_coleccion


def main():
    coleccion = preparar_coleccion(EJEMPLO, "completo")
    alcance = alcance_indexacion(coleccion)
    print(f'Ejemplo: {alcance["cantidad_fragmentos"]} fragmentos de {len(alcance["rutas"])} archivos')
    for ruta in alcance["rutas"]:
        print(f"  {ruta}")
    for ruta, motivo in sorted(alcance["excluidos"].items()):
        print(f"  Excluido: {ruta}: {motivo}")
    if not coleccion["fragmentos"]:
        print("No hay fragmentos permitidos para indexar.")
        return 1
    if input("Enviar el ejemplo permitido a OpenAI para embeddings? Escribí INDEXAR: ").strip() != "INDEXAR":
        print("Indexación cancelada.")
        return 0
    cliente = cliente_openai(timeout=60.0)
    textos = [texto_para_embedding(fragmento) for fragmento in coleccion["fragmentos"]]
    vectores(cliente, EJEMPLO, textos, CACHE_EJEMPLO, cache_key="ejemplo-v1")
    print(f"Índice preparado: {ruta_cache(EJEMPLO, CACHE_EJEMPLO, 'ejemplo-v1')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
