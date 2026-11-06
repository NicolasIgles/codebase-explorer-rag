"""Pruebas HTTP con TestClient y clientes OpenAI simulados."""

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api_http import (
    CACHE_EJEMPLO, EJEMPLO as EJEMPLO_PUBLICO, ColeccionesTemporales,
    LimitesApi, LimitadorOpenAI, crear_app,
)


EJEMPLO = Path(__file__).parent / "sample_project"


def fuente(ruta, simbolo, codigo):
    return {
        "ruta": ruta, "inicio": 1, "fin": 1, "simbolo": simbolo,
        "contenedor": "", "tipo": "funcion", "descripcion": "",
        "codigo": codigo, "llamadas": [], "metodos_llamados": [],
        "atributos_llamados": [],
    }


class ApiHttpTest(unittest.TestCase):
    def setUp(self):
        self.cliente = TestClient(crear_app())

    def crear_coleccion(self, modo="local"):
        respuesta = self.cliente.post(
            "/ejemplo/colecciones", json={"modo": modo}
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        return respuesta.json()["coleccion_id"]

    def test_local_recupera_sin_api_y_permite_liberar_coleccion(self):
        with patch(
            "servicio_consultas.OpenAI",
            side_effect=AssertionError("El modo local no debe crear cliente"),
        ):
            coleccion_id = self.crear_coleccion()
            respuesta = self.cliente.post(
                f"/colecciones/{coleccion_id}/consultas",
                json={"pregunta": "¿Quién puede editar una tarea?"},
            )
            self.assertEqual(respuesta.status_code, 201, respuesta.text)
            datos = respuesta.json()
            self.assertEqual(datos["fuentes"][0]["simbolo"], "can_edit_task")
            denegada = self.cliente.post(
                f"/colecciones/{coleccion_id}/consultas/{datos['consulta_id']}/respuesta",
                json={"autorizacion": "ENVIAR"},
            )
            self.assertEqual(denegada.status_code, 403)
        self.assertEqual(
            self.cliente.delete(f"/colecciones/{coleccion_id}").status_code, 204
        )
        self.assertEqual(
            self.cliente.get(f"/colecciones/{coleccion_id}/alcance").status_code, 404
        )

    def test_acotado_exige_confirmacion_tras_mostrar_fuentes(self):
        coleccion_id = self.crear_coleccion("acotado")
        consulta = self.cliente.post(
            f"/colecciones/{coleccion_id}/consultas",
            json={"pregunta": "¿Quién puede editar una tarea?"},
        ).json()
        ruta = f"/colecciones/{coleccion_id}/consultas/{consulta['consulta_id']}/respuesta"
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.OpenAI") as modelo,
            patch(
                "servicio_consultas.responder_con_evidencia",
                return_value={
                    "hay_evidencia": True,
                    "respuesta": "Puede editarla un administrador.",
                    "fuentes": [1],
                },
            ) as responder,
        ):
            self.assertEqual(self.cliente.post(ruta, json={}).status_code, 403)
            modelo.assert_not_called()
            self.assertEqual(
                self.cliente.post(
                    ruta, json={"autorizacion": "ENVIAR", "fuentes": []}
                ).status_code, 422
            )
            respuesta = self.cliente.post(ruta, json={"autorizacion": "ENVIAR"})
            self.assertEqual(respuesta.status_code, 200, respuesta.text)
            self.assertEqual(respuesta.json()["citas"], [1])
            self.assertFalse(respuesta.json()["abstencion"])
            self.assertEqual(
                responder.call_args.args[2][0]["codigo"],
                consulta["fuentes"][0]["codigo"],
            )

    def test_completo_muestra_alcance_y_exige_indexar_dos_veces(self):
        publico = fuente("publico.py", "guardar", "1: def guardar(): pass")
        secreto = fuente(
            "config.py", "api_key", "1: api_key = 'sk-12345678901234567890'"
        )
        with patch(
            "servicio_consultas.obtener_fragmentos", return_value=[publico, secreto]
        ):
            creado = self.cliente.post(
                "/ejemplo/colecciones", json={"modo": "completo"}
            )
        self.assertEqual(creado.status_code, 201, creado.text)
        datos = creado.json()
        self.assertEqual(datos["alcance"]["rutas"], ["publico.py"])
        self.assertEqual(datos["alcance"]["carpeta"], "ejemplo")
        self.assertIn("config.py", datos["alcance"]["excluidos"])
        ruta = f"/colecciones/{datos['coleccion_id']}/consultas"
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.OpenAI") as modelo,
            patch(
                "servicio_consultas.buscar_con_embeddings",
                return_value=([publico], [publico]),
            ) as buscar,
            patch(
                "servicio_consultas.responder_con_evidencia",
                return_value={"hay_evidencia": False, "respuesta": "", "fuentes": []},
            ) as responder,
        ):
            self.assertEqual(
                self.cliente.post(ruta, json={"pregunta": "guardar"}).status_code, 403
            )
            modelo.assert_not_called()
            buscar.assert_not_called()
            consulta = self.cliente.post(
                ruta, json={"pregunta": "guardar", "autorizacion": "INDEXAR"}
            )
            self.assertEqual(consulta.status_code, 201, consulta.text)
            self.assertEqual(consulta.json()["fuentes"][0]["ruta"], "publico.py")
            respuesta_ruta = (
                f"{ruta}/{consulta.json()['consulta_id']}/respuesta"
            )
            self.assertEqual(
                self.cliente.post(respuesta_ruta, json={}).status_code, 403
            )
            responder.assert_not_called()
            respuesta = self.cliente.post(
                respuesta_ruta, json={"autorizacion": "INDEXAR"}
            )
            self.assertEqual(respuesta.status_code, 200, respuesta.text)
            self.assertTrue(respuesta.json()["abstencion"])
            self.assertEqual(responder.call_args.args[2], [publico])

    def test_traduccion_reutiliza_coleccion_y_pregunta_original(self):
        coleccion_id = self.crear_coleccion("acotado")
        pregunta = "¿Qué función cuenta los encargos sin terminar?"
        consulta = self.cliente.post(
            f"/colecciones/{coleccion_id}/consultas", json={"pregunta": pregunta}
        ).json()
        self.assertEqual(consulta["fuentes"], [])
        ruta = (
            f"/colecciones/{coleccion_id}/consultas/"
            f"{consulta['consulta_id']}/traduccion"
        )
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.OpenAI") as modelo,
        ):
            self.assertEqual(self.cliente.post(ruta, json={}).status_code, 403)
            modelo.assert_not_called()
            modelo.return_value.responses.create.return_value.output_text = (
                "Which function counts pending tasks?"
            )
            traducida = self.cliente.post(
                ruta, json={"autorizacion": "ENVIAR"}
            )
        self.assertEqual(traducida.status_code, 200, traducida.text)
        self.assertTrue(
            any(f["simbolo"] == "count_pending_tasks"
                for f in traducida.json()["fuentes"])
        )
        self.assertEqual(
            traducida.json()["consulta_ingles"],
            "Which function counts pending tasks?",
        )


    def test_respuesta_invalida_del_modelo_devuelve_502(self):
        coleccion_id = self.crear_coleccion("acotado")
        consulta = self.cliente.post(
            f"/colecciones/{coleccion_id}/consultas",
            json={"pregunta": "¿Quién puede editar una tarea?"},
        ).json()
        ruta = f"/colecciones/{coleccion_id}/consultas/{consulta['consulta_id']}/respuesta"
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.OpenAI"),
            patch(
                "servicio_consultas.responder_con_evidencia",
                side_effect=ValueError("El modelo no devolvió JSON válido."),
            ),
        ):
            respuesta = self.cliente.post(ruta, json={"autorizacion": "ENVIAR"})
        self.assertEqual(respuesta.status_code, 502)
        self.assertIn("JSON válido", respuesta.json()["detail"])


    def test_publico_rechaza_rutas_y_usa_solo_el_ejemplo_del_servidor(self):
        with patch("api_http.preparar_coleccion", wraps=__import__(
            "servicio_consultas"
        ).preparar_coleccion) as preparar:
            arbitraria = self.cliente.post(
                "/colecciones", json={"carpeta": "C:/Windows", "modo": "local"}
            )
            self.assertEqual(arbitraria.status_code, 404)
            inyectada = self.cliente.post(
                "/ejemplo/colecciones",
                json={"carpeta": "C:/Windows", "modo": "local"},
            )
            self.assertEqual(inyectada.status_code, 422)
            preparar.assert_not_called()
            permitida = self.cliente.post(
                "/ejemplo/colecciones", json={"modo": "local"}
            )
        self.assertEqual(permitida.status_code, 201)
        self.assertEqual(preparar.call_args.args[0], EJEMPLO_PUBLICO)
        consulta = self.cliente.post(
            f"/colecciones/{permitida.json()['coleccion_id']}/consultas",
            json={"pregunta": "¿Quién puede editar una tarea?"},
        )
        self.assertEqual(consulta.status_code, 201)
        self.assertEqual(consulta.json()["fuentes"][0]["simbolo"], "can_edit_task")

    def test_ruta_local_requiere_habilitacion_explicita(self):
        cliente = TestClient(crear_app(permitir_rutas_locales=True))
        respuesta = cliente.post(
            "/colecciones",
            json={"carpeta": str(Path(__file__).parent / "sample_web_project"),
                  "modo": "local"},
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        self.assertEqual(respuesta.json()["origen"], "local_desarrollo")

    def test_limites_de_pregunta_y_consultas_rechazan_antes_de_recuperar(self):
        cliente = TestClient(crear_app(
            limites=LimitesApi(caracteres_pregunta=12, consultas_coleccion=1)
        ))
        creado = cliente.post("/ejemplo/colecciones", json={"modo": "local"})
        coleccion_id = creado.json()["coleccion_id"]
        ruta = f"/colecciones/{coleccion_id}/consultas"
        with patch(
            "api_http.recuperar_fuentes",
            side_effect=AssertionError("No debe buscar"),
        ) as buscar:
            larga = cliente.post(ruta, json={"pregunta": "x" * 13})
            self.assertEqual(larga.status_code, 413)
            buscar.assert_not_called()
        primera = cliente.post(ruta, json={"pregunta": "editar tarea"})
        self.assertEqual(primera.status_code, 201, primera.text)
        with patch(
            "api_http.recuperar_fuentes",
            side_effect=AssertionError("No debe buscar"),
        ) as buscar:
            exceso = cliente.post(ruta, json={"pregunta": "otra tarea"})
            self.assertEqual(exceso.status_code, 429)
            buscar.assert_not_called()

    def test_limite_de_colecciones_rechaza_antes_de_leer_archivos(self):
        cliente = TestClient(crear_app(
            limites=LimitesApi(colecciones_activas=1)
        ))
        primera = cliente.post("/ejemplo/colecciones", json={"modo": "local"})
        self.assertEqual(primera.status_code, 201)
        with patch(
            "api_http.preparar_coleccion",
            side_effect=AssertionError("No debe leer archivos"),
        ) as preparar:
            segunda = cliente.post("/ejemplo/colecciones", json={"modo": "local"})
            self.assertEqual(segunda.status_code, 429)
            preparar.assert_not_called()

    def test_rafaga_se_rechaza_antes_del_modelo_y_se_renueva(self):
        class Reloj:
            instante = 0.0

            def __call__(self):
                return self.instante

        reloj = Reloj()
        cliente = TestClient(crear_app(
            limites=LimitesApi(peticiones_origen=2, ventana_segundos=60),
            reloj=reloj,
        ))
        creado = cliente.post("/ejemplo/colecciones", json={"modo": "acotado"})
        coleccion_id = creado.json()["coleccion_id"]
        consulta = cliente.post(
            f"/colecciones/{coleccion_id}/consultas",
            json={"pregunta": "¿Quién puede editar una tarea?"},
        ).json()
        ruta = f"/colecciones/{coleccion_id}/consultas/{consulta['consulta_id']}/respuesta"
        with patch("servicio_consultas.OpenAI") as modelo:
            exceso = cliente.post(ruta, json={"autorizacion": "ENVIAR"})
            self.assertEqual(exceso.status_code, 429)
            modelo.assert_not_called()
        reloj.instante = 61.0
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.OpenAI"),
            patch(
                "servicio_consultas.responder_con_evidencia",
                return_value={"hay_evidencia": False, "respuesta": "", "fuentes": []},
            ),
        ):
            aceptada = cliente.post(ruta, json={"autorizacion": "ENVIAR"})
        self.assertEqual(aceptada.status_code, 200, aceptada.text)

    def test_cinco_envios_openai_por_visitante_en_una_hora_movil(self):
        class Reloj:
            instante = 0.0

            def __call__(self):
                return self.instante

        reloj = Reloj()
        cupo = LimitadorOpenAI(LimitesApi(), reloj)
        for _ in range(5):
            cupo.consumir("visitante-a")
        with self.assertRaises(HTTPException) as exceso:
            cupo.consumir("visitante-a")
        self.assertEqual(exceso.exception.status_code, 429)
        self.assertEqual(exceso.exception.headers["Retry-After"], "3600")
        cupo.consumir("visitante-b")
        reloj.instante = 3599.0
        with self.assertRaises(HTTPException) as exceso:
            cupo.consumir("visitante-a")
        self.assertEqual(exceso.exception.headers["Retry-After"], "1")
        reloj.instante = 3600.0
        cupo.consumir("visitante-a")

    def test_cupo_openai_no_cuenta_busqueda_local_ni_respuesta_guardada(self):
        class Reloj:
            instante = 0.0

            def __call__(self):
                return self.instante

        reloj = Reloj()
        cliente = TestClient(crear_app(
            limites=LimitesApi(
                llamadas_openai_origen=1, peticiones_origen=100,
                vida_segundos=7200,
            ),
            reloj=reloj,
        ))
        creada = cliente.post("/ejemplo/colecciones", json={"modo": "acotado"})
        self.assertEqual(creada.status_code, 201)
        coleccion_id = creada.json()["coleccion_id"]
        ruta_consultas = f"/colecciones/{coleccion_id}/consultas"
        primera = cliente.post(ruta_consultas, json={"pregunta": "editar tarea"})
        segunda = cliente.post(ruta_consultas, json={"pregunta": "¿Quién puede editar una tarea?"})
        self.assertEqual((primera.status_code, segunda.status_code), (201, 201))
        ruta_respuesta = f"{ruta_consultas}/{{}}/respuesta"
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.OpenAI") as constructor,
        ):
            constructor.return_value.responses.create.return_value.output_text = (
                '{"hay_evidencia":false,"respuesta":"","fuentes":[]}'
            )
            uno = cliente.post(
                ruta_respuesta.format(primera.json()["consulta_id"]),
                json={"autorizacion": "ENVIAR"},
            )
            repetida = cliente.post(
                ruta_respuesta.format(primera.json()["consulta_id"]),
                json={"autorizacion": "ENVIAR"},
            )
            exceso = cliente.post(
                ruta_respuesta.format(segunda.json()["consulta_id"]),
                json={"autorizacion": "ENVIAR"},
            )
            self.assertEqual(uno.status_code, 200, uno.text)
            self.assertEqual(repetida.status_code, 200, repetida.text)
            self.assertEqual(exceso.status_code, 429, exceso.text)
            self.assertEqual(exceso.headers["Retry-After"], "3600")
            self.assertEqual(constructor.return_value.responses.create.call_count, 1)
            self.assertEqual(constructor.call_args.kwargs["max_retries"], 0)
            self.assertEqual(
                cliente.post(ruta_consultas, json={"pregunta": "guardar tarea"}).status_code,
                201,
            )
            reloj.instante = 3600.0
            aceptada = cliente.post(
                ruta_respuesta.format(segunda.json()["consulta_id"]),
                json={"autorizacion": "ENVIAR"},
            )
            self.assertEqual(aceptada.status_code, 200, aceptada.text)
            self.assertEqual(constructor.return_value.responses.create.call_count, 2)

    def test_vencimiento_limpia_coleccion_y_permite_otra(self):
        class Reloj:
            instante = 0.0

            def __call__(self):
                return self.instante

        reloj = Reloj()
        cliente = TestClient(crear_app(
            limites=LimitesApi(colecciones_activas=1, vida_segundos=2),
            reloj=reloj,
        ))
        primera = cliente.post("/ejemplo/colecciones", json={"modo": "local"})
        coleccion_id = primera.json()["coleccion_id"]
        consulta = cliente.post(
            f"/colecciones/{coleccion_id}/consultas",
            json={"pregunta": "editar tarea"},
        ).json()
        reloj.instante = 3.0
        vencida = cliente.post(
            f"/colecciones/{coleccion_id}/consultas/{consulta['consulta_id']}/respuesta",
            json={},
        )
        self.assertEqual(vencida.status_code, 404)
        segunda = cliente.post("/ejemplo/colecciones", json={"modo": "local"})
        self.assertEqual(segunda.status_code, 201, segunda.text)

    def test_consulta_de_otra_coleccion_no_es_accesible(self):
        uno = self.crear_coleccion("acotado")
        dos = self.crear_coleccion("acotado")
        consulta = self.cliente.post(
            f"/colecciones/{uno}/consultas",
            json={"pregunta": "¿Quién puede editar una tarea?"},
        ).json()
        cruzada = self.cliente.post(
            f"/colecciones/{dos}/consultas/{consulta['consulta_id']}/respuesta",
            json={"autorizacion": "ENVIAR"},
        )
        self.assertEqual(cruzada.status_code, 404)

    def test_repetir_respuesta_reutiliza_resultado_sin_otro_envio(self):
        coleccion_id = self.crear_coleccion("acotado")
        consulta = self.cliente.post(
            f"/colecciones/{coleccion_id}/consultas",
            json={"pregunta": "¿Quién puede editar una tarea?"},
        ).json()
        ruta = f"/colecciones/{coleccion_id}/consultas/{consulta['consulta_id']}/respuesta"
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.OpenAI"),
            patch(
                "servicio_consultas.responder_con_evidencia",
                return_value={
                    "hay_evidencia": True,
                    "respuesta": "can_edit_task",
                    "fuentes": [1],
                },
            ) as responder,
        ):
            primera = self.cliente.post(ruta, json={"autorizacion": "ENVIAR"})
            segunda = self.cliente.post(ruta, json={"autorizacion": "ENVIAR"})
        self.assertEqual(primera.status_code, 200)
        self.assertEqual(primera.json(), segunda.json())
        responder.assert_called_once()

    def test_cache_del_ejemplo_esta_separada_del_cache_local(self):
        coleccion_id = self.crear_coleccion("completo")
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "clave-de-prueba"}),
            patch("servicio_consultas.OpenAI"),
            patch(
                "servicio_consultas.buscar_con_embeddings",
                return_value=([], []),
            ) as buscar,
        ):
            respuesta = self.cliente.post(
                f"/colecciones/{coleccion_id}/consultas",
                json={"pregunta": "guardar tarea", "autorizacion": "INDEXAR"},
            )
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        self.assertEqual(buscar.call_args.kwargs["cache_dir"], CACHE_EJEMPLO)
        self.assertFalse(buscar.call_args.kwargs["guardar_pregunta"])
        self.assertEqual(CACHE_EJEMPLO.name, "index_ejemplo")
        self.assertEqual(buscar.call_args.kwargs["cache_key"], "ejemplo-v1")


    def test_configuracion_local_por_variable_de_entorno(self):
        with patch.dict("os.environ", {"RAG_HABILITAR_RUTAS_LOCALES": "1"}):
            cliente = TestClient(crear_app())
        creada = cliente.post(
            "/colecciones", json={"carpeta": str(EJEMPLO), "modo": "local"}
        )
        self.assertEqual(creada.status_code, 201, creada.text)


    def test_respuesta_espera_traduccion_y_no_guarda_abstencion_prematura(self):
        almacen = ColeccionesTemporales(LimitesApi(), lambda: 0.0)
        coleccion_id = almacen.reservar_coleccion()
        almacen.completar_coleccion(coleccion_id, {"modo": "acotado"})
        consulta_id = almacen.reservar_consulta(coleccion_id, "¿Dónde está?")
        almacen.completar_consulta(
            coleccion_id, consulta_id, {"fuentes": [], "segundos": 0.0}
        )
        self.assertIsNone(
            almacen.iniciar_operacion(coleccion_id, consulta_id, "traduccion")
        )
        with self.assertRaises(HTTPException) as error:
            almacen.iniciar_operacion(coleccion_id, consulta_id, "respuesta")
        self.assertEqual(error.exception.status_code, 409)
        almacen.terminar_operacion(
            coleccion_id, consulta_id, "traduccion", {"fuentes": []}
        )
        self.assertIsNone(
            almacen.iniciar_operacion(coleccion_id, consulta_id, "respuesta")
        )


if __name__ == "__main__":
    unittest.main()
