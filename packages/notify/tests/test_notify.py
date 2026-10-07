from print3d_notify import NotifyProvider, OutboundMessage


class _Fake:
    async def send(self, message: OutboundMessage) -> str:
        return "wamid.1"


def test_fake_satisfaz_contrato() -> None:
    assert isinstance(_Fake(), NotifyProvider)


def test_mensagem_defaults() -> None:
    msg = OutboundMessage(to="+5515999999999", body="oi")
    assert msg.buttons == []
    assert msg.template is None
