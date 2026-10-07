"""Guarda de CI: o nome da marca NUNCA pode aparecer fixo no código (spec seção 0.1).

Varre o código-fonte (não a documentação) atrás de nomes de marca proibidos.
Para trocar a marca basta editar o admin; nenhum arquivo daqui deve mudar.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Marca provisória e variações comuns (maiúsculas, espaço, hífen, underscore).
FORBIDDEN = re.compile(r"maya[\s_-]?3d", re.IGNORECASE)

SCAN_DIRS = ("apps", "packages", "infra", "ops", ".github", "tools")
SCAN_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".css",
    ".json",
    ".yml",
    ".yaml",
    ".sh",
    ".conf",
    ".template",
    ".toml",
    ".env",
    ".service",
    ".timer",
    ".html",
}
SKIP_PARTS = {"node_modules", ".next", ".venv", "__pycache__", "tests"}
SKIP_FILES = {"check_brand.py"}  # este arquivo precisa citar o padrão


def iter_files() -> Iterator[Path]:
    for name in SCAN_DIRS:
        base = ROOT / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if (
                path.is_file()
                and path.suffix in SCAN_SUFFIXES
                and path.name not in SKIP_FILES
                and not SKIP_PARTS.intersection(path.parts)
            ):
                yield path


def find_violations() -> list[str]:
    violations: list[str] = []
    for path in iter_files():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if FORBIDDEN.search(line):
                violations.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:100]}")
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print(
            "Marca fixa encontrada no código (use BrandSettings / brand_settings):", file=sys.stderr
        )
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("check_brand: ok — nenhum nome de marca fixo no código")
    return 0


if __name__ == "__main__":
    sys.exit(main())
