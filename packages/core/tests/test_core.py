import pytest

from print3d_core import NICHE_TARGETS, Niche, SalesChannel, TokenVault, TokenVaultError


def test_metas_somam_720_e_cobrem_todos_os_nichos() -> None:
    assert sum(NICHE_TARGETS.values()) == 720
    assert set(NICHE_TARGETS) == set(Niche)


def test_marketplaces() -> None:
    assert SalesChannel.MERCADO_LIVRE.is_marketplace
    assert SalesChannel.SHOPEE.is_marketplace
    assert not SalesChannel.SITE.is_marketplace


def test_vault_roundtrip() -> None:
    vault = TokenVault(TokenVault.generate_key())
    token = vault.encrypt("refresh-abc")
    assert token != "refresh-abc"
    assert vault.decrypt(token) == "refresh-abc"


def test_vault_chave_errada_falha() -> None:
    token = TokenVault(TokenVault.generate_key()).encrypt("x")
    with pytest.raises(TokenVaultError):
        TokenVault(TokenVault.generate_key()).decrypt(token)


def test_vault_chave_invalida() -> None:
    with pytest.raises(TokenVaultError):
        TokenVault("não-é-chave")
