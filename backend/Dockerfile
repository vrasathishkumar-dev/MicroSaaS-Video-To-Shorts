# syntax=docker/dockerfile:1
#
# Backend image for both the API and the render worker -- they run the same
# code and the same ffmpeg toolchain, only the entrypoint command differs.
#
# Debian's ffmpeg build ships libass and libfreetype, which the render
# pipeline needs for burned-in captions (see app/services/video_render.py:
# without them exports still succeed, just without captions).

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        curl \
        libpq5 \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc libpq-dev && apt-get autoremove -y

COPY . .

# Uploaded sources and rendered exports live here; mounted as a volume in
# docker-compose so the API and the worker share one filesystem.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/uploads/videos /app/uploads/exports \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["api"]
