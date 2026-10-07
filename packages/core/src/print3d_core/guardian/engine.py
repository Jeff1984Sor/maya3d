"""Guardião de IP e segurança — etapa determinística (regras).

Substitui a aprovação manual: nenhuma peça é publicada sem passar por TODOS os filtros.
A análise visual dos renders por modelo multimodal (spec item 3) é uma etapa posterior,
que só roda em quem passou aqui.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Literal

from print3d_core.guardian import rules as R
from print3d_core.guardian.text import Searchable, fold
from print3d_core.niches import Niche

Origin = Literal["parametrico", "licenca_comercial", "cc0", "cc_by", "outro"]


@dataclass(frozen=True)
class LicenseGrant:
    """Licença de personagem/marca cadastrada (módulo License, spec 2.6)."""

    licensor: str
    covered_terms: frozenset[str]
    valid_from: date
    valid_until: date
    channels: frozenset[str] = frozenset()  # vazio = todos
    categories: frozenset[str] = frozenset()  # vazio = todas

    def covers(self, term: str, *, today: date, channel: str | None, category: str | None) -> bool:
        return (
            self.valid_from <= today <= self.valid_until
            and fold(term) in {fold(t) for t in self.covered_terms}
            and (not self.channels or channel is None or channel in self.channels)
            and (not self.categories or category is None or category in self.categories)
        )


@dataclass(frozen=True)
class GuardianInput:
    niche: str
    title: str
    description: str = ""
    tags: Sequence[str] = ()
    occasions: Sequence[str] = ()
    category: str | None = None
    origin: Origin = "outro"
    license: str | None = None
    author: str | None = None
    attribution_text: str | None = None
    material_kinds: Sequence[str] = ()
    customer_text: Sequence[str] = ()  # nome digitado no chaveiro, frase da placa...
    channel: str | None = None
    licenses: Sequence[LicenseGrant] = ()
    today: date = field(default_factory=date.today)


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    evidence: str = ""


@dataclass(frozen=True)
class Decision:
    violations: tuple[Violation, ...]
    disclaimers: tuple[str, ...]
    warnings: tuple[str, ...]
    attribution_required: bool
    age_rating: str | None

    @property
    def approved(self) -> bool:
        return not self.violations

    @property
    def verdict(self) -> Literal["aprovado", "bloqueado"]:
        return "aprovado" if self.approved else "bloqueado"

    @property
    def reason(self) -> str:
        return "; ".join(f"{v.code}: {v.message}" for v in self.violations) or "ok"


@dataclass(frozen=True)
class Ruleset:
    term_rules: tuple[R.TermRule, ...] = R.TERM_RULES
    combo_rules: tuple[R.ComboRule, ...] = R.COMBO_RULES
    disclaimer_rules: tuple[R.DisclaimerRule, ...] = R.DISCLAIMER_RULES
    material_rules: tuple[R.MaterialRule, ...] = R.MATERIAL_RULES

    def with_overrides(
        self, *, add: Iterable[tuple[str, str]] = (), remove: Iterable[tuple[str | None, str]] = ()
    ) -> "Ruleset":
        """add: (código da regra, termo). Código desconhecido vai para a regra 'lista_admin'.
        remove: (código ou None = todas, termo)."""
        removed = [(c, fold(t)) for c, t in remove]
        extra: dict[str, list[str]] = {}
        for code, term in add:
            extra.setdefault(code, []).append(term)

        def keep(code: str, term: str) -> bool:
            return not any(fold(term) == t and (c is None or c == code) for c, t in removed)

        known = {r.code for r in self.term_rules}
        rules = [
            replace(
                r, terms=tuple(t for t in (*r.terms, *extra.get(r.code, ())) if keep(r.code, t))
            )
            for r in self.term_rules
        ]
        admin_terms = [t for c, ts in extra.items() if c not in known for t in ts]
        if admin_terms:
            rules.append(
                R.TermRule(
                    "lista_admin", tuple(admin_terms), "termo bloqueado no admin", licensable=True
                )
            )
        return replace(self, term_rules=tuple(rules))


DEFAULT_RULESET = Ruleset()


def classify_license(origin: Origin, license_text: str | None) -> str:
    """'proprio' | 'comercial' | 'cc0' | 'cc_by' | 'bloqueada' | 'desconhecida'."""
    if origin == "parametrico":
        return "proprio"
    text = Searchable.of(license_text or "")
    if not license_text or not license_text.strip():
        return "desconhecida"
    if text.first(R.LICENSE_BLOCK_MARKERS):
        return "bloqueada"
    if text.first(("cc0", "cc 0", "dominio publico", "public domain")):
        return "cc0"
    if text.first(("cc by", "creative commons attribution", "ccby")):
        return "cc_by"
    if origin == "licenca_comercial" or text.first(
        ("licenca comercial", "commercial license", "uso comercial", "commercial use")
    ):
        return "comercial"
    return "desconhecida"


def _applies(niches: frozenset[str] | None, niche: str) -> bool:
    return niches is None or niche in niches


def evaluate(item: GuardianInput, ruleset: Ruleset = DEFAULT_RULESET) -> Decision:
    violations: list[Violation] = []
    disclaimers: list[str] = []
    warnings: list[str] = []
    text = Searchable.of(
        item.title,
        item.description,
        " ".join(item.tags),
        " ".join(item.occasions),
        " ".join(item.customer_text),
    )

    # 1. Licença do modelo 3D
    kind = classify_license(item.origin, item.license)
    attribution_required = kind == "cc_by"
    if kind in ("bloqueada", "desconhecida"):
        violations.append(
            Violation(
                "licenca",
                f"licença {kind}: só CC0, CC BY, comercial ou paramétrico próprio",
                item.license or "",
            )
        )
    if attribution_required and not (item.attribution_text or item.author):
        violations.append(Violation("atribuicao", "CC BY exige autor/atribuição no anúncio"))

    # 2. Termos proibidos (com exceções e licenças)
    for rule in ruleset.term_rules:
        if not _applies(rule.niches, item.niche):
            continue
        hit = text.first(rule.terms)
        if hit is None or (rule.unless_any and text.first(rule.unless_any)):
            continue
        if rule.licensable and any(
            g.covers(hit, today=item.today, channel=item.channel, category=item.category)
            for g in item.licenses
        ):
            warnings.append(f"'{hit}' liberado por licença vigente")
            continue
        violations.append(Violation(rule.code, rule.message, hit))

    for combo in ruleset.combo_rules:
        if not _applies(combo.niches, item.niche):
            continue
        a, b = text.first(combo.any_of), text.first(combo.and_any_of)
        if a and b:
            violations.append(Violation(combo.code, combo.message, f"{a} + {b}"))

    # 3. Marcas de carro/celular: só como compatibilidade, nunca como original/oficial
    brand = text.first(R.COMPAT_BRANDS)
    if brand:
        compat_niche = item.niche in (Niche.AUTOMOTIVO.value, Niche.CELULAR.value)
        if not compat_niche:
            violations.append(
                Violation(
                    "marca_fora_de_contexto",
                    "marca de fabricante fora de anúncio de compatibilidade",
                    brand,
                )
            )
        elif not text.first(R.COMPAT_PHRASES):
            violations.append(
                Violation(
                    "marca_sem_compatibilidade",
                    "use 'compatível com <marca> <modelo> <anos>'",
                    brand,
                )
            )
        if text.first(R.OFFICIAL_CLAIMS):
            violations.append(
                Violation(
                    "falsa_originalidade", "não sugerir peça original/oficial do fabricante", brand
                )
            )

    # 4. Material mínimo por uso
    kinds = {k.upper() for k in item.material_kinds}
    for mrule in ruleset.material_rules:
        if not _applies(mrule.niches, item.niche) or not kinds:
            continue
        if mrule.when_any and not text.first(mrule.when_any):
            continue
        bad = kinds & mrule.forbidden_kinds
        missing_required = mrule.required_kinds and not (kinds & mrule.required_kinds)
        if bad or missing_required:
            violations.append(Violation(mrule.code, mrule.message, ",".join(sorted(kinds))))

    # 5. Avisos obrigatórios e classificação etária
    for drule in ruleset.disclaimer_rules:
        if _applies(drule.niches, item.niche) and (not drule.terms or text.first(drule.terms)):
            disclaimers.append(drule.disclaimer)
    kids = item.niche == Niche.INFANTIL.value or text.first(
        ("dia das criancas", "infantil", "crianca", "criancas")
    )
    age_rating = "14+" if kids else None
    if kids:
        disclaimers.append(R.KIDS_DISCLAIMER)

    return Decision(
        violations=tuple(violations),
        disclaimers=tuple(dict.fromkeys(disclaimers)),
        warnings=tuple(warnings),
        attribution_required=attribution_required,
        age_rating=age_rating,
    )


def material_available(min_material: str | None, printable_kinds: Iterable[str]) -> bool:
    """Produto com material mínimo (ex.: ASA) só é publicável se alguma impressora ativa o imprime.
    Quando uma impressora capaz for cadastrada, o produto é liberado automaticamente."""
    return min_material is None or min_material.upper() in {k.upper() for k in printable_kinds}
