"""Armazenamento de arquivos (STL, 3MF, renders, fotos). Local hoje; GCS depois, mesma interface."""

from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable


class StorageError(Exception):
    pass


def safe_key(key: str) -> str:
    """Chave relativa sem '..', barra inicial ou caracteres de controle."""
    path = PurePosixPath(key)
    if (
        not key
        or path.is_absolute()
        # confere a chave crua: PurePosixPath normaliza "a//b" e "a/./b" e esconderia o problema
        or any(part in ("", ".", "..") for part in key.split("/"))
        or any(ord(c) < 32 for c in key)
        or "\\" in key
    ):
        raise StorageError(f"chave inválida: {key!r}")
    return str(path)


@runtime_checkable
class Storage(Protocol):
    def local_path(self, key: str) -> Path:
        """Caminho local onde gravar/ler a chave (para ferramentas como OpenSCAD e fatiador)."""
        ...

    def exists(self, key: str) -> bool: ...


class LocalStorage:
    """Disco do servidor (volume docker compartilhado entre API e worker)."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def local_path(self, key: str) -> Path:
        path = (self.root / safe_key(key)).resolve()
        if self.root not in path.parents and path != self.root:
            raise StorageError(f"chave fora do armazenamento: {key!r}")
        return path

    def exists(self, key: str) -> bool:
        return self.local_path(key).is_file()
