"""Rewrite extracted kit Dockerfiles so the build context is frontend/web."""

from __future__ import annotations

from pathlib import Path

SVELTE_DOCKERFILE = """\
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

ARG PUBLIC_API_BASE_URL=/api/v1
ENV PUBLIC_API_BASE_URL=${PUBLIC_API_BASE_URL}
ENV NODE_ENV=production

RUN npm run build

FROM node:22-alpine AS production

WORKDIR /app

ARG PUBLIC_API_BASE_URL=/api/v1
ENV PUBLIC_API_BASE_URL=${PUBLIC_API_BASE_URL}
ENV NODE_ENV=production
ENV PORT=5000
ENV HOST=0.0.0.0

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/build ./build

EXPOSE 5000

CMD ["node", "build"]
"""

SVELTE_DOCKERFILE_DEV = """\
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

EXPOSE 5000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5000"]
"""

NEXT_DOCKERFILE = """\
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

ARG NEXT_PUBLIC_API_BASE_URL=/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NODE_ENV=production

RUN npm run build

FROM node:22-alpine AS production

WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL=/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NODE_ENV=production
ENV PORT=5000
ENV HOSTNAME=0.0.0.0

COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

EXPOSE 5000

CMD ["node", "server.js"]
"""

NUXT_DOCKERFILE = """\
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

ARG NUXT_PUBLIC_API_BASE_URL=/api/v1
ENV NUXT_PUBLIC_API_BASE_URL=${NUXT_PUBLIC_API_BASE_URL}
ENV NODE_ENV=production

RUN npm run build

FROM node:22-alpine AS production

WORKDIR /app

ARG NUXT_PUBLIC_API_BASE_URL=/api/v1
ENV NUXT_PUBLIC_API_BASE_URL=${NUXT_PUBLIC_API_BASE_URL}
ENV NODE_ENV=production
ENV PORT=5000
ENV HOST=0.0.0.0

COPY --from=build /app/.output ./

EXPOSE 5000

CMD ["node", "server/index.mjs"]
"""

RIO_DOCKERFILE = """\
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
WORKDIR /app

RUN pip install --no-cache-dir "rio-ui[window]>=0.12.3,<1.0.0"

COPY . .

EXPOSE 5000

CMD ["rio", "run", "--port", "5000", "--release", "--public"]
"""

RIO_DOCKERFILE_DEV = """\
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
WORKDIR /app

RUN pip install --no-cache-dir "rio-ui[window]>=0.12.3,<1.0.0"

COPY . .

EXPOSE 5000

CMD ["rio", "run", "--port", "5000", "--public"]
"""

_FILES = {
    "svelte": {"Dockerfile": SVELTE_DOCKERFILE, "Dockerfile.dev": SVELTE_DOCKERFILE_DEV},
    "next": {"Dockerfile": NEXT_DOCKERFILE},
    "nuxt": {"Dockerfile": NUXT_DOCKERFILE},
    "rio": {"Dockerfile": RIO_DOCKERFILE, "Dockerfile.dev": RIO_DOCKERFILE_DEV},
}


def rewrite_dockerfiles(web_dir: Path, kit_id: str) -> None:
    files = _FILES.get(kit_id)
    if not files:
        raise SystemExit(f"No Dockerfile rewrite for kit {kit_id!r}")
    for name, text in files.items():
        (web_dir / name).write_text(text, encoding="utf-8")
