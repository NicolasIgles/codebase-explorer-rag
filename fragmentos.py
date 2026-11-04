"""Contrato común de fuentes para código y documentos."""

from uuid import uuid4


def normalizar(fragmento, coleccion_id=None):
    """Completa campos comunes sin quitar claves usadas por la CLI existente."""
    resultado = dict(fragmento)
    resultado["coleccion_id"] = coleccion_id or resultado.get("coleccion_id") or uuid4().hex
    resultado.setdefault("tipo_fuente", "documento" if resultado.get("tipo") == "documento" else "codigo")
    resultado.setdefault("titulo", resultado.get("simbolo", ""))
    resultado.setdefault("texto", resultado.get("codigo", ""))
    resultado.setdefault("metadatos", {})
    if "ubicacion" not in resultado:
        if resultado.get("pagina") is not None:
            resultado["ubicacion"] = {
                "tipo": "pagina",
                "pagina": resultado["pagina"],
                "inicio": resultado.get("inicio"),
                "fin": resultado.get("fin"),
            }
        else:
            resultado["ubicacion"] = {
                "tipo": "lineas",
                "inicio": resultado.get("inicio"),
                "fin": resultado.get("fin"),
            }
    return resultado


def lugar(fragmento):
    ubicacion = fragmento.get("ubicacion") or {}
    if ubicacion.get("tipo") == "pagina":
        lugar_base = f'{fragmento["ruta"]}:página {ubicacion["pagina"]}'
    else:
        lugar_base = f'{fragmento["ruta"]}:{fragmento["inicio"]}-{fragmento["fin"]}'
    if ubicacion.get("columna_inicio") is not None:
        return f'{lugar_base}:columnas {ubicacion["columna_inicio"]}-{ubicacion["columna_fin"]}'
    return lugar_base


def identidad(fragmento):
    ubicacion = fragmento.get("ubicacion") or {}
    return (
        fragmento["ruta"],
        ubicacion.get("pagina"),
        ubicacion.get("columna_inicio"),
        ubicacion.get("columna_fin"),
        fragmento["inicio"],
        fragmento["fin"],
        fragmento.get("contenedor", ""),
        fragmento["simbolo"],
    )


def se_superponen(uno, otro):
    if uno["ruta"] != otro["ruta"]:
        return False
    ubicacion_uno = uno.get("ubicacion") or {}
    ubicacion_otro = otro.get("ubicacion") or {}
    if (ubicacion_uno.get("pagina") is not None and
            ubicacion_otro.get("pagina") is not None and
            ubicacion_uno["pagina"] != ubicacion_otro["pagina"]):
        return False
    if uno["inicio"] > otro["fin"] or otro["inicio"] > uno["fin"]:
        return False
    columna_uno = ubicacion_uno.get("columna_inicio")
    columna_otro = ubicacion_otro.get("columna_inicio")
    if columna_uno is not None and columna_otro is not None:
        return not (ubicacion_uno["columna_fin"] < columna_otro or
                    ubicacion_otro["columna_fin"] < columna_uno)
    return True
