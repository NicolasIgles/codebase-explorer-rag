"""Recorrido y extracción de fragmentos de código fuente."""

import ast
import os
import tokenize
from pathlib import Path

from lenguajes_js import EXTENSIONES, fragmentos_javascript


CARPETAS_IGNORADAS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist",
    ".next", ".turbo", "coverage", "out", "vendor",
}
MAX_LINEAS = 100
MAX_ARCHIVOS = 2000
MAX_BYTES_ARCHIVO = 10_000_000
LINEAS_TEXTO = 30


def registrar_aviso(avisos, mensaje):
    if avisos is not None:
        avisos.append(mensaje)


def leer_archivo(ruta):
    """Devuelve texto Python respetando la codificación declarada por el archivo."""
    with tokenize.open(ruta) as archivo:
        return archivo.read()


def archivos_codigo(carpeta, avisos=None):
    """Recorre código Python, JavaScript y TypeScript sin carpetas generadas."""
    def avisar_error(error):
        registrar_aviso(avisos, f"No se pudo recorrer {error.filename}: {error.strerror}")

    for carpeta_actual, subcarpetas, archivos in os.walk(carpeta, onerror=avisar_error):
        subcarpetas[:] = sorted(
            nombre for nombre in subcarpetas
            if nombre not in CARPETAS_IGNORADAS and not nombre.startswith(".")
        )
        for nombre in sorted(archivos):
            if nombre.endswith(".py") or Path(nombre).suffix.lower() in EXTENSIONES:
                yield Path(carpeta_actual) / nombre


def archivos_python(carpeta, avisos=None):
    """Conserva el recorrido Python para quien use la función anterior."""
    return (ruta for ruta in archivos_codigo(carpeta, avisos) if ruta.suffix == ".py")


def fragmentos_texto(texto, ruta, carpeta):
    """Divide un archivo sin símbolos reconocidos en bloques de texto."""
    lineas = texto.splitlines()
    fragmentos = []
    for inicio in range(1, len(lineas) + 1, LINEAS_TEXTO):
        fin = min(inicio + LINEAS_TEXTO - 1, len(lineas))
        fragmentos.append({
            "ruta": ruta.relative_to(carpeta).as_posix(),
            "inicio": inicio,
            "fin": fin,
            "simbolo": "texto sin analizar",
            "contenedor": "",
            "tipo": "texto",
            "lenguaje": "python" if ruta.suffix == ".py" else EXTENSIONES.get(ruta.suffix.lower(), "texto"),
            "descripcion": "",
            "codigo": "\n".join(f"{n}: {lineas[n - 1]}" for n in range(inicio, fin + 1)),
            "llamadas": [],
            "metodos_llamados": [],
            "atributos_llamados": [],
        })
    return fragmentos


def nombres_llamados(nodo):
    """Devuelve nombres de funciones invocadas directamente dentro del bloque."""
    nombres = []
    for parte in ast.walk(nodo):
        if isinstance(parte, ast.Call) and isinstance(parte.func, ast.Name):
            if parte.func.id not in nombres:
                nombres.append(parte.func.id)
    return nombres


def nombres_metodos_llamados(nodo):
    """Devuelve los métodos invocados como self.metodo() dentro de una función."""
    nombres = []
    for parte in ast.walk(nodo):
        if (
            isinstance(parte, ast.Call)
            and isinstance(parte.func, ast.Attribute)
            and isinstance(parte.func.value, ast.Name)
            and parte.func.value.id == "self"
            and parte.func.attr not in nombres
        ):
            nombres.append(parte.func.attr)
    return nombres


def nombres_atributos_llamados(nodo):
    """Conserva las llamadas como objeto.metodo(), incluso en pruebas."""
    return [
        parte.func.attr
        for parte in ast.walk(nodo)
        if isinstance(parte, ast.Call) and isinstance(parte.func, ast.Attribute)
    ]


def fragmentos_de_archivo(ruta, carpeta, avisos=None):
    """Extrae funciones, clases y variables de nivel superior con sus líneas."""
    nombre = ruta.relative_to(carpeta).as_posix()
    try:
        if ruta.is_symlink():
            registrar_aviso(avisos, f"{nombre}: se omitió un enlace a otro archivo")
            return []
        if ruta.stat().st_size > MAX_BYTES_ARCHIVO:
            registrar_aviso(avisos, f"{nombre}: se omitió por superar {MAX_BYTES_ARCHIVO} bytes")
            return []
        texto = leer_archivo(ruta) if ruta.suffix == ".py" else ruta.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, SyntaxError, LookupError) as error:
        try:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError:
            registrar_aviso(avisos, f"{nombre}: no se pudo leer ({error})")
            return []
        registrar_aviso(avisos, f"{nombre}: lectura de respaldo tras un error de lectura")
        return fragmentos_texto(texto, ruta, carpeta)
    if ruta.suffix.lower() in EXTENSIONES:
        fragmentos = fragmentos_javascript(texto, ruta, carpeta, MAX_LINEAS)
        if fragmentos:
            return fragmentos
        registrar_aviso(avisos, f"{nombre}: no se reconocieron símbolos; búsqueda como texto")
        return fragmentos_texto(texto, ruta, carpeta)
    try:
        arbol = ast.parse(texto, filename=str(ruta))
    except SyntaxError as error:
        registrar_aviso(avisos, f"{nombre}: sintaxis inválida en línea {error.lineno}; búsqueda como texto")
        return fragmentos_texto(texto, ruta, carpeta)

    lineas = texto.splitlines()
    fragmentos = []
    padres = {
        hijo: padre
        for padre in ast.walk(arbol)
        for hijo in ast.iter_child_nodes(padre)
    }
    definiciones = [
        nodo for nodo in ast.walk(arbol)
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for nodo in definiciones:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            isinstance(decorador, ast.Name) and decorador.id == "overload"
            or isinstance(decorador, ast.Attribute) and decorador.attr == "overload"
            for decorador in nodo.decorator_list
        ) and any(
            otro is not nodo and otro.name == nodo.name
            and padres.get(otro) is padres.get(nodo)
            and not any(
                isinstance(decorador, ast.Name) and decorador.id == "overload"
                or isinstance(decorador, ast.Attribute) and decorador.attr == "overload"
                for decorador in otro.decorator_list
            )
            for otro in definiciones
        ):
            continue
        inicio = min([nodo.lineno] + [d.lineno for d in nodo.decorator_list])
        if isinstance(nodo, ast.ClassDef):
            # La fuente de una clase muestra su encabezado y descripción.
            # Sus métodos tienen fragmentos propios y no deben contaminar su ranking.
            primera_parte = nodo.body[0] if nodo.body else None
            if (
                isinstance(primera_parte, ast.Expr)
                and isinstance(primera_parte.value, ast.Constant)
                and isinstance(primera_parte.value.value, str)
            ):
                ultimo = primera_parte.end_lineno or nodo.lineno
            else:
                ultimo = nodo.lineno
        else:
            ultimo = nodo.end_lineno or len(lineas)
        contenedores = []
        padre = padres.get(nodo)
        while padre is not None:
            if isinstance(padre, ast.ClassDef):
                contenedores.insert(0, padre.name)
            padre = padres.get(padre)
        for inicio_bloque in range(inicio, ultimo + 1, MAX_LINEAS):
            fin = min(ultimo, inicio_bloque + MAX_LINEAS - 1)
            fragmentos.append({
                "ruta": ruta.relative_to(carpeta).as_posix(),
                "inicio": inicio_bloque,
                "fin": fin,
                "simbolo": nodo.name,
                "contenedor": ".".join(contenedores),
                "tipo": "clase" if isinstance(nodo, ast.ClassDef) else "funcion",
                "lenguaje": "python",
                "descripcion": ast.get_docstring(nodo) or "",
                "codigo": "\n".join(f"{n}: {lineas[n - 1]}" for n in range(inicio_bloque, fin + 1)),
                "llamadas": [] if isinstance(nodo, ast.ClassDef) else nombres_llamados(nodo),
                "metodos_llamados": (
                    [] if isinstance(nodo, ast.ClassDef) else nombres_metodos_llamados(nodo)
                ),
                "atributos_llamados": (
                    [] if isinstance(nodo, ast.ClassDef) else nombres_atributos_llamados(nodo)
                ),
            })

    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign):
            nombres = [objetivo.id for objetivo in nodo.targets if isinstance(objetivo, ast.Name)]
        elif isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
            nombres = [nodo.target.id]
        else:
            continue
        if not nombres:
            continue
        inicio = nodo.lineno
        fin = min(nodo.end_lineno or inicio, inicio + MAX_LINEAS - 1)
        fragmentos.append({
            "ruta": ruta.relative_to(carpeta).as_posix(),
            "inicio": inicio,
            "fin": fin,
            "simbolo": ", ".join(nombres),
            "contenedor": "",
            "tipo": "variable",
            "lenguaje": "python",
            "descripcion": "",
            "codigo": "\n".join(f"{n}: {lineas[n - 1]}" for n in range(inicio, fin + 1)),
            "llamadas": [],
            "metodos_llamados": [],
            "atributos_llamados": [],
        })
    return fragmentos



def obtener_fragmentos(carpeta, avisos=None):
    """Prepara una sola colección de fragmentos para cualquier recuperación."""
    carpeta = Path(carpeta).expanduser().resolve()
    if not carpeta.is_dir():
        raise ValueError(f"No existe la carpeta: {carpeta}")
    fragmentos = []
    for cantidad, ruta in enumerate(archivos_codigo(carpeta, avisos), start=1):
        if cantidad > MAX_ARCHIVOS:
            registrar_aviso(avisos, f"Se detuvo la lectura al llegar a {MAX_ARCHIVOS} archivos de código.")
            break
        fragmentos.extend(fragmentos_de_archivo(ruta, carpeta, avisos))
    return fragmentos
