"""Genera CVs ficticios en PDF con layouts típicos para evaluar la ingesta.

Cada CV imita una forma común de exportar un currículum:
- cv_word.pdf: documento de una columna exportado por un procesador de texto (LibreOffice, fuente Carlito).
- cv_dos_columnas.pdf: plantilla de diseño con barra lateral (contacto, habilidades, idiomas) y texto posicionado.
- cv_espaciado.pdf: plantilla en inglés, dos páginas, con espaciado entre letras (tracking) en todo el texto,
  habilidades en una línea separada por barras y viñetas.
- cv_canva.pdf: plantilla de editor visual que dibuja cada palabra por separado y los títulos letra por letra.

Uso: python evaluacion/eval_pdf/generar_cvs.py  (requiere reportlab y LibreOffice para cv_word.pdf)
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

CARPETA = Path(__file__).resolve().parent / "cvs"


HTML_WORD = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body { font-family: Carlito; font-size: 11pt; }
h1 { font-size: 20pt; margin-bottom: 0; }
h2 { font-size: 13pt; border-bottom: 1px solid #888; margin-top: 14pt; }
p, li { margin: 2pt 0; }
</style></head><body>
<h1>Martina Sofía Gómez</h1>
<p>Desarrolladora Full Stack · Córdoba, Argentina</p>
<p>martina.gomez.dev@correo.com · +54 351 555-0182 · linkedin.com/in/martinagomezdev · github.com/mgomez-dev</p>

<h2>Perfil profesional</h2>
<p>Desarrolladora con 6 años de experiencia construyendo aplicaciones web para fintech y comercio electrónico.
Me especializo en interfaces accesibles y en APIs eficientes. Disfruto la mentoría de perfiles junior.</p>

<h2>Experiencia laboral</h2>
<p><b>Tech Lead</b> — Pagofácil Digital S.A. (marzo 2022 – actualidad)</p>
<ul>
<li>Lideré un equipo de 5 desarrolladores en la reescritura del checkout con React y TypeScript.</li>
<li>Reduje el tiempo de carga del flujo de pago un 40% con code splitting y caché en el edge.</li>
<li>Definí la estrategia de pruebas end-to-end con Playwright e integración continua en GitHub Actions.</li>
</ul>
<p><b>Desarrolladora Backend</b> — Mercantil Online (enero 2019 – febrero 2022)</p>
<ul>
<li>Diseñé microservicios en Node.js y Express con PostgreSQL y Redis.</li>
<li>Migré la infraestructura a AWS (ECS, RDS, S3) usando Terraform y Docker.</li>
<li>Implementé la conciliación diaria de pagos con colas en RabbitMQ.</li>
</ul>
<p><b>Pasante de Desarrollo</b> — Estudio Sierras Software (2018)</p>
<ul><li>Mantenimiento de sitios en PHP y WordPress; primeras tareas con JavaScript.</li></ul>

<h2>Formación académica</h2>
<p>Ingeniería en Sistemas de Información — Universidad Tecnológica Nacional, Facultad Regional Córdoba (2013 – 2019)</p>
<p>Diplomatura en Ciencia de Datos — Universidad Nacional de Córdoba (2021)</p>

<h2>Certificaciones</h2>
<p>AWS Certified Solutions Architect – Associate (2023). Scrum Fundamentals Certified (2020).</p>

<h2>Habilidades técnicas</h2>
<p>Lenguajes: JavaScript, TypeScript, Python, SQL. Frameworks: React, Next.js, Express, FastAPI.
Bases de datos: PostgreSQL, MongoDB, Redis. Herramientas: Docker, Git, Jira, Figma.</p>

<h2>Idiomas</h2>
<p>Español nativo. Inglés avanzado (C1, First Certificate). Portugués básico.</p>
</body></html>
"""


def cv_word(destino):
    if not shutil.which("soffice"):
        print("LibreOffice no disponible: se omite cv_word.pdf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "cv_word.html"
        html.write_text(HTML_WORD, encoding="utf-8")
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf:writer_web_pdf_Export", "--outdir", tmp, str(html)],
            check=True, capture_output=True, timeout=120,
        )
        shutil.copy(Path(tmp) / "cv_word.pdf", destino)


def cv_dos_columnas(destino):
    """Plantilla con barra lateral; el texto se dibuja en el orden en que lo haría un editor visual."""
    ancho, alto = A4
    c = canvas.Canvas(str(destino), pagesize=A4)
    lateral = 190
    c.setFillColor(HexColor("#1f2d3d"))
    c.rect(0, 0, lateral, alto, fill=1, stroke=0)

    def texto(x, y, valor, fuente="Helvetica", tam=9.5, color="#222222"):
        c.setFillColor(HexColor(color))
        c.setFont(fuente, tam)
        c.drawString(x, y, valor)

    # Encabezado en la columna principal (se dibuja primero, como en muchas plantillas)
    texto(lateral + 25, alto - 60, "JUAN PABLO RÍOS", "Helvetica-Bold", 22)
    texto(lateral + 25, alto - 80, "Analista de Datos | Business Intelligence", "Helvetica", 11, "#555555")

    # Barra lateral
    blanco = "#ffffff"
    y = alto - 60
    for linea, fuente, tam in [
        ("CONTACTO", "Helvetica-Bold", 11),
        ("jprios.datos@mail.com", "Helvetica", 9),
        ("+34 612 555 019", "Helvetica", 9),
        ("Valencia, España", "Helvetica", 9),
        ("linkedin.com/in/jprios", "Helvetica", 9),
        ("", "Helvetica", 9),
        ("HABILIDADES", "Helvetica-Bold", 11),
        ("SQL avanzado", "Helvetica", 9),
        ("Python (pandas, scikit-learn)", "Helvetica", 9),
        ("Power BI y Tableau", "Helvetica", 9),
        ("Excel / VBA", "Helvetica", 9),
        ("dbt y Airflow", "Helvetica", 9),
        ("Google BigQuery", "Helvetica", 9),
        ("Estadística aplicada", "Helvetica", 9),
        ("", "Helvetica", 9),
        ("IDIOMAS", "Helvetica-Bold", 11),
        ("Español — nativo", "Helvetica", 9),
        ("Inglés — B2", "Helvetica", 9),
        ("Catalán — intermedio", "Helvetica", 9),
        ("", "Helvetica", 9),
        ("INTERESES", "Helvetica-Bold", 11),
        ("Ciclismo de montaña", "Helvetica", 9),
        ("Fotografía", "Helvetica", 9),
    ]:
        if linea:
            texto(22, y, linea, fuente, tam, blanco)
        y -= 16

    # Columna principal
    x = lateral + 25
    y = alto - 120
    bloques = [
        ("SOBRE MÍ", [
            "Analista con 4 años transformando datos de ventas y logística en decisiones.",
            "Experiencia construyendo tableros ejecutivos y modelos de previsión de demanda.",
        ]),
        ("EXPERIENCIA", [
            "Analista de Datos Senior · Logística Mediterránea (2023 – presente)",
            "• Automaticé reportes semanales con Python y Airflow, ahorrando 12 horas por semana.",
            "• Diseñé el modelo de previsión de demanda que redujo el quiebre de stock un 18%.",
            "• Coordino a 2 analistas junior y presento resultados al comité de operaciones.",
            "",
            "Analista de BI · Retail Levante (2021 – 2023)",
            "• Construí tableros en Power BI para 30 tiendas con datos de ventas diarias.",
            "• Modelé el data warehouse en BigQuery y transformaciones con dbt.",
        ]),
        ("EDUCACIÓN", [
            "Grado en Estadística · Universitat de València (2016 – 2020)",
            "Máster en Big Data y Business Analytics · EAE Business School (2021)",
        ]),
        ("CERTIFICACIONES", [
            "Microsoft Certified: Power BI Data Analyst Associate (PL-300), 2022",
        ]),
    ]
    for titulo, lineas in bloques:
        texto(x, y, titulo, "Helvetica-Bold", 12, "#1f2d3d")
        y -= 18
        for linea in lineas:
            if linea:
                texto(x, y, linea, "Helvetica", 9.5)
            y -= 14
        y -= 10
    c.showPage()
    c.save()


def cv_espaciado(destino):
    """Plantilla en inglés, dos páginas, con espaciado entre letras.

    El espaciado se fija en el primer título y queda activo para el resto del texto (el estado de
    texto del PDF sobrevive entre bloques), como en plantillas con tracking en todo el cuerpo.
    """
    c = canvas.Canvas(str(destino), pagesize=A4)
    ancho, alto = A4

    def titulo(y, valor):
        t = c.beginText(50, y)
        t.setFont("Helvetica-Bold", 12)
        t.setCharSpace(4)
        t.textLine(valor.upper())
        c.drawText(t)
        c.line(50, y - 4, ancho - 50, y - 4)
        return y - 22

    def linea(y, valor, fuente="Helvetica", tam=10):
        c.setFont(fuente, tam)
        c.drawString(50, y, valor)
        return y - 14

    y = alto - 60
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, y, "Daniel Okafor")
    y -= 20
    y = linea(y, "Senior Mobile Engineer — iOS & Android")
    y = linea(y, "daniel.okafor@inbox.dev  |  +44 7700 900123  |  London, UK  |  github.com/dokafor")
    y -= 10
    y = titulo(y, "Summary")
    y = linea(y, "Mobile engineer with 8 years of experience shipping consumer apps used by millions.")
    y = linea(y, "Strong focus on performance, offline-first architecture and accessibility.")
    y -= 8
    y = titulo(y, "Skills")
    y = linea(y, "Swift | SwiftUI | Kotlin | Jetpack Compose | Flutter | Dart | GraphQL | Firebase | CI/CD | Fastlane")
    y -= 8
    y = titulo(y, "Experience")
    for valor, fuente in [
        ("Lead iOS Engineer, Streamly Media — London (2021 – Present)", "Helvetica-Bold"),
        ("• Led the rewrite of the video player in SwiftUI, cutting crash rate by 35%.", "Helvetica"),
        ("• Mentored 4 engineers and introduced weekly architecture reviews.", "Helvetica"),
        ("• Built offline downloads with background sessions and encrypted storage.", "Helvetica"),
        ("", "Helvetica"),
        ("Android Developer, Banco Atlântico Digital — Lisbon (2018 – 2021)", "Helvetica-Bold"),
        ("• Developed the mobile banking app in Kotlin with Jetpack Compose.", "Helvetica"),
        ("• Integrated biometric login and push notifications via Firebase Cloud Messaging.", "Helvetica"),
        ("", "Helvetica"),
        ("Junior Developer, AppFoundry — Lagos (2016 – 2018)", "Helvetica-Bold"),
        ("• Built cross-platform prototypes in Flutter for startup clients.", "Helvetica"),
    ]:
        y = linea(y, valor, fuente) if valor else y - 8
    c.showPage()

    y = alto - 60
    y = titulo(y, "Education")
    y = linea(y, "BSc Computer Science — University of Lagos (2012 – 2016), First Class Honours")
    y -= 8
    y = titulo(y, "Certifications")
    y = linea(y, "Google Associate Android Developer (2019)")
    y = linea(y, "Apple WWDC Scholarship (2015)")
    y -= 8
    y = titulo(y, "Languages")
    y = linea(y, "English (native), Portuguese (professional working proficiency), Yoruba (native)")
    y -= 8
    y = titulo(y, "Volunteering")
    y = linea(y, "Code mentor at Black Girls Code London chapter, teaching mobile development basics.")
    c.showPage()
    c.save()


def cv_canva(destino):
    """Plantilla de editor visual: cada palabra se dibuja por separado y los títulos letra por letra.

    Así exportan muchas herramientas de diseño (Canva, Figma, algunos generadores web): no hay
    caracteres de espacio, solo palabras ubicadas una al lado de la otra.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    c = canvas.Canvas(str(destino), pagesize=A4)
    ancho, alto = A4
    lateral = 180
    c.setFillColor(HexColor("#f3ece6"))
    c.rect(0, 0, lateral, alto, fill=1, stroke=0)
    c.setFillColor(HexColor("#2b2b2b"))

    def palabras(x, y, valor, fuente="Helvetica", tam=9.5):
        c.setFont(fuente, tam)
        espacio = stringWidth(" ", fuente, tam)
        for palabra in valor.split(" "):
            c.drawString(x, y, palabra)
            x += stringWidth(palabra, fuente, tam) + espacio

    def espaciado(x, y, valor, fuente="Helvetica-Bold", tam=11, separacion=2.5):
        c.setFont(fuente, tam)
        for letra in valor:
            c.drawString(x, y, letra)
            x += stringWidth(letra, fuente, tam) + separacion

    espaciado(lateral + 25, alto - 62, "VALENTINA RUIZ", tam=22, separacion=4)
    palabras(lateral + 25, alto - 84, "Diseñadora UX/UI y Desarrolladora Frontend", tam=11)

    y = alto - 70
    for tipo, valor in [
        ("t", "CONTACTO"), ("p", "valen.ruiz.ux@correo.com"), ("p", "+52 55 5555 0147"),
        ("p", "Ciudad de México"), ("p", "behance.net/valenruiz"), ("-", ""),
        ("t", "HERRAMIENTAS"), ("p", "Figma y FigJam"), ("p", "Adobe Illustrator"), ("p", "Maze y Hotjar"),
        ("p", "HTML, CSS y Sass"), ("p", "JavaScript y Vue.js"), ("p", "Storybook"), ("-", ""),
        ("t", "IDIOMAS"), ("p", "Español nativo"), ("p", "Inglés intermedio (B1)"), ("p", "Francés básico"),
    ]:
        if tipo == "t":
            espaciado(22, y, valor)
            y -= 18
        elif tipo == "p":
            palabras(22, y, valor, tam=9)
            y -= 14
        else:
            y -= 10

    x = lateral + 25
    y = alto - 125
    for titulo, lineas in [
        ("PERFIL", [
            "Diseñadora con 5 años creando productos digitales centrados en las personas.",
            "Combino investigación de usuarios, prototipado y maquetación frontend.",
        ]),
        ("EXPERIENCIA", [
            "Diseñadora UX Senior — Clínica Digital Salud+ (2022 – actualidad)",
            "Rediseñé la app de turnos médicos y aumenté la tasa de reservas completadas un 27%.",
            "Armé el sistema de diseño con 60 componentes documentados en Storybook.",
            "Realicé 40 entrevistas y pruebas de usabilidad remotas con pacientes.",
            "",
            "Diseñadora UI — Agencia Colibrí (2019 – 2022)",
            "Diseñé sitios para marcas de moda y gastronomía en Figma y los maqueté en Vue.js.",
            "Lideré los talleres de descubrimiento con clientes y el equipo comercial.",
        ]),
        ("FORMACIÓN", [
            "Licenciatura en Diseño de la Comunicación Gráfica — UAM Xochimilco (2014 – 2018)",
            "Certificado Google UX Design — Coursera (2020)",
        ]),
        ("PREMIOS", [
            "Mención honorífica en los Premios Diseño Accesible 2023 por la app de turnos.",
        ]),
    ]:
        espaciado(x, y, titulo, separacion=3)
        y -= 18
        for linea in lineas:
            if linea:
                palabras(x, y, linea)
            y -= 14
        y -= 10
    c.showPage()
    c.save()


if __name__ == "__main__":
    CARPETA.mkdir(parents=True, exist_ok=True)
    cv_word(CARPETA / "cv_word.pdf")
    cv_dos_columnas(CARPETA / "cv_dos_columnas.pdf")
    cv_espaciado(CARPETA / "cv_espaciado.pdf")
    cv_canva(CARPETA / "cv_canva.pdf")
    print("PDFs en", CARPETA)
