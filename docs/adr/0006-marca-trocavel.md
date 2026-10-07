# 0006 — Marca trocável e guarda automática

- **Status:** Aceita
- **Data:** 2026-10-07

## Contexto
O nome é provisório. Trocar não pode exigir mudança de código nem de infraestrutura.

## Decisão
- Identidade em `brand_settings` (linha única, `CHECK id = 1`), exposta por `GET /v1/brand` **sem campos internos** (voz, CNPJ, razão social).
- Frontends leem a marca no servidor e aplicam o tema via `brandThemeCss`, que aceita apenas tokens conhecidos com valor hex (nada de CSS arbitrário vindo do banco).
- Slugs técnicos neutros: `print3d` (repo, bancos, containers, pacotes).
- `tools/check_brand.py` no CI falha se o nome provisório aparecer no código.
- Itens fora do controle do admin ficam em [troca-de-marca.md](../troca-de-marca.md).

## Consequências
Qualquer texto novo com o nome da loja deve vir de `brand_settings`; o fallback do frontend usa o nome neutro "Print3D".
