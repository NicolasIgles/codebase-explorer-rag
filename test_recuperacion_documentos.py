"""Recuperación léxica sobre colecciones de documentos, como un CV subido en PDF o TXT."""

import unittest

from fragmentos import normalizar
from ingesta_documentos import fragmentos_desde_bytes
from recuperacion_local import ordenar_fragmentos, separar_palabras


# Secciones separadas, como quedan los fragmentos de un CV en PDF con títulos de plantilla.
CV = """# Martina Gómez
martina.gomez@correo.com · +54 351 555-0182

## Experiencia
Tech Lead en Pagofácil (2022 – actualidad). Checkout con React y TypeScript.
Analista de BI en Mercantil: tableros en Power BI y microservicios en Node.js.

## Formación
Ingeniería en Sistemas — Universidad Tecnológica Nacional

## Idiomas
Español nativo. Inglés avanzado (C1).
"""


def coleccion():
    fragmentos = fragmentos_desde_bytes("cv.md", CV.encode("utf-8"))
    return [normalizar(f, "cv") for f in fragmentos]


def primero(pregunta):
    fuentes = ordenar_fragmentos(coleccion(), pregunta)
    return fuentes[0]["texto"] if fuentes else ""


class RecuperacionDocumentosTest(unittest.TestCase):
    def test_nombres_compuestos_y_siglas(self):
        palabras = separar_palabras("JavaScript, Node.js y CI/CD", unir=True)
        for esperada in ("java", "script", "javascript", "nodejs", "js", "ci", "cd", "cicd"):
            self.assertIn(esperada, palabras)
        self.assertNotIn("ur", separar_palabras("Signed URLs"))
        self.assertEqual(separar_palabras("Integré LLMs y APIs"), ["integre", "llm", "api"])
        self.assertEqual(separar_palabras("¿Trabajó con pandas?"), ["pandas"])
        self.assertNotIn("javascript", separar_palabras("JavaScript"))

    def test_preguntas_habituales_sobre_un_cv(self):
        casos = {
            "¿Sabe typescript?": "TypeScript",
            "¿Qué herramientas de BI maneja?": "Power BI",
            "¿Usó nodejs?": "Node.js",
            "¿Cuál es su email?": "martina.gomez@correo.com",
            "¿Cuál es su teléfono?": "+54 351",
            "¿Qué nivel de inglés tiene?": "Inglés avanzado",
            "¿En qué empresa trabaja actualmente?": "Pagofácil",
            "¿Dónde estudió?": "Universidad Tecnológica",
        }
        for pregunta, esperado in casos.items():
            with self.subTest(pregunta=pregunta):
                self.assertIn(esperado, primero(pregunta))

    def test_sin_coincidencias_no_devuelve_fuentes(self):
        self.assertEqual(ordenar_fragmentos(coleccion(), "¿Sabe programar en Kotlin?"), [])


if __name__ == "__main__":
    unittest.main()
