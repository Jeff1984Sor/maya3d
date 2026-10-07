from print3d_social import ContentPiece, ContentPublisher


class _Fake:
    async def submit(self, piece: ContentPiece) -> str:
        return "mp-1"


def test_fake_satisfaz_contrato() -> None:
    assert isinstance(_Fake(), ContentPublisher)
