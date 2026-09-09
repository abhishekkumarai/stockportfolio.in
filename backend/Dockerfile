FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /uvx /usr/local/bin/

# NLTK corpora are baked into the image at build time so that cold starts do not
# depend on a network round-trip to nltk.org. app/main.py reads this path.
ENV NLTK_DATA=/usr/local/share/nltk_data \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev \
    && .venv/bin/python -m nltk.downloader -d "$NLTK_DATA" vader_lexicon

ENV PATH="/app/.venv/bin:$PATH"

COPY app ./app
# Migrations, the worker entrypoint and the MCP server ship in the same image:
# the compose stack runs `alembic upgrade head` and scripts/worker.py from it,
# and one image means the api, the worker and a migration can never disagree
# about what version of the code they are running.
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY scripts ./scripts
COPY mcp_server ./mcp_server

# Render injects $PORT at runtime and it is not fixed across deploys, so it must
# be read at start rather than hardcoded. Default keeps local `docker run` simple.
ENV PORT=8001
EXPOSE 8001

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
