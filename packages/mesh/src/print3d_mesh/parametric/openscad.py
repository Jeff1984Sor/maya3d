"""Executa o OpenSCAD em modo linha de comando (sem tela), com limite de tempo.

O código SCAD é gerado por nós a partir de parâmetros validados (nunca texto livre do cliente
interpolado sem escape — ver `scad_string`).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path


class OpenScadError(Exception):
    pass


def scad_string(value: str) -> str:
    """Literal de string SCAD seguro: escapa barra e aspas, remove quebras de linha."""
    cleaned = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + " ".join(cleaned.splitlines()) + '"'


class OpenScadRunner:
    def __init__(self, binary: str = "openscad", timeout_s: int = 120) -> None:
        self.binary = binary
        self.timeout_s = timeout_s

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def render(self, source: str, out_path: Path) -> Path:
        """Gera um STL a partir do código SCAD. Levanta OpenScadError com a saída do OpenSCAD."""
        if not self.available():
            raise OpenScadError(f"OpenSCAD não encontrado ({self.binary})")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            scad = Path(tmp) / "modelo.scad"
            scad.write_text(source, encoding="utf-8")
            try:
                proc = subprocess.run(  # noqa: S603 — binário fixo, argumentos sem shell
                    [self.binary, "--export-format", "binstl", "-o", str(out_path), str(scad)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise OpenScadError(f"OpenSCAD passou de {self.timeout_s}s") from exc
        if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-8:]
            raise OpenScadError("falha no OpenSCAD: " + " | ".join(tail))
        return out_path
