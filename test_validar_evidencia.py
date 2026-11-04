"""Validación de la estructura recibida del modelo, sin usar la API."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from validar_evidencia import interpretar_respuesta, responder_con_evidencia


class EvidenciaTest(unittest.TestCase):
    def test_acepta_respuesta_con_fuente_existente(self):
        resultado = interpretar_respuesta(
            '{"hay_evidencia":true,"respuesta":"Se usa addTest.","fuentes":[1]}', 2
        )
        self.assertTrue(resultado["hay_evidencia"])
        self.assertEqual(resultado["fuentes"], [1])

    def test_acepta_abstencion_vacia(self):
        resultado = interpretar_respuesta(
            '{"hay_evidencia":false,"respuesta":"","fuentes":[]}', 2
        )
        self.assertFalse(resultado["hay_evidencia"])

    def test_rechaza_fuente_inexistente_o_sin_respaldo(self):
        for texto in (
            '{"hay_evidencia":true,"respuesta":"Algo.","fuentes":[9]}',
            '{"hay_evidencia":true,"respuesta":"Algo.","fuentes":[]}',
            '{"hay_evidencia":false,"respuesta":"Algo.","fuentes":[]}',
        ):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                interpretar_respuesta(texto, 2)

    def test_sin_fragmentos_no_llama_a_api(self):
        cliente = Mock()
        self.assertFalse(responder_con_evidencia(cliente, "pregunta", [])["hay_evidencia"])
        cliente.responses.create.assert_not_called()

    def test_consulta_estructurada_usa_fuentes(self):
        cliente = Mock()
        cliente.responses.create.return_value = SimpleNamespace(
            output_text='{"hay_evidencia":true,"respuesta":"Sí.","fuentes":[1]}'
        )
        fuente = {"ruta":"a.py","inicio":1,"fin":2,"contenedor":"A","simbolo":"f","codigo":"1: def f():\n2:     pass"}
        resultado = responder_con_evidencia(cliente, "¿Dónde?", [fuente])
        self.assertTrue(resultado["hay_evidencia"])
        self.assertIn("a.py:1-2", cliente.responses.create.call_args.kwargs["input"])


if __name__ == "__main__":
    unittest.main()
