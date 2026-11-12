"""Pruebas locales de la búsqueda; no llaman a OpenAI."""

import ast
import io
import json
import stat
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import inicio
import ingesta_codigo as ingesta
import recuperacion_local as local
import servicio_consultas as servicio
from privacidad import motivo_exclusion
from validar_evidencia import preparar_consulta


BASE = Path(__file__).parent
EJEMPLO = BASE / "sample_project"


class BusquedaTest(unittest.TestCase):
    def test_filtro_remoto_excluye_archivos_sensibles_por_nombre(self):
        self.assertEqual(
            motivo_exclusion({"ruta": "config/credentials.prod.ts", "codigo": "export const value = 1"}),
            "nombre de archivo o carpeta sensible",
        )

    def test_modo_local_muestra_fuentes_sin_crear_cliente(self):
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "¿Quién puede editar una tarea?"]),
            patch.object(servicio, "OpenAI", side_effect=AssertionError("No debe llamar a OpenAI")),
            redirect_stdout(salida),
        ):
            self.assertEqual(inicio.main(), 0)
        self.assertIn("permissions.py", salida.getvalue())
        self.assertIn("Modo local", salida.getvalue())

    def test_modo_acotado_no_envia_fuentes_sin_confirmacion(self):
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "¿Quién puede editar una tarea?", "NO"]),
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(servicio, "OpenAI", side_effect=AssertionError("No debe llamar a OpenAI")),
            redirect_stdout(salida),
        ):
            self.assertEqual(inicio.main("acotado"), 0)
        self.assertIn("no se enviaron fragmentos", salida.getvalue())

    def test_modo_completo_muestra_alcance_y_puede_cancelarse_sin_api(self):
        fuente = {
            "ruta": "permissions.py", "inicio": 1, "fin": 2,
            "simbolo": "can_edit_task", "contenedor": "", "descripcion": "",
            "codigo": "1: def can_edit_task():\n2:     return True",
        }
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "pregunta", "NO"]),
            patch("servicio_consultas.obtener_fragmentos", return_value=[fuente]),
            patch.object(servicio, "OpenAI", side_effect=AssertionError("No debe llamar a OpenAI")),
            redirect_stdout(salida),
        ):
            self.assertEqual(inicio.main("completo"), 0)
        self.assertIn("permissions.py", salida.getvalue())
        self.assertIn("no se envió código", salida.getvalue())

    def test_modo_completo_excluye_credenciales_antes_de_indexar(self):
        fuente = {
            "ruta": "permissions.py", "inicio": 1, "fin": 2,
            "simbolo": "can_edit_task", "contenedor": "", "descripcion": "",
            "codigo": "1: def can_edit_task():\n2:     return True",
        }
        secreto = {
            "ruta": "config.py", "inicio": 1, "fin": 1,
            "simbolo": "api_key", "contenedor": "", "descripcion": "",
            "codigo": "1: api_key = 'sk-12345678901234567890'",
        }
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "pregunta", "INDEXAR"]),
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.obtener_fragmentos", return_value=[fuente, secreto]),
            patch("servicio_consultas.buscar_con_embeddings", return_value=([], [fuente])) as buscar,
            patch.object(servicio, "OpenAI") as cliente,
            redirect_stdout(salida),
        ):
            cliente.return_value.responses.create.return_value.output_text = json.dumps({
                "hay_evidencia": True, "respuesta": "La función can_edit_task.", "fuentes": [1],
            })
            self.assertEqual(inicio.main("completo"), 0)
        self.assertEqual(buscar.call_args.kwargs["fragmentos"], [fuente])
        self.assertIn("config.py: posible credencial", salida.getvalue())
        self.assertTrue(cliente.return_value.responses.create.call_args.kwargs["store"] is False)

    def test_extrae_llamadas_a_metodos_de_un_bloque(self):
        arbol = ast.parse("signer.sign(value)\nsigner.unsign(value)\nsigner.unsign(value)")
        self.assertEqual(ingesta.nombres_atributos_llamados(arbol), ["sign", "unsign", "unsign"])

    def test_preguntas_con_ubicacion_conocida(self):
        preguntas = json.loads((BASE / "questions.json").read_text(encoding="utf-8"))
        for caso in preguntas:
            with self.subTest(pregunta=caso["question"]):
                resultados = local.buscar_en_carpeta(EJEMPLO, caso["question"])
                if caso["expected_symbol"] is None:
                    self.assertFalse(resultados)
                    continue
                self.assertTrue(resultados)
                self.assertEqual(resultados[0]["simbolo"], caso["expected_symbol"])
                self.assertEqual(Path(resultados[0]["ruta"]).name, caso["expected_file"])

    def test_fuente_contiene_definicion_y_condicion(self):
        fragmentos = ingesta.fragmentos_de_archivo(EJEMPLO / "permissions.py", EJEMPLO)
        funcion = next(f for f in fragmentos if f["simbolo"] == "can_edit_task")
        self.assertEqual((funcion["inicio"], funcion["fin"]), (4, 6))
        self.assertIn("4: def can_edit_task(", funcion["codigo"])
        self.assertIn("6:     return user.get(", funcion["codigo"])

    def test_busqueda_incluye_subcarpetas(self):
        rutas = {ruta.relative_to(BASE).as_posix() for ruta in ingesta.archivos_python(BASE)}
        self.assertIn("sample_project/permissions.py", rutas)
        self.assertFalse(any(".venv/" in ruta for ruta in rutas))

    def test_mensaje_incluye_pregunta_y_fuente_real(self):
        pregunta = "¿Quién puede editar una tarea?"
        fragmentos = local.buscar_en_carpeta(EJEMPLO, pregunta)
        mensaje = preparar_consulta(pregunta, fragmentos)
        self.assertIn(pregunta, mensaje)
        self.assertIn("[1] permissions.py:4-6", mensaje)
        self.assertIn("return user.get(\"role\")", mensaje)

    def test_sigue_funciones_llamadas_desde_la_solicitud(self):
        pregunta = "¿Qué ocurre al procesar una solicitud para completar una tarea?"
        resultados = local.buscar_en_carpeta(EJEMPLO, pregunta)
        self.assertEqual(resultados[0]["simbolo"], "complete_task_request")
        nombres = {fragmento["simbolo"] for fragmento in resultados}
        self.assertTrue({"load_task", "can_edit_task", "complete_task", "save_task"} <= nombres)

    def test_incluye_metodo_de_la_misma_clase_que_llama_al_primero(self):
        texto = (
            "class Inspector:\n"
            "    def verify_signature(self, signature):\n"
            "        \"\"\"Verify signature validity.\"\"\"\n"
            "        return signature == 'ok'\n"
            "\n"
            "    def unsign(self, signed):\n"
            "        if self.verify_signature(signed):\n"
            "            return signed\n"
        )
        ruta = EJEMPLO / "permissions.py"
        with (
            patch.object(ingesta, "archivos_codigo", return_value=iter([ruta])),
            patch.object(ingesta, "leer_archivo", return_value=texto),
        ):
            resultados = local.buscar_en_carpeta(
                EJEMPLO, "Which Inspector method verifies signature validity?"
            )
        self.assertEqual(resultados[0]["simbolo"], "verify_signature")
        self.assertIn("unsign", [fragmento["simbolo"] for fragmento in resultados])

    def test_usa_los_cinco_lugares_disponibles(self):
        texto = "\n".join(
            f'def option_{numero}():\n    """Handles shared operation."""\n    return {numero}\n'
            for numero in range(6)
        )
        ruta = EJEMPLO / "permissions.py"
        with (
            patch.object(ingesta, "archivos_codigo", return_value=iter([ruta])),
            patch.object(ingesta, "leer_archivo", return_value=texto),
        ):
            resultados = local.buscar_en_carpeta(EJEMPLO, "Where is shared operation handled?")
        self.assertEqual(len(resultados), 5)

    def test_sintaxis_invalida_usa_busqueda_textual_y_avisa(self):
        avisos = []
        with patch.object(ingesta, "leer_archivo", return_value="def roto(:\n    pass\n"):
            fragmentos = ingesta.fragmentos_de_archivo(EJEMPLO / "permissions.py", EJEMPLO, avisos)
        self.assertEqual(fragmentos[0]["simbolo"], "texto sin analizar")
        self.assertIn("1: def roto(:", fragmentos[0]["codigo"])
        self.assertTrue(any("sintaxis inválida" in aviso for aviso in avisos))

    def test_archivo_grande_se_omite_con_aviso(self):
        avisos = []
        tamano = SimpleNamespace(st_size=ingesta.MAX_BYTES_ARCHIVO + 1, st_mode=stat.S_IFREG)
        with patch.object(Path, "stat", return_value=tamano):
            fragmentos = ingesta.fragmentos_de_archivo(EJEMPLO / "permissions.py", EJEMPLO, avisos)
        self.assertEqual(fragmentos, [])
        self.assertTrue(any("superar" in aviso for aviso in avisos))

    def test_funcion_larga_conserva_el_tramo_final(self):
        texto = "def larga():\n" + "    valor = 1\n" * 110 + "    return valor\n"
        with patch.object(ingesta, "leer_archivo", return_value=texto):
            fragmentos = ingesta.fragmentos_de_archivo(EJEMPLO / "permissions.py", EJEMPLO)
        tramos = [f for f in fragmentos if f["simbolo"] == "larga"]
        self.assertEqual(len(tramos), 2)
        self.assertEqual((tramos[0]["inicio"], tramos[0]["fin"]), (1, 100))
        self.assertIn("return valor", tramos[1]["codigo"])

    def test_detecta_espanol_sin_afectar_preguntas_inglesas(self):
        self.assertTrue(local.parece_espanol("¿Dónde está la función?"))
        self.assertTrue(local.parece_espanol("Donde esta la funcion?"))
        self.assertFalse(local.parece_espanol("Which function handles a request?"))

    def test_traduccion_vacia_o_multilinea_se_descarta(self):
        cliente = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(output_text="")))
        coleccion = {"modo": "acotado"}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}):
            self.assertEqual(servicio.traducir_pregunta(coleccion, "¿Dónde está?", "ENVIAR", cliente), "")
        cliente.responses.create = lambda **kwargs: SimpleNamespace(output_text="Query\nExtra text")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}):
            self.assertEqual(servicio.traducir_pregunta(coleccion, "¿Dónde está?", "ENVIAR", cliente), "")

    def test_sin_evidencia_no_llama_al_modelo(self):
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "Where is a SQL database connection opened?"]),
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(servicio, "OpenAI", side_effect=AssertionError("No debe llamarse al modelo")),
            redirect_stdout(salida),
        ):
            resultado = inicio.main("acotado")
        self.assertEqual(resultado, 0)
        self.assertIn("No encontré código relacionado", salida.getvalue())

    def test_respaldo_ingles_recupera_fuente_y_responde(self):
        salida = io.StringIO()
        pregunta = "¿Qué función cuenta los encargos sin terminar?"
        traduccion = "Which function counts pending tasks?"
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), pregunta, "ENVIAR", "ENVIAR"]),
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(servicio, "OpenAI") as cliente,
            redirect_stdout(salida),
        ):
            cliente.return_value.responses.create.side_effect = [
                SimpleNamespace(output_text=traduccion),
                SimpleNamespace(output_text=json.dumps({
                    "hay_evidencia": True,
                    "respuesta": "La función es count_pending_tasks.",
                    "fuentes": [1],
                })),
            ]
            resultado = inicio.main("acotado")
        self.assertEqual(resultado, 0)
        self.assertEqual(cliente.return_value.responses.create.call_count, 2)
        self.assertEqual(cliente.return_value.responses.create.call_args_list[0].kwargs["input"], pregunta)
        self.assertIn("Consulta ampliada al inglés", salida.getvalue())
        self.assertIn("count_pending_tasks", salida.getvalue())

    def test_respaldo_no_inventa_fuentes(self):
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "¿Quién procesa una transferencia bancaria?", "ENVIAR"]),
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(servicio, "OpenAI") as cliente,
            redirect_stdout(salida),
        ):
            cliente.return_value.responses.create.return_value.output_text = "Who processes a bank transfer?"
            resultado = inicio.main("acotado")
        self.assertEqual(resultado, 0)
        self.assertEqual(cliente.return_value.responses.create.call_count, 1)
        self.assertIn("No encontré código relacionado", salida.getvalue())

    def test_respuesta_muestra_fuentes_con_un_cliente_simulado(self):
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "¿Qué condiciones permiten editar una tarea?", "ENVIAR"]),
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(servicio, "OpenAI") as cliente,
            redirect_stdout(salida),
        ):
            cliente.return_value.responses.create.return_value.output_text = json.dumps({
                "hay_evidencia": True,
                "respuesta": "Puede editarla un administrador o su responsable.",
                "fuentes": [1],
            })
            resultado = inicio.main("acotado")
        self.assertEqual(resultado, 0)
        cliente.return_value.responses.create.assert_called_once()
        self.assertIn("[1] permissions.py:4-6 (can_edit_task)", salida.getvalue())
        self.assertIn("Respuesta: Puede editarla", salida.getvalue())
        self.assertIn("responsable. [1]", salida.getvalue())

    def test_fuentes_irrelevantes_producen_abstencion(self):
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "Which task function sends email alerts?", "ENVIAR"]),
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(servicio, "ordenar_fragmentos", return_value=[
                next(f for f in ingesta.obtener_fragmentos(EJEMPLO) if f["simbolo"] == "create_task")
            ]),
            patch.object(servicio, "OpenAI") as cliente,
            redirect_stdout(salida),
        ):
            cliente.return_value.responses.create.return_value.output_text = json.dumps({
                "hay_evidencia": False, "respuesta": "", "fuentes": [],
            })
            self.assertEqual(inicio.main("acotado"), 0)
        self.assertIn("No encontré evidencia suficiente", salida.getvalue())

    def test_respuesta_con_fuente_inexistente_no_se_muestra(self):
        salida = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(EJEMPLO), "¿Quién puede editar una tarea?", "ENVIAR"]),
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch.object(servicio, "OpenAI") as cliente,
            redirect_stdout(salida),
        ):
            cliente.return_value.responses.create.return_value.output_text = json.dumps({
                "hay_evidencia": True, "respuesta": "Respuesta inventada", "fuentes": [99],
            })
            self.assertEqual(inicio.main("acotado"), 1)
        self.assertIn("No se pudo validar", salida.getvalue())
        self.assertNotIn("Respuesta: Respuesta inventada", salida.getvalue())


if __name__ == "__main__":
    unittest.main()
