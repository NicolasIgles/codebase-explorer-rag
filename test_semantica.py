"""Pruebas sin API para el índice semántico."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import semantica
from lenguajes_js import fragmentos_javascript


class SemanticaTest(unittest.TestCase):
    def test_indice_agrega_solo_importaciones_usadas_por_el_simbolo(self):
        carpeta = Path(__file__).parent / "sample_web_project"
        codigo = (
            'import { clsx } from "clsx"\n'
            'import { twMerge } from "tailwind-merge"\n'
            'import { unused } from "other"\n'
            'export function cn(inputs) { return twMerge(clsx(inputs)) }\n'
        )
        fragmento = fragmentos_javascript(codigo, carpeta / "lib" / "utils.ts", carpeta)[0]
        texto = semantica.texto_para_embedding(fragmento)
        self.assertIn('from "clsx"', texto)
        self.assertIn('from "tailwind-merge"', texto)
        self.assertNotIn('from "other"', texto)
        self.assertNotIn('from "tailwind-merge"', semantica.texto_para_embedding(fragmento, False))

    def test_indice_incluye_codigo_python_javascript_y_typescript(self):
        fragmentos = semantica.obtener_fragmentos(Path(__file__).parent)
        fuentes = {(f["ruta"], f["simbolo"]) for f in fragmentos}
        self.assertIn(("sample_project/tasks.py", "create_task"), fuentes)
        self.assertIn(("sample_web_project/lib/format.js", "formatTask"), fuentes)
        self.assertIn(("sample_web_project/lib/tasks.ts", "listTasks"), fuentes)

    def test_coseno(self):
        self.assertAlmostEqual(semantica.similitud_coseno([1, 0], [1, 0]), 1.0)
        self.assertEqual(semantica.similitud_coseno([1, 0], [0, 1]), 0.0)

    def test_cache_evita_nueva_llamada_para_texto_igual(self):
        cliente = Mock()
        cliente.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.6, 0.8])]
        )
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporal:
            primera = semantica.vectores(cliente, Path(temporal), ["símbolo de prueba"], temporal)
            segunda = semantica.vectores(cliente, Path(temporal), ["símbolo de prueba"], temporal)
        self.assertEqual(primera, segunda)
        cliente.embeddings.create.assert_called_once()

    def test_pruebas_relacionan_un_metodo_con_su_implementacion(self):
        fuente = {
            "ruta": "src/paquete/timed.py", "inicio": 20, "fin": 30,
            "contenedor": "TimestampSigner", "simbolo": "unsign",
            "tipo": "funcion", "similitud": 0.2,
        }
        pruebas = [
            {
                "ruta": "tests/test_timed.py", "inicio": numero, "fin": numero + 5,
                "contenedor": "TestTimestampSigner", "simbolo": f"test_{numero}",
                "tipo": "funcion", "atributos_llamados": ["sign", "unsign"],
                "similitud": 0.8,
            }
            for numero in (10, 40)
        ]
        self.assertIs(semantica.implementacion_desde_pruebas([fuente, *pruebas], pruebas), fuente)
        self.assertIsNone(semantica.implementacion_desde_pruebas([fuente, *pruebas], pruebas[:1]))


    def test_ejemplo_persistente_no_guarda_vector_de_pregunta(self):
        carpeta = Path(__file__).parent / "sample_project"
        fragmento = next(
            f for f in semantica.obtener_fragmentos(carpeta)
            if f["simbolo"] == "can_edit_task"
        )
        cliente = Mock()
        cliente.embeddings.create.side_effect = [
            SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[1, 0])]),
            SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[1, 0])]),
        ]
        pregunta = "¿Quién puede editar una tarea?"
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporal:
            semantica.buscar_con_embeddings(
                carpeta, pregunta, cliente, cache_dir=temporal,
                fragmentos=[fragmento], guardar_pregunta=False,
            )
            archivo = semantica.ruta_cache(carpeta, temporal)
            guardados = json.loads(archivo.read_text(encoding="utf-8"))["vectores"]
        clave_pregunta = hashlib.sha256(
            ("Pregunta sobre código: " + pregunta).encode("utf-8")
        ).hexdigest()
        self.assertEqual(len(guardados), 1)
        self.assertNotIn(clave_pregunta, guardados)
        self.assertEqual(cliente.embeddings.create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
