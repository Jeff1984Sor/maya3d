import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check_brand", Path(__file__).resolve().parents[1] / "check_brand.py"
)
assert SPEC is not None
assert SPEC.loader is not None
check_brand = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_brand)


def test_padrao_pega_variacoes() -> None:
    for text in ("Maya3D", "maya3d", "MAYA 3D", "maya-3d", "maya_3d"):
        assert check_brand.FORBIDDEN.search(text), text


def test_nao_pega_nomes_neutros() -> None:
    assert not check_brand.FORBIDDEN.search("print3d storefront")


def test_repositorio_esta_limpo() -> None:
    assert check_brand.find_violations() == []
