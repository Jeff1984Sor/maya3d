"""Evals do Guardião (spec, Fase 2): casos que DEVEM ser bloqueados e casos que DEVEM passar.

Adicionar um caso aqui é a forma de corrigir um falso positivo/negativo achado em produção.
"""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from print3d_core.guardian import GuardianInput, LicenseGrant, evaluate

TODAY = date(2026, 10, 7)
OK_LICENSE: dict[str, Any] = {"origin": "parametrico", "license": None}


def item(niche: str, title: str, **over: Any) -> GuardianInput:
    base: dict[str, Any] = {"niche": niche, "title": title, "today": TODAY, **OK_LICENSE}
    base.update(over)
    return GuardianInput(**base)


# (id, entrada, código de regra que deve disparar)
MUST_BLOCK: list[tuple[str, GuardianInput, str]] = [
    (
        "cristo redentor sem licença",
        item("religioso", "Imagem Cristo Redentor 20cm"),
        "cristo_redentor",
    ),
    (
        "logo de santuário",
        item("religioso", "Placa com logo do Santuário Nacional"),
        "marca_de_instituicao_religiosa",
    ),
    ("papa", item("religioso", "Busto do Papa Francisco"), "pessoa_real"),
    (
        "porta-vela de chama em PLA",
        item("religioso", "Porta-vela Nossa Senhora", material_kinds=["PLA"]),
        "fogo",
    ),
    (
        "emblema de montadora",
        item("automotivo", "Emblema VW para grade compatível com Gol", material_kinds=["ASA"]),
        "emblema_de_fabricante",
    ),
    (
        "peça de freio",
        item("automotivo", "Pastilha de freio compatível com Uno", material_kinds=["PETG"]),
        "seguranca_automotiva",
    ),
    (
        "painel em PLA",
        item(
            "automotivo", "Tampa do painel compatível com Gol G5 2009-2012", material_kinds=["PLA"]
        ),
        "pla_no_carro",
    ),
    (
        "painel em PETG (sol exige ASA)",
        item("automotivo", "Tampa do painel compatível com Gol G5", material_kinds=["PETG"]),
        "exposto_ao_sol",
    ),
    (
        "personagem em Dia das Crianças",
        item(
            "datas-comemorativas",
            "Luminária Patrulha Canina com nome",
            occasions=["dia das criancas"],
        ),
        "franquia",
    ),
    ("personagem em Natal", item("datas-comemorativas", "Enfeite de árvore do Mickey"), "franquia"),
    (
        "forma de chocolate",
        item("datas-comemorativas", "Forma de chocolate para Páscoa"),
        "forma_de_alimento",
    ),
    ("CrossFit no título", item("fitness", "Medalha CrossFit Open 2026"), "marca_famosa"),
    ("crossfit disfarçado", item("fitness", "Troféu C-R-O-S-S-F-I-T campeonato"), "marca_famosa"),
    (
        "trava de anilha",
        item("fitness", "Trava de anilha para barra olímpica"),
        "seguranca_fitness",
    ),
    (
        "chaveiro com palavrão",
        item("chaveiros", "Chaveiro letra + nome", customer_text=["porra"]),
        "palavrao",
    ),
    (
        "chaveiro com marca",
        item("chaveiros", "Chaveiro letra N", customer_text=["Nike"]),
        "marca_famosa",
    ),
    (
        "chaveiro com time",
        item("chaveiros", "Chaveiro letra C", customer_text=["Corinthians"]),
        "time_de_futebol",
    ),
    (
        "cãozinho parecido com franquia (nome)",
        item("infantil", "Cãozinho bombeiro Marshall"),
        "lembra_franquia",
    ),
    (
        "cãozinho parecido com franquia (visual)",
        item("infantil", "Dálmata bombeiro herói"),
        "lembra_franquia_visual",
    ),
    (
        "personagem com licença vencida",
        item(
            "infantil",
            "Topo de bolo Bluey",
            licenses=[
                LicenseGrant(
                    "Licenciante X", frozenset({"bluey"}), date(2025, 1, 1), date(2026, 1, 1)
                )
            ],
        ),
        "franquia",
    ),
    ("lego", item("brindes", "Peças compatíveis com LEGO"), "marca_famosa"),
    ("minifigura", item("brindes", "Minifigura personalizada do noivo"), "blocos_de_montar"),
    ("anunciado como brinquedo", item("infantil", "Brinquedo cãozinho herói"), "brinquedo"),
    (
        "licença NC",
        item(
            "religioso",
            "Santo Antônio 12cm",
            origin="cc_by",
            license="CC BY-NC 4.0",
            author="Fulano",
        ),
        "licenca",
    ),
    (
        "licença desconhecida",
        item("religioso", "Santa Rita 12cm", origin="outro", license="free"),
        "licenca",
    ),
    (
        "CC BY sem atribuição",
        item("religioso", "São Jorge 15cm", origin="cc_by", license="CC BY 4.0"),
        "atribuicao",
    ),
    (
        "marca de carro fora de compatibilidade",
        item("automotivo", "Porta-copos Fiat", material_kinds=["PETG"]),
        "marca_sem_compatibilidade",
    ),
    (
        "peça original",
        item("automotivo", "Botão original compatível com Fiat Uno", material_kinds=["ASA"]),
        "falsa_originalidade",
    ),
    (
        "cestinha sem aviso de embalado",
        item("datas-comemorativas", "Cestinha de coelho para bombons"),
        "alimento_sem_aviso",
    ),
    ("caricatura religiosa", item("religioso", "Meme de santo engraçado"), "ofensa_religiosa"),
    ("leetspeak", item("brindes", "Chaveiro p0kem0n"), "franquia"),
]

MUST_PASS: list[tuple[str, GuardianInput]] = [
    (
        "Nossa Senhora CC BY com atribuição",
        item(
            "religioso",
            "Nossa Senhora Aparecida 15cm manto azul",
            origin="cc_by",
            license="CC BY 4.0",
            author="Designer Y",
        ),
    ),
    ("cruz de São Bento", item("religioso", "Cruz de parede São Bento com nome")),
    ("presépio", item("religioso", "Presépio minimalista com nome da família")),
    ("placa de oração", item("religioso", "Placa Pai Nosso para porta")),
    ("vela LED", item("datas-comemorativas", "Luminária de Natal para vela LED")),
    (
        "suporte iPhone",
        item("celular", "Suporte de mesa compatível com iPhone 15", material_kinds=["PETG"]),
    ),
    (
        "botão compatível",
        item(
            "automotivo",
            "Botão do vidro compatível com VW Gol G5 2009-2012",
            material_kinds=["ASA"],
        ),
    ),
    (
        "puxador automotivo (não é fitness)",
        item("automotivo", "Puxador de porta compatível com Fiat Uno 2010", material_kinds=["ASA"]),
    ),
    (
        "chaveiro com nome",
        item("chaveiros", "Chaveiro letra J com nome", customer_text=["Jefferson"]),
    ),
    ("colégio não casa 'lego'", item("brindes", "Lembrança de formatura do Colégio São José")),
    ("chaveiro de kettlebell", item("fitness", "Chaveiro de kettlebell personalizado")),
    ("miniatura de anilha", item("fitness", "Chaveiro miniatura de anilha com nome")),
    ("medalha de cross training", item("fitness", "Medalha de cross training do box")),
    (
        "cestinha com aviso",
        item(
            "datas-comemorativas",
            "Cestinha de Páscoa",
            description="Para bombons e ovos embalados.",
        ),
    ),
    ("porta-joias", item("caixas", "Porta-joias redondo com nome")),
    ("Papai Noel não é papa", item("datas-comemorativas", "Papai Noel decorativo desenho próprio")),
    ("cachorrinho original", item("infantil", "Cãozinho construtor Tobias, colecionável")),
    (
        "personagem com licença vigente",
        item(
            "infantil",
            "Topo de bolo Bluey",
            channel="site",
            licenses=[
                LicenseGrant(
                    "Licenciante X", frozenset({"bluey"}), date(2026, 1, 1), date(2027, 1, 1)
                )
            ],
        ),
    ),
    (
        "Cristo Redentor com licença",
        item(
            "religioso",
            "Cristo Redentor 20cm",
            licenses=[
                LicenseGrant(
                    "Arquidiocese",
                    frozenset({"cristo redentor"}),
                    date(2026, 1, 1),
                    date(2027, 12, 31),
                )
            ],
        ),
    ),
    (
        "licença comercial",
        item(
            "religioso",
            "Santa Teresinha 12cm",
            origin="licenca_comercial",
            license="Licença comercial (pacote comprado)",
        ),
    ),
]


@pytest.mark.parametrize(("case", "entrada", "codigo"), MUST_BLOCK, ids=[c[0] for c in MUST_BLOCK])
def test_deve_bloquear(case: str, entrada: GuardianInput, codigo: str) -> None:
    decision = evaluate(entrada)
    assert not decision.approved, case
    assert codigo in {v.code for v in decision.violations}, decision.reason


@pytest.mark.parametrize(("case", "entrada"), MUST_PASS, ids=[c[0] for c in MUST_PASS])
def test_deve_passar(case: str, entrada: GuardianInput) -> None:
    decision = evaluate(entrada)
    assert decision.approved, f"{case}: {decision.reason}"


def test_avisos_obrigatorios() -> None:
    d = evaluate(item("caixas", "Caixa presente com tampa de ímã"))
    assert d.approved
    assert any("ímã" in x for x in d.disclaimers)

    d = evaluate(item("religioso", "Imagem São Francisco"))
    assert any("impressão 3D" in x for x in d.disclaimers)


def test_infantil_recebe_14_mais_e_aviso() -> None:
    d = evaluate(item("infantil", "Cãozinho piloto colecionável"))
    assert d.age_rating == "14+"
    assert any("Não é brinquedo" in x for x in d.disclaimers)


def test_cc_by_marca_atribuicao() -> None:
    d = evaluate(item("religioso", "Santa Luzia", origin="cc_by", license="CC-BY 4.0", author="A"))
    assert d.approved
    assert d.attribution_required


def test_licenca_fora_do_canal_nao_libera() -> None:
    grant = LicenseGrant(
        "X", frozenset({"bluey"}), date(2026, 1, 1), date(2027, 1, 1), channels=frozenset({"site"})
    )
    d = evaluate(item("infantil", "Topo Bluey", channel="mercadolivre", licenses=[grant]))
    assert not d.approved


def test_overrides_do_admin() -> None:
    from print3d_core.guardian import DEFAULT_RULESET

    rs = DEFAULT_RULESET.with_overrides(
        add=[("qualquer", "marca nova xyz")], remove=[(None, "mola")]
    )
    assert not evaluate(item("brindes", "Chaveiro Marca Nova XYZ"), rs).approved
    assert evaluate(item("fitness", "Mola de reformer"), rs).approved
    # sem override, 'mola' no fitness bloqueia
    assert not evaluate(item("fitness", "Mola de reformer"), DEFAULT_RULESET).approved


def test_entrada_imutavel_reutilizavel() -> None:
    base = item("brindes", "Porta-caneta com nome")
    assert evaluate(base).approved
    assert not evaluate(replace(base, title="Porta-caneta Disney")).approved
