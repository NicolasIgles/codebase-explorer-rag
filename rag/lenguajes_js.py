"""Extrae símbolos de JavaScript, TypeScript, JSX y TSX sin ejecutar código."""

from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_javascript
import tree_sitter_typescript


EXTENSIONES = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".mts": "typescript",
    ".cts": "typescript", ".tsx": "tsx",
}
DECLARACIONES = {
    "function_declaration": "funcion",
    "generator_function_declaration": "funcion",
    "class_declaration": "clase",
    "interface_declaration": "clase",
    "type_alias_declaration": "variable",
    "enum_declaration": "clase",
    "method_definition": "funcion",
}
VALORES_FUNCION = {"arrow_function", "function_expression", "generator_function"}


def parser_para(ruta):
    extension = Path(ruta).suffix.lower()
    if extension in {".js", ".jsx", ".mjs", ".cjs"}:
        lenguaje = tree_sitter_javascript.language()
    elif extension == ".tsx":
        lenguaje = tree_sitter_typescript.language_tsx()
    elif extension in {".ts", ".mts", ".cts"}:
        lenguaje = tree_sitter_typescript.language_typescript()
    else:
        raise ValueError(f"Extensión no soportada: {extension}")
    return Parser(Language(lenguaje))


def _texto(nodo):
    return nodo.text.decode("utf-8", errors="replace") if nodo is not None else ""


def _fin_linea(nodo):
    return nodo.end_point.row + (nodo.end_point.column > 0)


def _importaciones(raiz):
    """Asocia cada importación con los nombres locales que introduce."""
    importaciones = []
    for nodo in raiz.named_children:
        if nodo.type != "import_statement":
            continue
        clausula = next((h for h in nodo.named_children if h.type == "import_clause"), None)
        if clausula is None:
            continue
        nombres = set()
        for parte in clausula.named_children:
            if parte.type == "identifier":
                nombres.add(_texto(parte))
            elif parte.type == "namespace_import":
                nombres.update(_texto(h) for h in parte.named_children if h.type == "identifier")
            elif parte.type == "named_imports":
                for especificacion in parte.named_children:
                    if especificacion.type != "import_specifier":
                        continue
                    local = (especificacion.child_by_field_name("alias")
                             or especificacion.child_by_field_name("name"))
                    if local is not None:
                        nombres.add(_texto(local))
        if nombres:
            importaciones.append((_texto(nodo), nombres))
    return importaciones


def _identificadores_en_tramo(nodo, inicio, fin):
    """Devuelve referencias de código en el tramo, sin contar comentarios ni cadenas."""
    nombres = set()
    pendientes = [nodo]
    while pendientes:
        actual = pendientes.pop()
        if actual.start_point.row + 1 > fin or _fin_linea(actual) < inicio:
            continue
        if actual.type in {"identifier", "type_identifier", "jsx_identifier", "shorthand_property_identifier"}:
            nombres.add(_texto(actual))
        else:
            pendientes.extend(actual.named_children)
    return nombres


def _llamadas(nodo):
    directas, metodos, atributos = [], [], []
    pendientes = [nodo]
    while pendientes:
        actual = pendientes.pop()
        if actual.type == "call_expression":
            funcion = actual.child_by_field_name("function")
            if funcion is not None and funcion.type == "identifier":
                nombre = _texto(funcion)
                if nombre not in directas:
                    directas.append(nombre)
            elif funcion is not None and funcion.type == "member_expression":
                nombre = _texto(funcion.child_by_field_name("property"))
                if nombre:
                    atributos.append(nombre)
                    if _texto(funcion.child_by_field_name("object")) == "this" and nombre not in metodos:
                        metodos.append(nombre)
        pendientes.extend(reversed(actual.named_children))
    return directas, metodos, atributos


def _definiciones(raiz):
    """Recorre declaraciones de módulo y métodos, sin indexar variables locales."""
    for nodo in raiz.named_children:
        inicio_exportacion = None
        if nodo.type == "export_statement":
            inicio_exportacion = nodo.start_point.row + 1
            hijos = nodo.named_children
        else:
            hijos = [nodo]
        for declaracion in hijos:
            if declaracion.type in DECLARACIONES and declaracion.type != "method_definition":
                nombre = _texto(declaracion.child_by_field_name("name"))
                if nombre:
                    yield declaracion, nombre, DECLARACIONES[declaracion.type], "", inicio_exportacion
                    if declaracion.type == "class_declaration":
                        cuerpo = declaracion.child_by_field_name("body")
                        if cuerpo is not None:
                            for metodo in cuerpo.named_children:
                                if metodo.type == "method_definition":
                                    nombre_metodo = _texto(metodo.child_by_field_name("name"))
                                    if nombre_metodo:
                                        yield metodo, nombre_metodo, "funcion", nombre, None
            elif declaracion.type in {"lexical_declaration", "variable_declaration"}:
                for variable in declaracion.named_children:
                    if variable.type != "variable_declarator":
                        continue
                    nombre = _texto(variable.child_by_field_name("name"))
                    valor = variable.child_by_field_name("value")
                    if nombre and valor is not None:
                        tipo = "funcion" if valor.type in VALORES_FUNCION else "variable"
                        yield variable, nombre, tipo, "", inicio_exportacion
            elif inicio_exportacion is not None and declaracion.type in VALORES_FUNCION:
                yield declaracion, "default", "funcion", "", inicio_exportacion


def fragmentos_javascript(texto, ruta, carpeta, max_lineas=100):
    """Devuelve fuentes con la misma forma que los fragmentos Python."""
    ruta = Path(ruta)
    arbol = parser_para(ruta).parse(texto.encode("utf-8"))
    lineas = texto.splitlines()
    if not lineas:
        return []
    lenguaje = EXTENSIONES[ruta.suffix.lower()]
    fragmentos = []
    importaciones = _importaciones(arbol.root_node)
    for nodo, nombre, tipo, contenedor, inicio_exportacion in _definiciones(arbol.root_node):
        inicio = inicio_exportacion or nodo.start_point.row + 1
        fin = _fin_linea(nodo)
        if tipo == "clase" and nodo.type == "class_declaration":
            cuerpo = nodo.child_by_field_name("body")
            if cuerpo is not None:
                fin = cuerpo.start_point.row + 1
        fin = min(fin, len(lineas))
        if inicio > fin:
            continue
        directas, metodos, atributos = _llamadas(nodo) if tipo == "funcion" else ([], [], [])
        for inicio_bloque in range(inicio, fin + 1, max_lineas):
            fin_bloque = min(fin, inicio_bloque + max_lineas - 1)
            codigo = "\n".join(f"{n}: {lineas[n - 1]}" for n in range(inicio_bloque, fin_bloque + 1))
            identificadores = _identificadores_en_tramo(nodo, inicio_bloque, fin_bloque)
            fragmentos.append({
                "ruta": ruta.relative_to(carpeta).as_posix(),
                "inicio": inicio_bloque,
                "fin": fin_bloque,
                "simbolo": nombre,
                "contenedor": contenedor,
                "tipo": tipo,
                "lenguaje": lenguaje,
                "descripcion": "",
                "codigo": codigo,
                "importaciones": [texto for texto, nombres in importaciones if nombres & identificadores],
                "llamadas": directas,
                "metodos_llamados": metodos,
                "atributos_llamados": atributos,
            })
    return fragmentos
