# --- Editor build (Node) -------------------------------------------------
FROM node:20-slim AS editor-build
WORKDIR /build
COPY serve-bucket/editor/package.json serve-bucket/editor/package-lock.json ./
RUN npm ci
COPY serve-bucket/editor/ ./
RUN npm run build

# --- App image (Python) --------------------------------------------------
FROM python:3.12-slim

# UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Palimpsest is imported via a sibling symlink in dev. Copy it as a real directory
# so `import palimpsest` resolves inside the container.
COPY palimpsest /app/palimpsest

# Install Python deps via UV
COPY serve-bucket/pyproject.toml serve-bucket/uv.lock /app/
RUN uv sync --frozen --no-install-project

# App code
COPY serve-bucket/app /app/app
COPY serve-bucket/sidebar.html /app/sidebar.html

# Editor build output from the Node stage
COPY --from=editor-build /build/dist /app/editor/dist

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
