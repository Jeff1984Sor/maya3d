from decimal import Decimal

import pytest
from pydantic import ValidationError

from print3d_channels import ChannelProvider, ListingDraft, ListingResult, ListingStatus
from print3d_core import SalesChannel


class _Fake:
    channel = SalesChannel.SITE

    async def publish(self, draft: ListingDraft) -> ListingResult:
        return ListingResult(external_id="1", status=ListingStatus.ACTIVE)

    async def update_price_and_stock(
        self, external_id: str, *, price: Decimal, stock: int
    ) -> ListingResult:
        return ListingResult(external_id=external_id, status=ListingStatus.ACTIVE)

    async def pause(self, external_id: str) -> ListingResult:
        return ListingResult(external_id=external_id, status=ListingStatus.PAUSED)


def test_fake_satisfaz_contrato() -> None:
    assert isinstance(_Fake(), ChannelProvider)


def test_preco_precisa_ser_positivo() -> None:
    with pytest.raises(ValidationError):
        ListingDraft(
            variant_id="v", title="t", description="d", price=Decimal("0"), stock=1,
            image_urls=[], package_weight_g=10, package_dimensions_mm=(1, 1, 1),
        )
