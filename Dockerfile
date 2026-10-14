# Imagem do servidor LandMass (D200 a D205). Build: docker build -t landmass-emu .
# O container não tem o cliente: catálogo e `shop sync` ficam fora dele (docs/operations/production.md).
FROM python:3.14-slim

# O uv.toml do projeto põe o cache fora de /app; no build, o cache vai para um caminho próprio.
ENV PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_CACHE_DIR=/tmp/uv-cache

# uv na mesma versão usada no desenvolvimento.
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv

WORKDIR /app

# Dependências antes do código: a camada só muda quando o lockfile muda.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN --mount=type=cache,target=/tmp/uv-cache \
    uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/tmp/uv-cache \
    uv sync --locked --no-dev

# Sem privilégio de root. O volume de dados precisa ser deste usuário.
RUN groupadd --gid 10001 landmass \
 && useradd --uid 10001 --gid landmass --home-dir /app --no-create-home --shell /usr/sbin/nologin landmass \
 && mkdir -p /app/data \
 && chown landmass:landmass /app/data
USER landmass

EXPOSE 7313 7314

# SIGTERM pede o desligamento gracioso (D202). O processo é o PID 1, com a forma exec.
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["/app/.venv/bin/landmass-emu", "health"]

ENTRYPOINT ["/app/.venv/bin/landmass-emu"]
CMD ["serve"]
