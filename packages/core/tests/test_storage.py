from pathlib import Path

import pytest

from print3d_core.storage import LocalStorage, Storage, StorageError, safe_key


@pytest.mark.parametrize(
    "bad", ["", "/etc/passwd", "../segredo", "a/../../b", "a//b", "a\\b", "a/./b", "x\x00y"]
)
def test_chave_insegura(bad: str) -> None:
    with pytest.raises(StorageError):
        safe_key(bad)


def test_chave_valida() -> None:
    assert safe_key("parametric/abc123/completo.stl") == "parametric/abc123/completo.stl"


def test_local_storage(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    assert isinstance(storage, Storage)
    path = storage.local_path("parametric/j1/base.stl")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"solid")
    assert storage.exists("parametric/j1/base.stl")
    assert not storage.exists("parametric/j1/nada.stl")
    with pytest.raises(StorageError):
        storage.local_path("../fora.stl")
