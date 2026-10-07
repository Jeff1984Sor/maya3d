"""Rotas do painel. Todas exigem X-Admin-Token (ver print3d_api.security)."""

from fastapi import APIRouter, Depends

from print3d_api.models import (
    ChannelFeeBand,
    Customer,
    GuardianTermOverride,
    License,
    Material,
    Niche,
    PackagingBox,
    Printer,
)
from print3d_api.routes.admin import (
    ai,
    costs,
    guardian,
    integrations,
    library,
    mesh,
    orders,
    parametric,
    photo,
    pricing,
    products,
)
from print3d_api.routes.admin.crud import crud_router
from print3d_api.schemas.admin import (
    FeeBandIn,
    FeeBandOut,
    FeeBandPatch,
    MaterialIn,
    MaterialOut,
    MaterialPatch,
    PackagingIn,
    PackagingOut,
    PackagingPatch,
    PrinterIn,
    PrinterOut,
    PrinterPatch,
)
from print3d_api.schemas.governance import (
    LicenseIn,
    LicenseOut,
    LicensePatch,
    NicheIn,
    NicheOut,
    NichePatch,
    TermOverrideIn,
    TermOverrideOut,
    TermOverridePatch,
)
from print3d_api.schemas.orders import CustomerIn, CustomerOut, CustomerPatch
from print3d_api.security import require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])

router.include_router(
    crud_router(
        Material,
        MaterialIn,
        MaterialPatch,
        MaterialOut,
        prefix="/materials",
        tag="admin: materiais",
        order_by=(Material.kind, Material.color_name),
    )
)
router.include_router(
    crud_router(
        Printer, PrinterIn, PrinterPatch, PrinterOut, prefix="/printers", tag="admin: impressoras"
    )
)
router.include_router(
    crud_router(
        PackagingBox,
        PackagingIn,
        PackagingPatch,
        PackagingOut,
        prefix="/packaging",
        tag="admin: embalagens",
    )
)
router.include_router(
    crud_router(
        ChannelFeeBand,
        FeeBandIn,
        FeeBandPatch,
        FeeBandOut,
        prefix="/channel-fees",
        tag="admin: tarifas",
        order_by=(ChannelFeeBand.channel, ChannelFeeBand.min_price),
    )
)
router.include_router(
    crud_router(
        Niche,
        NicheIn,
        NichePatch,
        NicheOut,
        prefix="/niches",
        tag="admin: nichos",
        order_by=(Niche.sort_order, Niche.id),
    )
)
router.include_router(
    crud_router(
        License, LicenseIn, LicensePatch, LicenseOut, prefix="/licenses", tag="admin: licenças"
    )
)
router.include_router(
    crud_router(
        GuardianTermOverride,
        TermOverrideIn,
        TermOverridePatch,
        TermOverrideOut,
        prefix="/guardian/terms",
        tag="admin: guardião e auditoria",
    )
)
router.include_router(costs.router)
router.include_router(pricing.router)
router.include_router(mesh.router)
router.include_router(guardian.router)
router.include_router(parametric.router)
router.include_router(products.router)
router.include_router(orders.router)
router.include_router(ai.router)
router.include_router(photo.router)
router.include_router(integrations.router)
router.include_router(library.router)
router.include_router(
    crud_router(
        Customer,
        CustomerIn,
        CustomerPatch,
        CustomerOut,
        prefix="/customers",
        tag="admin: clientes",
        order_by=(Customer.name,),
    )
)
