"""Primera búsqueda local para el proyecto de aprendizaje Codebase Explorer."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SAMPLE_PROJECT = ROOT / "sample_project"
STOP_WORDS = {
    "a", "al", "como", "con", "de", "del", "donde", "el", "en", "es",
    "esta", "este", "la", "las", "lo", "los", "para", "por", "que",
    "se", "un", "una", "y",
}


@dataclass(frozen=True)
class Symbol:
    file: str
    line: int
    name: str
    description: str


def words(text: str) -> set[str]:
    """Convierte texto en palabras comparables, ignorando tildes y conectores."""
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return {word for word in re.findall(r"[a-z0-9]+", plain) if word not in STOP_WORDS}


def index_project(project: Path = SAMPLE_PROJECT) -> list[Symbol]:
    """Lee funciones de cada archivo Python sin ejecutar el proyecto de ejemplo."""
    symbols: list[Symbol] = []
    for path in sorted(project.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    Symbol(
                        file=path.relative_to(project).as_posix(),
                        line=node.lineno,
                        name=node.name,
                        description=(ast.get_docstring(node) or "").split("\n", 1)[0],
                    )
                )
    return symbols


def search(question: str, symbols: list[Symbol]) -> list[Symbol]:
    """Ordena coincidencias; es una base simple que luego podremos comparar con IA."""
    query = words(question)

    def score(symbol: Symbol) -> int:
        name_words = words(symbol.name.replace("_", " "))
        description_words = words(symbol.description)
        file_words = words(symbol.file.replace("_", " ").replace(".py", ""))
        return 3 * len(query & name_words) + 2 * len(query & description_words) + len(query & file_words)

    ranked = sorted(symbols, key=lambda symbol: (-score(symbol), symbol.file, symbol.line))
    return [symbol for symbol in ranked if score(symbol) > 0]


def ask(question: str) -> None:
    matches = search(question, index_project())
    if not matches:
        print("No encontré una función relacionada. Probá con otras palabras.")
        return
    best = matches[0]
    print(f"Mejor coincidencia: {best.description}")
    print(f"Fuente: sample_project/{best.file}:{best.line} ({best.name})")


def evaluate() -> None:
    """Comprueba si la primera coincidencia apunta al símbolo esperado."""
    cases = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))
    symbols = index_project()
    correct = 0
    for number, case in enumerate(cases, start=1):
        matches = search(case["question"], symbols)
        best = matches[0] if matches else None
        found = f"{best.file}:{best.name}" if best else "sin coincidencia"
        expected = f"{case['expected_file']}:{case['expected_symbol']}"
        passed = found == expected
        correct += passed
        print(f"{number:2}. {'OK' if passed else 'FALLÓ'} — {case['question']}")
        if not passed:
            print(f"    Esperado: {expected} | Encontrado: {found}")
    print(f"Resultado: {correct}/{len(cases)} ubicaciones correctas")


def main() -> None:
    parser = argparse.ArgumentParser(description="Explorador de un repositorio de ejemplo")
    commands = parser.add_subparsers(dest="command", required=True)
    ask_command = commands.add_parser("ask", help="Busca una respuesta con evidencia")
    ask_command.add_argument("question", help="Pregunta sobre el código")
    commands.add_parser("evaluate", help="Ejecuta las diez preguntas de evaluación")
    args = parser.parse_args()
    if args.command == "ask":
        ask(args.question)
    else:
        evaluate()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
