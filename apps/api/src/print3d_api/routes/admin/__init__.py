"""Rotas do painel. Todas exigem X-Admin-Token (ver print3d_api.security)."""

from fastapi import APIRouter, Depends

from print3d_api.models import ChannelFeeBand, Material, PackagingBox, Printer
from print3d_api.routes.admin import costs, mesh, pricing
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
router.include_router(costs.router)
router.include_router(pricing.router)
router.include_router(mesh.router)
