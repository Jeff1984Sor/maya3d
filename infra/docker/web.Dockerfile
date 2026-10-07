# Imagem dos apps Next.js: docker build --build-arg APP=storefront|admin
# Contexto de build: raiz do repositório.
FROM node:22-alpine AS build
ARG APP
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-workspace.yaml pnpm-lock.yam[l] ./
COPY packages/shared packages/shared
COPY apps/storefront apps/storefront
COPY apps/admin apps/admin
# app Expo: só o manifesto, para o workspace bater com o lockfile (não é instalado aqui)
COPY apps/mobile/package.json apps/mobile/package.json
# Workspace completo (para o lockfile bater); só o app pedido é buildado.
RUN if [ -f pnpm-lock.yaml ]; then F=--frozen-lockfile; else F=--no-frozen-lockfile; fi \
 && pnpm install $F --filter "@print3d/${APP}..." \
 && pnpm --filter "@print3d/${APP}" build

FROM node:22-alpine
ARG APP
ARG RELEASE=dev
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000 NEXT_TELEMETRY_DISABLED=1 RELEASE=${RELEASE}
RUN addgroup -S app && adduser -S -u 10001 -G app app
WORKDIR /srv/app
COPY --from=build --chown=app:app /src/apps/${APP}/.next/standalone ./
COPY --from=build --chown=app:app /src/apps/${APP}/.next/static ./apps/${APP}/.next/static
ENV APP=${APP}
USER app
EXPOSE 3000
# standalone em monorepo: server.js fica em apps/<app>/
CMD ["sh", "-c", "exec node apps/${APP}/server.js"]
