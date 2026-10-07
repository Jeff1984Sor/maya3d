"""Guardião com dados do banco: regras padrão + ajustes do admin + licenças vigentes."""

from collections.abc import Sequence
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import GuardianTermOverride, License, Niche
from print3d_api.schemas.governance import GuardianCheckIn, GuardianCheckOut, ViolationOut
from print3d_api.services import audit
from print3d_core.guardian import (
    DEFAULT_RULESET,
    Decision,
    GuardianInput,
    LicenseGrant,
    Ruleset,
    evaluate,
)


class UnknownNicheError(Exception):
    pass


def build_ruleset(overrides: Sequence[GuardianTermOverride]) -> Ruleset:
    return DEFAULT_RULESET.with_overrides(
        add=[(o.rule_code or "lista_admin", o.term) for o in overrides if o.mode == "add"],
        remove=[(o.rule_code, o.term) for o in overrides if o.mode == "remove"],
    )


def to_grant(lic: License) -> LicenseGrant:
    return LicenseGrant(
        licensor=lic.licensor,
        covered_terms=frozenset(lic.covered_terms),
        valid_from=lic.valid_from,
        valid_until=lic.valid_until,
        channels=frozenset(lic.channels),
        categories=frozenset(lic.categories),
    )


async def decide(session: AsyncSession, req: GuardianCheckIn) -> Decision:
    """Decisão do Guardião com regras do admin e licenças vigentes (sem gravar nada)."""
    niche = await session.scalar(select(Niche).where(Niche.slug == req.niche, Niche.active))
    if niche is None:
        raise UnknownNicheError(f"nicho '{req.niche}' não existe ou está inativo")
    overrides = (await session.scalars(select(GuardianTermOverride))).all()
    licenses = (await session.scalars(select(License).where(License.active))).all()
    return evaluate(
        GuardianInput(**req.model_dump(), licenses=[to_grant(lic) for lic in licenses]),
        build_ruleset(overrides),
    )


async def check(session: AsyncSession, req: GuardianCheckIn) -> GuardianCheckOut:
    decision = await decide(session, req)
    entry = await audit.record(
        session,
        actor="guardiao",
        action="verificacao",
        decision=decision.verdict,
        reason=decision.reason,
        payload={
            "entrada": req.model_dump(),
            "violacoes": [asdict(v) for v in decision.violations],
        },
    )
    await session.commit()

    return GuardianCheckOut(
        verdict=decision.verdict,
        approved=decision.approved,
        violations=[ViolationOut(**asdict(v)) for v in decision.violations],
        disclaimers=list(decision.disclaimers),
        warnings=list(decision.warnings),
        attribution_required=decision.attribution_required,
        age_rating=decision.age_rating,
        audit_id=entry.id,
    )
