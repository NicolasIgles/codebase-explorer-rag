"""Pruebas de ubicaciones documentales y PDF sin OCR."""

import unittest
from io import BytesIO

from pypdf import PdfWriter

from fragmentos import identidad, lugar, se_superponen
from ingesta_documentos import fragmentos_desde_bytes
from ingesta_fuentes import obtener_fragmentos


def pdf_con_texto(texto):
    contenido = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode("ascii")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(contenido)).encode() + b" >>\nstream\n" + contenido + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = [0]
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{numero} 0 obj\n".encode() + objeto + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(posiciones)}\n0000000000 65535 f \n".encode()
    for posicion in posiciones[1:]:
        salida += f"{posicion:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {len(posiciones)} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF".encode()
    return bytes(salida)


class IngestaDocumentosTest(unittest.TestCase):
    def test_markdown_conserva_seccion_y_lineas(self):
        texto = b"# Guia\nIntroduccion\n## Permisos\nSolo el responsable edita.\n"
        fragmentos = fragmentos_desde_bytes("docs/guia.md", texto)
        permisos = next(f for f in fragmentos if f["simbolo"] == "Permisos")
        self.assertEqual((permisos["inicio"], permisos["fin"]), (3, 4))
        self.assertEqual(permisos["ubicacion"]["tipo"], "lineas")
        self.assertIn("Solo el responsable", permisos["texto"])

    def test_pdf_con_texto_cita_pagina_y_pdf_vacio_avisa(self):
        fragmentos = fragmentos_desde_bytes(
            "docs/guia.pdf", pdf_con_texto("Guia de tareas en PDF")
        )
        self.assertEqual(lugar(fragmentos[0]), "docs/guia.pdf:página 1")
        self.assertIn("Guia de tareas", fragmentos[0]["texto"])
        escritor = PdfWriter()
        escritor.add_blank_page(width=612, height=792)
        salida = BytesIO()
        escritor.write(salida)
        avisos = []
        self.assertEqual(
            fragmentos_desde_bytes("docs/vacio.pdf", salida.getvalue(), avisos), []
        )
        self.assertTrue(any("sin texto seleccionable" in aviso for aviso in avisos))

    def test_coleccion_mixta_compartida(self):
        fragmentos = obtener_fragmentos("sample_project", coleccion_id="ejemplo-prueba")
        tipos = {f["tipo_fuente"] for f in fragmentos}
        self.assertEqual(tipos, {"codigo", "documento"})
        self.assertEqual({f["coleccion_id"] for f in fragmentos}, {"ejemplo-prueba"})
        self.assertTrue(all(f["ruta"] and f["ubicacion"] for f in fragmentos))

    def test_linea_extensa_se_divide_sin_perder_ubicacion(self):
        fragmentos = fragmentos_desde_bytes("largo.txt", b"a" * 4000)
        self.assertEqual(len(fragmentos), 3)
        self.assertEqual(sum(len(f["texto"]) for f in fragmentos), 4000)
        self.assertEqual([f["ubicacion"]["columna_inicio"] for f in fragmentos],
                         [1, 1601, 3201])
        self.assertTrue(all(f["inicio"] == f["fin"] == 1 for f in fragmentos))
        self.assertEqual(len({identidad(f) for f in fragmentos}), 3)
        self.assertFalse(se_superponen(fragmentos[0], fragmentos[1]))


if __name__ == "__main__":
    unittest.main()
