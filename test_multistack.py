"""Verifica extracción, recuperación y respuesta simulada para proyectos web."""

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import inicio
import ingesta_codigo as ingesta
import recuperacion_local as local
import servicio_consultas as servicio
from lenguajes_js import fragmentos_javascript


BASE = Path(__file__).parent
WEB = BASE / "sample_web_project"


class MultistackTest(unittest.TestCase):
    def test_extrae_componentes_rutas_interfaces_y_funciones(self):
        esperados = {
            "app/page.tsx": {"Page"},
            "app/api/tasks/route.ts": {"GET", "POST"},
            "components/TaskCard.jsx": {"TaskCard"},
            "lib/tasks.ts": {"Task", "listTasks", "saveTask"},
            "lib/format.js": {"formatTask"},
        }
        for relativo, simbolos in esperados.items():
            with self.subTest(archivo=relativo):
                ruta = WEB / relativo
                fragmentos = ingesta.fragmentos_de_archivo(ruta, WEB)
                self.assertTrue(simbolos <= {f["simbolo"] for f in fragmentos})
                self.assertTrue(all(f["inicio"] <= f["fin"] for f in fragmentos))
                self.assertTrue(all(f["ruta"] == relativo for f in fragmentos))

    def test_busca_simbolos_de_varios_lenguajes(self):
        casos = [
            ("Which route handles POST task requests?", "POST", "app/api/tasks/route.ts"),
            ("Which React component displays a task card?", "TaskCard", "components/TaskCard.jsx"),
            ("Which function formats a task?", "formatTask", "lib/format.js"),
        ]
        for pregunta, simbolo, ruta in casos:
            with self.subTest(pregunta=pregunta):
                resultados = local.buscar_en_carpeta(WEB, pregunta)
                self.assertTrue(any(f["simbolo"] == simbolo and f["ruta"] == ruta for f in resultados))

    def test_funcion_javascript_larga_respeta_las_lineas_del_archivo(self):
        codigo = "export function larga() {\n" + "  ejecutar();\n" * 250 + "}\n"
        fragmentos = fragmentos_javascript(codigo, WEB / "lib" / "larga.js", WEB)
        tramos = [f for f in fragmentos if f["simbolo"] == "larga"]
        self.assertEqual(len(tramos), 3)
        self.assertTrue(all(1 <= f["inicio"] <= f["fin"] <= len(codigo.splitlines()) for f in tramos))

    def test_envia_fuentes_web_al_modelo_con_citas(self):
        salida = io.StringIO()
        respuesta = json.dumps({"hay_evidencia": True, "respuesta": "La función formatTask formatea la tarea.", "fuentes": [1]})
        cliente = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(output_text=respuesta)))
        with (
            patch("builtins.input", side_effect=[str(WEB), "Which function formats a task?", "ENVIAR"]),
            patch.dict(os.environ, {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(servicio, "OpenAI", return_value=cliente),
            patch.object(cliente.responses, "create", wraps=cliente.responses.create) as crear,
            redirect_stdout(salida),
        ):
            self.assertEqual(inicio.main("acotado"), 0)
        crear.assert_called_once()
        mensaje = crear.call_args.kwargs["input"]
        self.assertIn("lib/format.js:1-3 (formatTask)", mensaje)
        self.assertIn("1: export function formatTask", mensaje)
        self.assertIn("Respuesta: La función formatTask formatea la tarea. [1]", salida.getvalue())

    def test_limita_a_cinco_fuentes_enviadas(self):
        fragmentos = [
            {"ruta": f"lib/fuente_{n}.ts", "inicio": 1, "fin": 1,
             "simbolo": f"fuente_{n}", "contenedor": "", "codigo": f"1: export const fuente_{n} = {n};"}
            for n in range(1, 7)
        ]
        respuesta = json.dumps({"hay_evidencia": True, "respuesta": "Respuesta", "fuentes": [1]})
        cliente = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(output_text=respuesta)))
        with (
            patch("builtins.input", side_effect=[str(WEB), "pregunta", "ENVIAR"]),
            patch.dict(os.environ, {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(inicio, "preparar_coleccion", return_value={
                "carpeta": WEB, "modo": "acotado", "fragmentos": fragmentos,
                "excluidos": {}, "avisos": [],
            }),
            patch.object(servicio, "ordenar_fragmentos", return_value=fragmentos),
            patch.object(servicio, "OpenAI", return_value=cliente),
            patch.object(cliente.responses, "create", wraps=cliente.responses.create) as crear,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(inicio.main("acotado"), 0)
        mensaje = crear.call_args.kwargs["input"]
        self.assertIn("fuente_5", mensaje)
        self.assertNotIn("fuente_6", mensaje)


if __name__ == "__main__":
    unittest.main()
