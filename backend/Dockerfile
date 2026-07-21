FROM python:3.12-slim

# NLTK corpora are baked into the image at build time so that cold starts do not
# depend on a network round-trip to nltk.org. app/main.py reads this path.
ENV NLTK_DATA=/usr/local/share/nltk_data \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m nltk.downloader -d "$NLTK_DATA" vader_lexicon

COPY app ./app

# Render injects $PORT at runtime and it is not fixed across deploys, so it must
# be read at start rather than hardcoded. Default keeps local `docker run` simple.
ENV PORT=8001
EXPOSE 8001

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
