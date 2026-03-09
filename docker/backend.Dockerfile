FROM python:3.14.2-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
COPY ParaGraph ./ParaGraph

RUN uv sync --frozen || uv sync

EXPOSE 8000

CMD ["uv", "run", "--frozen", "python", "-m", "uvicorn", "ParaGraph.server.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]

