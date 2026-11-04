"""Contratos de privacidad y reutilización de la colección, sin llamadas reales a la API."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import semantica
import servicio_consultas as servicio


EJEMPLO = Path(__file__).parent / "sample_project"


def fuente(ruta, simbolo, codigo):
    return {
        "ruta": ruta, "inicio": 1, "fin": 1, "simbolo": simbolo,
        "contenedor": "", "tipo": "funcion", "descripcion": "",
        "codigo": codigo, "llamadas": [], "metodos_llamados": [],
        "atributos_llamados": [],
    }


class ServicioConsultasTest(unittest.TestCase):
    def test_acotado_exige_enviar_en_cada_operacion_externa(self):
        coleccion = servicio.preparar_coleccion(EJEMPLO, "acotado")
        fuentes = servicio.recuperar_fuentes(
            coleccion, "¿Quién puede editar una tarea?"
        )["fuentes"]
        self.assertTrue(fuentes)
        cliente = Mock()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}):
            with self.assertRaises(PermissionError):
                servicio.traducir_pregunta(coleccion, "¿Dónde está?", cliente=cliente)
            with self.assertRaises(PermissionError):
                servicio.generar_respuesta(
                    coleccion, "¿Quién puede editar una tarea?", fuentes, cliente=cliente
                )
            cliente.responses.create.assert_not_called()
            cliente.responses.create.return_value.output_text = json.dumps({
                "hay_evidencia": True, "respuesta": "can_edit_task", "fuentes": [1],
            })
            respuesta = servicio.generar_respuesta(
                coleccion, "¿Quién puede editar una tarea?", fuentes, "ENVIAR", cliente
            )
        self.assertTrue(respuesta["juicio"]["hay_evidencia"])
        cliente.responses.create.assert_called_once()

    def test_completo_exige_indexar_para_embedding_y_respuesta(self):
        coleccion = servicio.preparar_coleccion(EJEMPLO, "completo")
        cliente = Mock()
        fuente_primera = coleccion["fragmentos"][0]
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(
                servicio, "buscar_con_embeddings", return_value=([], [fuente_primera])
            ) as buscar,
        ):
            with self.assertRaises(PermissionError):
                servicio.recuperar_fuentes(coleccion, "pregunta", cliente=cliente)
            buscar.assert_not_called()
            resultado = servicio.recuperar_fuentes(
                coleccion, "pregunta", "INDEXAR", cliente
            )
            self.assertEqual(resultado["fuentes"], [fuente_primera])
            self.assertIs(buscar.call_args.kwargs["fragmentos"], coleccion["fragmentos"])
            with self.assertRaises(PermissionError):
                servicio.generar_respuesta(
                    coleccion, "pregunta", resultado["fuentes"], cliente=cliente
                )
            cliente.responses.create.assert_not_called()
            cliente.responses.create.return_value.output_text = json.dumps({
                "hay_evidencia": False, "respuesta": "", "fuentes": [],
            })
            servicio.generar_respuesta(
                coleccion, "pregunta", resultado["fuentes"], "INDEXAR", cliente
            )
            cliente.responses.create.assert_called_once()

    def test_acotado_excluye_archivo_sensible_antes_de_recuperar(self):
        publico = fuente("publico.py", "guardar", "1: def guardar(): pass")
        secreto = fuente(
            "config.py", "api_key", "1: api_key = 'sk-12345678901234567890'"
        )
        with patch.object(servicio, "obtener_fragmentos", return_value=[publico, secreto]):
            coleccion = servicio.preparar_coleccion(EJEMPLO, "acotado")
        self.assertEqual(coleccion["fragmentos"], [publico])
        self.assertIn("config.py", coleccion["excluidos"])
        cliente = Mock()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}):
            with self.assertRaises(ValueError):
                servicio.generar_respuesta(
                    coleccion, "pregunta", [secreto], "ENVIAR", cliente
                )
        cliente.responses.create.assert_not_called()

    def test_semantica_combina_solo_la_coleccion_recibida(self):
        permitido = fuente("publico.py", "guardar", "1: def guardar(): pass")
        cliente = Mock()
        with (
            patch.object(
                semantica, "obtener_fragmentos",
                side_effect=AssertionError("No debe volver a leer la carpeta"),
            ),
            patch.object(semantica, "vectores", return_value=[[1, 0], [1, 0]]),
            patch.object(semantica, "ordenar_fragmentos", return_value=[]) as ordenar,
        ):
            semantica.buscar_con_embeddings(
                EJEMPLO, "guardar", cliente, fragmentos=[permitido]
            )
        self.assertEqual(ordenar.call_args.args[0], [permitido])


    def test_respuesta_usa_codigo_original_aunque_cambie_la_fuente_recibida(self):
        coleccion = servicio.preparar_coleccion(EJEMPLO, "acotado")
        original = coleccion["fragmentos"][0]
        alterada = dict(original, codigo="1: código cambiado")
        cliente = Mock()
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(
                servicio, "responder_con_evidencia",
                return_value={"hay_evidencia": False, "respuesta": "", "fuentes": []},
            ) as responder,
        ):
            servicio.generar_respuesta(
                coleccion, "pregunta", [alterada], "ENVIAR", cliente
            )
        self.assertEqual(responder.call_args.args[2][0]["codigo"], original["codigo"])


if __name__ == "__main__":
    unittest.main()
