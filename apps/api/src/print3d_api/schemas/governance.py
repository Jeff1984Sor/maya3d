from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=40)]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


# --- Nichos ----------------------------------------------------------------------------------
class NicheIn(BaseModel):
    slug: Slug
    name: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    target_count: int = Field(default=0, ge=0)
    voice: str | None = None
    categories: list[str] = []
    sort_order: int = 0
    active: bool = True


class NichePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    target_count: int | None = Field(default=None, ge=0)
    voice: str | None = None
    categories: list[str] | None = None
    sort_order: int | None = None
    active: bool | None = None


class NicheOut(_Out, NicheIn):
    pass


# --- Licenças --------------------------------------------------------------------------------
class LicenseIn(BaseModel):
    licensor: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    covered_terms: list[str] = Field(min_length=1)
    categories: list[str] = []
    channels: list[str] = []
    territory: str | None = None
    valid_from: date
    valid_until: date
    royalty_pct: Decimal | None = Field(default=None, ge=0, lt=1)
    royalty_per_unit: Decimal | None = Field(default=None, ge=0)
    approval_rules: str | None = None
    contract_url: str | None = None
    active: bool = True

    @model_validator(mode="after")
    def _periodo(self) -> Self:
        if self.valid_until < self.valid_from:
            raise ValueError("valid_until antes de valid_from")
        return self


class LicensePatch(BaseModel):
    covered_terms: list[str] | None = None
    categories: list[str] | None = None
    channels: list[str] | None = None
    valid_until: date | None = None
    royalty_pct: Decimal | None = Field(default=None, ge=0, lt=1)
    royalty_per_unit: Decimal | None = Field(default=None, ge=0)
    approval_rules: str | None = None
    contract_url: str | None = None
    active: bool | None = None


class LicenseOut(_Out, LicenseIn):
    pass


# --- Ajustes do Guardião ---------------------------------------------------------------------
class TermOverrideIn(BaseModel):
    term: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    mode: Literal["add", "remove"]
    rule_code: str | None = Field(default=None, max_length=60)
    reason: str | None = None


class TermOverridePatch(BaseModel):
    reason: str | None = None


class TermOverrideOut(_Out, TermOverrideIn):
    pass


# --- Verificação ----------------------------------------------------------------------------
class GuardianCheckIn(BaseModel):
    niche: str
    title: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    description: str = ""
    tags: list[str] = []
    occasions: list[str] = []
    category: str | None = None
    origin: Literal["parametrico", "licenca_comercial", "cc0", "cc_by", "outro"] = "outro"
    license: str | None = None
    author: str | None = None
    attribution_text: str | None = None
    material_kinds: list[str] = []
    customer_text: list[str] = []
    channel: str | None = None


class ViolationOut(BaseModel):
    code: str
    message: str
    evidence: str


class GuardianCheckOut(BaseModel):
    verdict: Literal["aprovado", "bloqueado"]
    approved: bool
    violations: list[ViolationOut]
    disclaimers: list[str]
    warnings: list[str]
    attribution_required: bool
    age_rating: str | None
    audit_id: int


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    actor: str
    action: str
    entity_type: str | None
    entity_id: str | None
    decision: str | None
    reason: str | None
    payload: dict[str, Any]
