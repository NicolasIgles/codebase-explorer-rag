"""Límites y aislamiento de las colecciones subidas por visitantes."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api_http import LimiteCuerpoCarga, crear_app, origen_peticion
from cargas_temporales import AlmacenCargas, VIDA_SEGUNDOS


class Reloj:
    instante = 1_000_000.0

    def __call__(self):
        return self.instante


class CargasTemporalesTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.reloj = Reloj()
        self.raiz = Path(self.temporal.name)
        self.cliente = TestClient(crear_app(
            upload_dir=self.raiz, reloj=self.reloj, reloj_cargas=self.reloj
        ))

    def cargar(self, nombre="reglas.py", contenido=b"def elegir(x):\n    return x == 1\n", modo="local"):
        return self.cliente.post(
            "/cargas/colecciones", data={"modo": modo},
            files=[("archivos", (nombre, contenido))],
        )

    def test_carga_codigo_y_documento_aislados_y_borrado_manual(self):
        with patch("servicio_consultas.OpenAI", side_effect=AssertionError("Sin consentimiento")):
            creada = self.cliente.post(
                "/cargas/colecciones", data={"modo": "local"},
                files=[
                    ("archivos", ("reglas.py", b"def elegir(x):\n    return x == 1\n")),
                    ("archivos", ("guia.md", b"# Elegir\nLa regla elegir acepta el valor uno.\n")),
                ],
            )
            self.assertEqual(creada.status_code, 201, creada.text)
            uno = creada.json()["coleccion_id"]
            self.assertEqual(creada.json()["vence_en_segundos"], VIDA_SEGUNDOS)
            dos = self.cargar("privado.txt", b"Clave de la segunda coleccion").json()["coleccion_id"]
            respuesta = self.cliente.post(
                f"/colecciones/{uno}/consultas", json={"pregunta": "elegir"}
            )
            self.assertEqual(respuesta.status_code, 201, respuesta.text)
            fuentes = respuesta.json()["fuentes"]
            self.assertTrue(any(f["tipo_fuente"] == "codigo" for f in fuentes))
            self.assertTrue(any(f["tipo_fuente"] == "documento" for f in fuentes))
            self.assertNotIn("privado.txt", {f["ruta"] for f in fuentes})
            consulta_id = respuesta.json()["consulta_id"]
            self.assertEqual(self.cliente.get(
                f"/colecciones/{dos}/consultas/{consulta_id}/fuentes/1"
            ).status_code, 404)
            self.assertEqual(self.cliente.delete(f"/colecciones/{uno}").status_code, 204)
            self.assertFalse((self.raiz / uno).exists())
            self.assertEqual(self.cliente.get(f"/colecciones/{uno}/alcance").status_code, 404)

    def test_rechaza_rutas_formatos_y_tamano(self):
        self.assertEqual(self.cargar("../fuera.py").status_code, 422)
        self.assertEqual(self.cargar("orden.exe").status_code, 422)
        self.assertEqual(self.cargar(contenido=b"x" * 10_000_001).status_code, 413)
        self.assertEqual(self.cargar("largo.txt", b"a" * 1_600_001).status_code, 413)
        self.assertEqual(self.cargar("largo.py", b"a" * 10_001).status_code, 413)
        seis = [("archivos", (f"{i}.txt", b"a")) for i in range(6)]
        self.assertEqual(self.cliente.post(
            "/cargas/colecciones", data={"modo": "local"}, files=seis
        ).status_code, 413)
        self.assertFalse(any(self.raiz.iterdir()))

    def test_pdf_malformado_avisa_y_no_ejecuta_modelo(self):
        with patch("servicio_consultas.OpenAI", side_effect=AssertionError("Sin consentimiento")):
            creada = self.cargar("roto.pdf", b"no es un pdf")
        self.assertEqual(creada.status_code, 201, creada.text)
        self.assertEqual(creada.json()["cantidad_fragmentos"], 0)
        self.assertTrue(any("PDF no utilizable" in aviso for aviso in creada.json()["avisos"]))

    def test_vencimiento_borra_archivos_y_metadatos_tras_reinicio(self):
        creada = self.cargar()
        identificador = creada.json()["coleccion_id"]
        self.assertTrue((self.raiz / identificador / "reglas.py").exists())
        self.reloj.instante += VIDA_SEGUNDOS + 1
        self.assertEqual(self.cliente.get(f"/colecciones/{identificador}/alcance").status_code, 404)
        self.assertFalse((self.raiz / identificador).exists())
        otra = self.cargar()
        otro_id = otra.json()["coleccion_id"]
        self.reloj.instante += VIDA_SEGUNDOS + 1
        crear_app(upload_dir=self.raiz, reloj=self.reloj, reloj_cargas=self.reloj)
        self.assertFalse((self.raiz / otro_id).exists())

    def test_cupo_global_incluye_reserva_de_indices(self):
        cargas = AlmacenCargas(self.raiz, self.reloj)
        primero = "a" * 32
        segundo = "b" * 32
        cargas.reservar(primero, 50_000_000)
        cargas.confirmar(primero)
        (self.raiz / primero / "a.txt").write_bytes(b"x" * 50_000_000)
        with self.assertRaises(Exception) as error:
            cargas.reservar(segundo, 50_000_000)
        self.assertEqual(error.exception.status_code, 429)

    def test_cuerpo_sin_content_length_tambien_se_limita(self):
        async def consumir(_scope, receive, _send):
            await receive()

        mensajes = []

        async def recibir():
            return {"type": "http.request", "body": b"x" * 50_100_001,
                    "more_body": False}

        async def enviar(mensaje):
            mensajes.append(mensaje)

        asyncio.run(LimiteCuerpoCarga(consumir)(
            {"type": "http", "path": "/cargas/colecciones", "method": "POST",
             "headers": []}, recibir, enviar,
        ))
        self.assertEqual(mensajes[0]["status"], 413)

    def test_cabecera_falsa_no_cambia_origen_sin_proxy_confiable(self):
        class Peticion:
            client = type("Cliente", (), {"host": "10.0.0.2"})()
            headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}

        with patch.dict("os.environ", {"RAG_PROXY_TRUSTED_CIDRS": ""}):
            self.assertEqual(origen_peticion(Peticion()), "10.0.0.2")
        with patch.dict("os.environ", {"RAG_PROXY_TRUSTED_CIDRS": "10.0.0.0/24"}):
            self.assertEqual(origen_peticion(Peticion()), "5.6.7.8")
            Peticion.headers = {"x-real-ip": "9.8.7.6", "x-forwarded-for": "1.2.3.4"}
            self.assertEqual(origen_peticion(Peticion()), "9.8.7.6")


if __name__ == "__main__":
    unittest.main()
