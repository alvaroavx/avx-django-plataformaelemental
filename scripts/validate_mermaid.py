#!/usr/bin/env python3
"""Validate Mermaid diagrams embedded in Markdown files under docs/."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_PUPPETEER_CONFIG = REPO_ROOT / "scripts" / "mermaid-puppeteer-config.json"


@dataclass(frozen=True)
class MermaidBlock:
    path: Path
    line_number: int
    content: str


def find_mmdc() -> str | None:
    local_binary = REPO_ROOT / "node_modules" / ".bin" / "mmdc"
    if local_binary.exists():
        return str(local_binary)
    return shutil.which("mmdc")


def iter_markdown_files(root: Path):
    yield from sorted(root.rglob("*.md"))


def extract_mermaid_blocks(path: Path) -> list[MermaidBlock]:
    blocks: list[MermaidBlock] = []
    in_block = False
    start_line = 0
    current: list[str] = []

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not in_block and stripped == "```mermaid":
            in_block = True
            start_line = line_number
            current = []
            continue
        if in_block and stripped == "```":
            blocks.append(MermaidBlock(path=path, line_number=start_line, content="\n".join(current).strip() + "\n"))
            in_block = False
            current = []
            continue
        if in_block:
            current.append(line)

    if in_block:
        raise ValueError(f"{path}:{start_line}: bloque Mermaid sin cierre")

    return blocks


def validate_block(mmdc: str, block: MermaidBlock, output_dir: Path, puppeteer_config: Path) -> subprocess.CompletedProcess:
    relative = block.path.relative_to(REPO_ROOT)
    safe_name = str(relative).replace("/", "__").replace(" ", "_")
    input_path = output_dir / f"{safe_name}__L{block.line_number}.mmd"
    output_path = output_dir / f"{safe_name}__L{block.line_number}.svg"
    input_path.write_text(block.content, encoding="utf-8")

    command = [
        mmdc,
        "--quiet",
        "--puppeteerConfigFile",
        str(puppeteer_config),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]
    return subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Mermaid diagrams embedded in docs/**/*.md")
    parser.add_argument("--docs-dir", default=str(DEFAULT_DOCS_DIR), help="Directory containing Markdown documentation")
    parser.add_argument(
        "--puppeteer-config",
        default=str(DEFAULT_PUPPETEER_CONFIG),
        help="Puppeteer config passed to mmdc",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir).resolve()
    puppeteer_config = Path(args.puppeteer_config).resolve()
    mmdc = find_mmdc()
    if not mmdc:
        print("No se encontro mmdc. Ejecuta `npm install` o instala @mermaid-js/mermaid-cli.", file=sys.stderr)
        return 1
    if not docs_dir.exists():
        print(f"No existe el directorio de documentacion: {docs_dir}", file=sys.stderr)
        return 1
    if not puppeteer_config.exists():
        print(f"No existe la configuracion de Puppeteer: {puppeteer_config}", file=sys.stderr)
        return 1

    blocks: list[MermaidBlock] = []
    for markdown_file in iter_markdown_files(docs_dir):
        try:
            blocks.extend(extract_mermaid_blocks(markdown_file))
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1

    if not blocks:
        print("No se encontraron diagramas Mermaid.")
        return 0

    failures = 0
    with tempfile.TemporaryDirectory(prefix="mermaid-validate-") as temp_dir_name:
        output_dir = Path(temp_dir_name)
        for block in blocks:
            result = validate_block(mmdc, block, output_dir, puppeteer_config)
            if result.returncode != 0:
                failures += 1
                relative = block.path.relative_to(REPO_ROOT)
                print(f"\nFallo Mermaid: {relative}:{block.line_number}", file=sys.stderr)
                if result.stderr:
                    print(result.stderr.strip(), file=sys.stderr)
                if result.stdout:
                    print(result.stdout.strip(), file=sys.stderr)

    if failures:
        print(f"\nDiagramas Mermaid con error: {failures}/{len(blocks)}", file=sys.stderr)
        return 1

    print(f"Diagramas Mermaid validos: {len(blocks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
