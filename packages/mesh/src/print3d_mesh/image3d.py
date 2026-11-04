"""Foto vira objeto 3D por IA (serviço externo atrás de um Provider).

O serviço devolve só a forma (sem textura); o resto é nosso: conserto da malha, tamanho
final em mm e arquivos para o fatiador. Medidas vêm da malha, nunca da IA.

Meshy (docs.meshy.ai/en/api/image-to-3d, lido em 2026-11-04): POST /openapi/v1/image-to-3d
com a foto em data URI; status PENDING/IN_PROGRESS/SUCCEEDED/FAILED/CANCELED; os links em
model_urls expiram — baixar assim que terminar.
"""

import base64
import io
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

import httpx
import trimesh

type TaskStatus = Literal["fila", "processando", "concluido", "falhou"]


class Image3DError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Image3DTask:
    id: str
    status: TaskStatus
    progress: int = 0
    model_url: str | None = None  # STL pronto para baixar quando concluído
    error: str | None = None
    credits: int | None = None


@runtime_checkable
class ImageTo3D(Protocol):
    async def submit(self, image: bytes, mime: str) -> str: ...
    async def task(self, task_id: str) -> Image3DTask: ...
    async def download(self, url: str) -> bytes: ...


_MESHY_STATUS: dict[str, TaskStatus] = {
    "PENDING": "fila",
    "IN_PROGRESS": "processando",
    "SUCCEEDED": "concluido",
    "FAILED": "falhou",
    "CANCELED": "falhou",
}
_MESHY_ERRORS = {
    401: "chave da Meshy inválida (confira em Integrações)",
    402: "sem créditos na Meshy: recarregue a conta",
    403: "o plano da Meshy não libera a API (precisa do Pro ou maior)",
    429: "Meshy ocupada (limite de tarefas): tente de novo em instantes",
}


class MeshyImageTo3D:
    base_url = "https://api.meshy.ai"

    def __init__(
        self, api_key: str, model: str | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self._key = api_key
        self._model = model or None  # vazio = o padrão atual da Meshy (modelo nunca no código)
        self._client = client

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._key}"}
        try:
            if self._client is not None:
                res = await self._client.request(method, url, headers=headers, **kwargs)
            else:
                async with httpx.AsyncClient(timeout=60) as client:
                    res = await client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise Image3DError(f"Meshy fora do ar: {exc.__class__.__name__}") from exc
        if res.status_code in _MESHY_ERRORS:
            raise Image3DError(_MESHY_ERRORS[res.status_code], res.status_code)
        if res.status_code >= 400:
            detail = res.text[:300]
            raise Image3DError(f"Meshy recusou ({res.status_code}): {detail}", res.status_code)
        return res

    async def submit(self, image: bytes, mime: str) -> str:
        body: dict[str, Any] = {
            "image_url": f"data:{mime};base64,{base64.b64encode(image).decode()}",
            "should_texture": False,  # impressão: só a forma
            "target_formats": ["stl"],
            "origin_at": "bottom",
        }
        if self._model:
            body["ai_model"] = self._model
        res = await self._request("POST", f"{self.base_url}/openapi/v1/image-to-3d", json=body)
        task_id = res.json().get("result")
        if not task_id:
            raise Image3DError("Meshy não devolveu o id da tarefa")
        return str(task_id)

    async def task(self, task_id: str) -> Image3DTask:
        res = await self._request("GET", f"{self.base_url}/openapi/v1/image-to-3d/{task_id}")
        data = res.json()
        status = _MESHY_STATUS.get(str(data.get("status")), "processando")
        error = (data.get("task_error") or {}).get("message") or None
        url = (data.get("model_urls") or {}).get("stl") or None
        if status == "concluido" and not url:
            status, error = "falhou", "a Meshy terminou sem arquivo STL"
        return Image3DTask(
            id=task_id,
            status=status,
            progress=int(data.get("progress") or 0),
            model_url=url,
            error=error if status == "falhou" else None,
            credits=data.get("consumed_credits"),
        )

    async def download(self, url: str) -> bytes:
        # link assinado: sem o cabeçalho de autorização
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                res = await client.get(url)
        except httpx.HTTPError as exc:
            raise Image3DError(f"falha ao baixar o modelo: {exc.__class__.__name__}") from exc
        if res.status_code >= 400:
            raise Image3DError(f"falha ao baixar o modelo ({res.status_code})")
        return res.content


@dataclass
class PrintableModel:
    mesh: trimesh.Trimesh
    watertight: bool
    info: dict[str, Any] = field(default_factory=dict)


def prepare_for_print(data: bytes, file_type: str, size_mm: float) -> PrintableModel:
    """Conserta o que dá, coloca no tamanho pedido (maior lado), centraliza e apoia na mesa."""
    try:
        loaded = trimesh.load(io.BytesIO(data), file_type=file_type, force="mesh")
    except Exception as exc:  # arquivo corrompido vindo do serviço
        raise Image3DError(f"modelo inválido: {exc}") from exc
    if not isinstance(loaded, trimesh.Trimesh) or len(loaded.faces) == 0:
        raise Image3DError("o serviço devolveu um modelo vazio")
    mesh = loaded
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fill_holes(mesh)
    trimesh.repair.fix_normals(mesh)  # type: ignore[no-untyped-call]
    # maior lado = tamanho pedido (não depende de o serviço devolver Y ou Z para cima)
    largest = float(max(mesh.extents))
    if largest <= 0:
        raise Image3DError("modelo sem tamanho")
    mesh.apply_scale(size_mm / largest)  # type: ignore[no-untyped-call]
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    watertight = bool(mesh.is_watertight)
    info: dict[str, Any] = {
        "bbox_mm": [round(float(v), 1) for v in mesh.extents],
        "triangles": len(mesh.faces),
        "watertight": watertight,
    }
    if watertight:
        info["volume_cm3"] = round(float(mesh.volume) / 1000, 1)
    return PrintableModel(mesh=mesh, watertight=watertight, info=info)
