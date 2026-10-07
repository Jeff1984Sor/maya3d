from pydantic import BaseModel, ConfigDict


class BrandColors(BaseModel):
    light: dict[str, str]
    dark: dict[str, str]


class BrandPublic(BaseModel):
    """Só o que é seguro expor: voz da marca, CNPJ e razão social ficam internos."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    tagline: str | None
    logo_light_url: str | None
    logo_dark_url: str | None
    favicon_url: str | None
    colors: BrandColors
    fonts: dict[str, str]
    domain: str | None
    contact_email: str | None
    contact_whatsapp: str | None
    social: dict[str, str]
