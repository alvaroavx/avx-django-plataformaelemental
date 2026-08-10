#!/usr/bin/env python3
"""Valida destinos locales enlazados desde archivos Markdown del repositorio."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "staticfiles"}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.md")
        if not EXCLUDED_PARTS.intersection(path.relative_to(REPO_ROOT).parts)
    )


def normalizar_destino(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    # Los títulos opcionales Markdown se separan por espacio después de la URL.
    return target.split(maxsplit=1)[0]


def destino_local(origen: Path, target: str) -> Path | None:
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or target.startswith(("#", "mailto:")):
        return None
    ruta = unquote(parsed.path)
    if not ruta:
        return None
    if ruta.startswith("/"):
        return REPO_ROOT / ruta.lstrip("/")
    return origen.parent / ruta


def main() -> int:
    errores: list[str] = []
    revisados = 0
    for markdown in markdown_files():
        contenido = markdown.read_text(encoding="utf-8-sig")
        for numero_linea, linea in enumerate(contenido.splitlines(), start=1):
            for match in MARKDOWN_LINK.finditer(linea):
                target = normalizar_destino(match.group("target"))
                destino = destino_local(markdown, target)
                if destino is None:
                    continue
                revisados += 1
                if not destino.resolve(strict=False).exists():
                    origen = markdown.relative_to(REPO_ROOT)
                    errores.append(f"{origen}:{numero_linea}: no existe {target}")

    if errores:
        print("Enlaces locales Markdown inválidos:", file=sys.stderr)
        print("\n".join(errores), file=sys.stderr)
        return 1
    print(f"Enlaces locales Markdown válidos: {revisados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
