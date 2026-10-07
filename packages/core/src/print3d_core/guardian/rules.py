"""Regras padrão do Guardião (spec seções 2 e 2.1 a 2.7). Versionadas e testadas aqui;
o admin acrescenta ou remove termos por cima (tabela guardian_term_overrides).

Na dúvida, descarta. Falso positivo custa um produto; falso negativo pode custar a conta
no marketplace ou um processo.
"""

from dataclasses import dataclass, field

from print3d_core.niches import Niche


@dataclass(frozen=True)
class TermRule:
    code: str
    terms: tuple[str, ...]
    message: str
    niches: frozenset[str] | None = None  # None = vale para todos os nichos
    unless_any: tuple[str, ...] = ()  # exceções: se o texto tiver um destes, não bloqueia
    licensable: bool = False  # uma License vigente cobrindo o termo libera


@dataclass(frozen=True)
class ComboRule:
    """Bloqueia quando aparecem termos dos DOIS grupos (ex.: "logo" + "santuário")."""

    code: str
    any_of: tuple[str, ...]
    and_any_of: tuple[str, ...]
    message: str
    niches: frozenset[str] | None = None


@dataclass(frozen=True)
class DisclaimerRule:
    """Não bloqueia: exige um aviso no anúncio."""

    code: str
    terms: tuple[str, ...]
    disclaimer: str
    niches: frozenset[str] | None = None


def _n(*niches: Niche) -> frozenset[str]:
    return frozenset(n.value for n in niches)


FRANCHISES = (
    "disney",
    "pixar",
    "marvel",
    "dc comics",
    "pokemon",
    "pikachu",
    "nintendo",
    "super mario",
    "star wars",
    "hello kitty",
    "sanrio",
    "kuromi",
    "patrulha canina",
    "paw patrol",
    "barbie",
    "hot wheels",
    "minecraft",
    "roblox",
    "fortnite",
    "among us",
    "harry potter",
    "batman",
    "superman",
    "homem aranha",
    "spider man",
    "spiderman",
    "homem de ferro",
    "capitao america",
    "hulk",
    "mickey",
    "minnie",
    "frozen",
    "toy story",
    "shrek",
    "minions",
    "transformers",
    "sonic",
    "naruto",
    "dragon ball",
    "bluey",
    "peppa pig",
    "galinha pintadinha",
    "turma da monica",
    "stitch",
    "my little pony",
    "lol surprise",
    "baby shark",
    "bob esponja",
)
FAMOUS_BRANDS = (
    "lego",
    "playmobil",
    "crossfit",
    "coca cola",
    "pepsi",
    "nike",
    "adidas",
    "puma",
    "mcdonalds",
    "starbucks",
    "red bull",
    "ferrari",
    "lamborghini",
    "porsche",
    "harley davidson",
    "chanel",
    "louis vuitton",
    "gucci",
    "playstation",
    "xbox",
)
FOOTBALL_CLUBS = (
    "corinthians",
    "palmeiras",
    "flamengo",
    "fluminense",
    "botafogo",
    "vasco da gama",
    "gremio",
    "atletico mineiro",
    "cruzeiro esporte clube",
    "spfc",
    "santos fc",
    "real madrid",
    "fc barcelona",
    "juventus",
    "manchester united",
    "chelsea",
    "cbf",
    "selecao brasileira",
)
# Marcas que podem aparecer SÓ como compatibilidade ("compatível com Gol G5 2009-2012").
COMPAT_BRANDS = (
    "volkswagen",
    "vw",
    "fiat",
    "chevrolet",
    "ford",
    "toyota",
    "honda",
    "hyundai",
    "renault",
    "jeep",
    "nissan",
    "peugeot",
    "citroen",
    "bmw",
    "mercedes",
    "audi",
    "kia",
    "mitsubishi",
    "iphone",
    "apple",
    "samsung",
    "galaxy",
    "motorola",
    "xiaomi",
    "redmi",
)
COMPAT_PHRASES = ("compativel com", "compativel", "para", "serve no", "serve em")
OFFICIAL_CLAIMS = ("original", "oficial", "genuino", "genuina", "licenciado oficial")
EMBLEM_TERMS = ("logo", "logotipo", "emblema", "escudo", "brasao", "simbolo da marca")
PROFANITY = (
    "porra",
    "caralho",
    "merda",
    "puta",
    "puto",
    "foda",
    "fodase",
    "foda se",
    "buceta",
    "cu",
    "cuzao",
    "viado",
    "arrombado",
    "desgracado",
    "otario",
    "vagabunda",
    "fdp",
    "pqp",
    "vsf",
    "vtnc",
    "bosta",
    "cacete",
    "xota",
)  # sem palavras ambíguas que também são sobrenomes/animais (Pinto, rola, piranha)

TERM_RULES: tuple[TermRule, ...] = (
    TermRule(
        "franquia", FRANCHISES, "personagem/franquia de terceiros sem licença", licensable=True
    ),
    TermRule("marca_famosa", FAMOUS_BRANDS, "marca registrada de terceiros", licensable=True),
    TermRule(
        "time_de_futebol", FOOTBALL_CLUBS, "clube/escudo de futebol sem licença", licensable=True
    ),
    TermRule(
        "blocos_de_montar",
        ("minifigura", "minifig"),
        "não reproduzir minifiguras de blocos de montar",
    ),
    TermRule(
        "cristo_redentor",
        ("cristo redentor",),
        "imagem do Cristo Redentor exige licença da Arquidiocese do Rio",
        licensable=True,
    ),
    TermRule(
        "pessoa_real",
        ("papa", "papa francisco", "papa leao", "joao paulo ii", "bento xvi"),
        "imagem de papa/pessoa real",
    ),
    TermRule(
        "ofensa_religiosa",
        ("caricatura", "satira", "zoeira", "deboche", "meme", "engracado", "zueira"),
        "conteúdo caricato ou de deboche em item de fé",
        niches=_n(Niche.RELIGIOSO),
    ),
    TermRule(
        "seguranca_automotiva",
        (
            "freio",
            "pastilha de freio",
            "disco de freio",
            "pinca de freio",
            "direcao",
            "barra de direcao",
            "coluna de direcao",
            "volante",
            "suspensao",
            "amortecedor",
            "cinto de seguranca",
            "fivela do cinto",
            "airbag",
            "parafuso de roda",
            "porca de roda",
            "cubo de roda",
            "combustivel",
            "tanque",
            "bico injetor",
            "pedal",
            "peca do motor",
            "componente do motor",
            "coxim",
            "correia",
        ),
        "peça de segurança veicular: proibida",
        niches=_n(Niche.AUTOMOTIVO),
    ),
    TermRule(
        "seguranca_fitness",
        (
            "anilha",
            "trava de anilha",
            "clipe de anilha",
            "presilha de anilha",
            "pegada",
            "puxador",
            "gancho de carga",
            "mola",
            "apoio de pe",
            "apoio de mao",
            "peca estrutural",
            "suporte de peso",
        ),
        "peça que suporta carga ou o corpo: proibida",
        niches=_n(Niche.FITNESS),
        unless_any=(
            "chaveiro",
            "miniatura",
            "decorativo",
            "decorativa",
            "medalha",
            "trofeu",
            "porta medalha",
        ),
    ),
    TermRule(
        "fogo",
        (
            "vela",
            "porta vela",
            "castical",
            "candelabro",
            "lamparina",
            "incensario",
            "lamparina a oleo",
        ),
        "plástico perto de chama deforma e pode pegar fogo: só 'para vela LED'",
        unless_any=("led",),
    ),
    TermRule(
        "forma_de_alimento",
        (
            "forma de chocolate",
            "molde de chocolate",
            "forma para chocolate",
            "forma de bolo",
            "molde de bolo",
            "forma de gelo",
            "forma de bombom",
            "molde de bombom",
        ),
        "forma impressa em contato com alimento: proibida",
    ),
    TermRule(
        "alimento_sem_aviso",
        (
            "cestinha",
            "porta bombom",
            "porta ovos",
            "porta doces",
            "bomboniere",
            "caixa de doces",
            "pote de doces",
        ),
        "recipiente de comida precisa dizer 'para alimentos embalados'",
        unless_any=("embalado", "embalados", "embalada", "embaladas"),
    ),
    TermRule(
        "brinquedo",
        ("brinquedo",),
        "não anunciar como brinquedo (exige certificação Inmetro)",
        unless_any=("nao e brinquedo", "nao e um brinquedo", "nao brinquedo"),
    ),
    TermRule("palavrao", PROFANITY, "texto com palavrão"),
    # Turma própria de cãezinhos não pode lembrar franquias de cachorrinhos de resgate.
    TermRule(
        "lembra_franquia",
        ("chase", "marshall", "skye", "rubble", "zuma", "everest", "ryder", "patrulha"),
        "nome lembra personagem de franquia infantil",
        niches=_n(Niche.INFANTIL),
    ),
)

COMBO_RULES: tuple[ComboRule, ...] = (
    ComboRule(
        "marca_de_instituicao_religiosa",
        EMBLEM_TERMS,
        (
            "santuario",
            "diocese",
            "arquidiocese",
            "paroquia",
            "congregacao",
            "cnbb",
            "renovacao carismatica",
            "cancao nova",
            "basilica",
        ),
        "logo/brasão de santuário, diocese ou movimento",
    ),
    ComboRule(
        "emblema_de_fabricante",
        EMBLEM_TERMS,
        COMPAT_BRANDS,
        "emblema/logo de montadora ou fabricante",
    ),
    ComboRule(
        "lembra_franquia_visual",
        ("dalmata",),
        ("bombeiro", "bombeira"),
        "dálmata bombeiro lembra personagem de franquia",
        niches=_n(Niche.INFANTIL),
    ),
)

KIDS_DISCLAIMER = (
    "Não é brinquedo. Item decorativo/colecionável com peças pequenas: "
    "mantenha longe de crianças menores de 3 anos."
)
DISCLAIMER_RULES: tuple[DisclaimerRule, ...] = (
    DisclaimerRule(
        "ima",
        ("ima", "imas", "magnetico", "magnetica"),
        "Contém ímãs: mantenha longe de crianças pequenas.",
    ),
    DisclaimerRule(
        "cortador",
        ("cortador de biscoito", "cortador de massa"),
        "Uso rápido: lave após o uso; não indicado para contato prolongado com alimento.",
    ),
    DisclaimerRule(
        "vela_led", ("vela", "porta vela", "castical"), "Uso exclusivo com vela LED (nunca chama)."
    ),
    DisclaimerRule(
        "impressao_3d",
        (),
        "Peça feita em impressão 3D: linhas de camada podem ser visíveis.",
        niches=_n(Niche.RELIGIOSO),
    ),
)

# Linhas de licença aceitas (spec 2 — Guardião, item 1). Qualquer outra coisa: descarta.
LICENSE_BLOCK_MARKERS = (
    "nc",
    "non commercial",
    "noncommercial",
    "nao comercial",
    "uso pessoal",
    "personal use",
    "standard digital file",
    "sdfl",
    "nd",
    "no derivatives",
    "sa",
    "share alike",
    "all rights",
    "todos os direitos",
)


@dataclass(frozen=True)
class MaterialRule:
    code: str
    niches: frozenset[str]
    forbidden_kinds: frozenset[str]
    message: str
    when_any: tuple[str, ...] = ()  # vazio = sempre no nicho
    required_kinds: frozenset[str] = field(default_factory=frozenset)


MATERIAL_RULES: tuple[MaterialRule, ...] = (
    MaterialRule(
        "pla_no_carro",
        _n(Niche.AUTOMOTIVO),
        frozenset({"PLA"}),
        "PLA deforma no carro (60-70 °C ao sol): use PETG ou ASA",
    ),
    MaterialRule(
        "exposto_ao_sol",
        _n(Niche.AUTOMOTIVO),
        frozenset({"PLA", "PETG"}),
        "peça exposta ao sol (painel, tampa externa) exige ASA",
        when_any=("painel", "exposto ao sol", "parabrisa", "tampa externa"),
        required_kinds=frozenset({"ASA"}),
    ),
    MaterialRule(
        "suor_umidade",
        _n(Niche.FITNESS),
        frozenset({"PLA"}),
        "ambiente quente/úmido ou com suor exige no mínimo PETG",
        when_any=("suor", "umido", "banheiro", "vestiario", "garrafa", "squeeze"),
    ),
)
