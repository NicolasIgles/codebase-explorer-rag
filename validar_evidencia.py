"""Respuesta estructurada que exige un juicio explícito y fuentes válidas."""

import json

from fragmentos import lugar


FORMATO = {
    "type": "json_schema",
    "name": "respuesta_con_evidencia",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "hay_evidencia": {"type": "boolean"},
            "respuesta": {"type": "string"},
            "fuentes": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["hay_evidencia", "respuesta", "fuentes"],
        "additionalProperties": False,
    },
}


def preparar_consulta(pregunta, fragmentos):
    fuentes = []
    for numero, fragmento in enumerate(fragmentos, start=1):
        nombre = ".".join(filter(None, (fragmento["contenedor"], fragmento["simbolo"])))
        ubicacion = lugar(fragmento)
        fuentes.append(f'[{numero}] {ubicacion} ({nombre})\n{fragmento["codigo"]}')
    return f"Pregunta: {pregunta}\n\nFuentes:\n" + "\n\n".join(fuentes)


def interpretar_respuesta(texto, cantidad_fuentes):
    try:
        datos = json.loads(texto)
    except (TypeError, ValueError) as error:
        raise ValueError("El modelo no devolvió JSON válido.") from error
    if not isinstance(datos, dict) or set(datos) != {"hay_evidencia", "respuesta", "fuentes"}:
        raise ValueError("La respuesta no tiene los campos esperados.")
    evidencia = datos["hay_evidencia"]
    respuesta = datos["respuesta"]
    fuentes = datos["fuentes"]
    if type(evidencia) is not bool or not isinstance(respuesta, str) or not isinstance(fuentes, list):
        raise ValueError("La respuesta tiene tipos inválidos.")
    if any(type(numero) is not int or numero < 1 or numero > cantidad_fuentes for numero in fuentes):
        raise ValueError("La respuesta menciona fuentes inexistentes.")
    if evidencia and (not respuesta.strip() or not fuentes):
        raise ValueError("Falta la respuesta o una fuente que la respalde.")
    if not evidencia and (respuesta.strip() or fuentes):
        raise ValueError("Una respuesta sin evidencia debe estar vacía.")
    return {"hay_evidencia": evidencia, "respuesta": respuesta.strip(), "fuentes": list(dict.fromkeys(fuentes))}


def responder_con_evidencia(cliente, pregunta, fragmentos, antes_envio=None):
    if not fragmentos:
        return {"hay_evidencia": False, "respuesta": "", "fuentes": []}
    if antes_envio:
        antes_envio()
    respuesta = cliente.responses.create(
        model="gpt-6-luna",
        store=False,
        instructions=(
            "Decidí si alguno de los fragmentos realmente contiene evidencia para responder. "
            "Un nombre parecido no alcanza. Si hay evidencia, respondé en español de forma breve "
            "y poné en fuentes solo los números que respaldan la respuesta; no agregues citas al texto. "
            "Si no hay evidencia suficiente, usá hay_evidencia=false, respuesta vacía y fuentes vacías. "
            "No inventes comportamiento que no figure en los fragmentos."
        ),
        input=preparar_consulta(pregunta, fragmentos),
        text={"format": FORMATO},
    )
    return interpretar_respuesta(respuesta.output_text, len(fragmentos))
