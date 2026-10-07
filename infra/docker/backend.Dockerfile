# Imagem única para API e worker (comandos diferentes no compose).
# Contexto de build: raiz do repositório.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY apps/api apps/api
COPY apps/worker apps/worker
COPY packages packages
RUN uv sync --locked --no-dev --no-editable --all-packages

FROM python:3.12-slim
ARG RELEASE=dev
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 RELEASE=${RELEASE}
# OpenSCAD: gera os modelos paramétricos no worker (fontes OFL vêm dentro do pacote print3d_mesh).
RUN apt-get update \
 && apt-get install -y --no-install-recommends openscad \
 && rm -rf /var/lib/apt/lists/*
RUN useradd --system --uid 10001 --no-create-home app \
 && install -d -o app -g app /data/files
COPY --from=build /opt/venv /opt/venv
WORKDIR /srv/app
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/migrations ./migrations
USER app
EXPOSE 8000
CMD ["uvicorn", "print3d_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
