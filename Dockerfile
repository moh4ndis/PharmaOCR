FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"
ENV HOME="/home/appuser"
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PADDLEOCR_DET_MODEL=PP-OCRv5_mobile_det
ENV PADDLEOCR_REC_MODEL=en_PP-OCRv5_mobile_rec
ENV PADDLEOCR_CPU_THREADS=4

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
    && groupadd --system appuser \
    && useradd --system --gid appuser --home-dir /home/appuser --create-home appuser \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    && mkdir -p /app/uploads /home/appuser/.cache /home/appuser/.paddleocr /home/appuser/.paddlex \
    && chown -R appuser:appuser /app /home/appuser

COPY --chown=appuser:appuser app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
