# Home Air Quality in a container. docker-compose.yml runs it; DEPLOYMENT.md, "Docker", has the steps.
FROM python:3.12-slim-bookworm

# links the published image (ghcr.io/sguyon/home-air-quality) to its repo
LABEL org.opencontainers.image.source="https://github.com/sguyon/home-air-quality" \
      org.opencontainers.image.description="A page that reads your AirGradient monitors and says what to do about the air at home" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# .dockerignore keeps out the keys, your config.toml, tests and private notes
COPY . .

# config.toml is mounted at /config/config.toml. A link rather than CONFIG_FILE: with nothing mounted the link leads
# nowhere and the server does what it does on a computer (the demo, or "No config" when a token is set), where a
# CONFIG_FILE that can't be read stops it. CONFIG_FILE or CONFIG_TOML still win when set.
RUN ln -s /config/config.toml /app/config.toml \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["sh", "-c", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT:-8000}/health', timeout=4)\""]

# the commit, for the page's build stamp (image.yml passes it; a local build shows "no-git")
ARG GIT_SHA=""
ENV GIT_COMMIT_SHA=$GIT_SHA

# the Procfile's command, on the host's PORT when it sets one (Railway does, and builds this file), else 8000
CMD ["sh", "-c", "exec gunicorn server:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 8 --timeout 60"]
