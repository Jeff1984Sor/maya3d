"""Fábrica de rotas CRUD para cadastros simples (lista, cria, lê, edita parcialmente, remove).

Evita repetir o mesmo código em materiais, impressoras, embalagens e tarifas. Regras de
negócio específicas ficam em services/, não aqui.
"""

from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.base import Base
from print3d_api.db.session import get_session

Session = Annotated[AsyncSession, Depends(get_session)]


def crud_router(
    model: type[Base],
    create_schema: type[BaseModel],
    patch_schema: type[BaseModel],
    out_schema: type[BaseModel],
    *,
    prefix: str,
    tag: str,
    order_by: Sequence[Any] = (),
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    id_column = model.__table__.c.id

    async def _get_or_404(session: AsyncSession, item_id: int) -> Base:
        obj = await session.get(model, item_id)
        if obj is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"{model.__tablename__} {item_id} não existe"
            )
        return obj

    async def _commit(session: AsyncSession) -> None:
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "conflito com dados existentes") from exc

    @router.get("", response_model=list[out_schema])  # type: ignore[valid-type]
    async def list_items(session: Session) -> Sequence[Base]:
        stmt = select(model).order_by(*(order_by or (id_column,)))
        return (await session.scalars(stmt)).all()

    @router.post("", response_model=out_schema, status_code=status.HTTP_201_CREATED)
    async def create_item(payload: create_schema, session: Session) -> Base:  # type: ignore[valid-type]
        obj = model(**payload.model_dump())  # type: ignore[attr-defined]
        session.add(obj)
        await _commit(session)
        await session.refresh(obj)
        return obj

    @router.get("/{item_id}", response_model=out_schema)
    async def get_item(item_id: int, session: Session) -> Base:
        return await _get_or_404(session, item_id)

    @router.patch("/{item_id}", response_model=out_schema)
    async def patch_item(item_id: int, payload: patch_schema, session: Session) -> Base:  # type: ignore[valid-type]
        obj = await _get_or_404(session, item_id)
        for field, value in payload.model_dump(exclude_unset=True).items():  # type: ignore[attr-defined]
            setattr(obj, field, value)
        await _commit(session)
        await session.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_item(item_id: int, session: Session) -> Response:
        obj = await _get_or_404(session, item_id)
        await session.delete(obj)
        await _commit(session)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
