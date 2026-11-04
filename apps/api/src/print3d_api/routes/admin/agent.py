"""🤖 Assistente do painel: conversa e confirmação das propostas."""

from typing import Annotated

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AINotConfiguredError
from print3d_ai.claude import AIOutputError, AIRefusedError
from print3d_ai.image_search import ImageSearch
from print3d_ai.prompts.admin_agent import Turn
from print3d_api.db.session import get_session
from print3d_api.deps import get_ai_factory, get_image_search, get_queue, get_storage
from print3d_api.services import admin_agent, ai
from print3d_core.storage import LocalStorage

router = APIRouter(prefix="/agent", tags=["admin: assistente"])
Session = Annotated[AsyncSession, Depends(get_session)]
Images = Annotated[ImageSearch, Depends(get_image_search)]
Queue = Annotated[ArqRedis, Depends(get_queue)]


class ChatIn(BaseModel):
    turns: list[Turn] = Field(min_length=1, max_length=40)


@router.post("/chat", response_model=admin_agent.AgentReply)
async def chat(
    payload: ChatIn,
    session: Session,
    factory: Annotated[ai.ProviderFactory, Depends(get_ai_factory)],
    images: Images,
    queue: Queue,
) -> admin_agent.AgentReply:
    if payload.turns[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "a última fala é do dono")
    try:
        return await admin_agent.chat(session, factory, images, queue, payload.turns)
    except AINotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except (AIOutputError, AIRefusedError) as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"a IA não respondeu direito: {exc}"
        ) from exc
    except ai.PROVIDER_ERRORS as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"falha na IA: {type(exc).__name__}"
        ) from exc


@router.post("/proposals/{proposal_id}/confirm", response_model=admin_agent.ConfirmResult)
async def confirm(
    proposal_id: str,
    session: Session,
    storage: Annotated[LocalStorage, Depends(get_storage)],
    images: Images,
    queue: Queue,
) -> admin_agent.ConfirmResult:
    try:
        return await admin_agent.confirm(session, storage, queue, images, proposal_id)
    except admin_agent.AgentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
