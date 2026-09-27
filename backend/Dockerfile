# Imagem do backend VaiVem — serve os TRÊS processos do deploy.
#
# O mesmo artefato roda:
#
#   1. a API          — `uvicorn app.main:app` (Cloud Run service; CMD padrão)
#   2. as migrations  — `alembic upgrade head` (Cloud Run job, como owner)
#   3. o agendador    — `python scripts/processar_notificacoes.py` (Cloud Run job)
#
# Uma imagem e não três porque o agendador importa `app.services.agendador` e o
# job de migration importa `app.core.config`: separá-los criaria três conjuntos
# de dependências que podem divergir, e o sintoma da divergência apareceria em
# produção, no envio de uma notificação — não no build.
#
# O comando é sobrescrito por invocação (`--command`/`--args` no gcloud), então
# não há ENTRYPOINT rígido.

FROM python:3.13-slim AS base

# - PYTHONDONTWRITEBYTECODE: o filesystem do Cloud Run é efêmero; .pyc só ocupa
#   espaço na imagem.
# - PYTHONUNBUFFERED: sem isso o stdout fica preso no buffer e o Cloud Logging
#   só mostra os logs quando o processo morre — justamente quando se precisa
#   deles para entender por que ele morreu.
#
# PYTHONPATH=/app é OBRIGATÓRIO, não conveniência: os scripts de `scripts/` são
# invocados por caminho (`python scripts/processar_notificacoes.py`), e nesse
# modo o `sys.path[0]` é `/app/scripts`, não `/app` — o `import app.core.db`
# falha com `ModuleNotFoundError`. Sem esta linha o job do agendador morre no
# start e o aviso de preparo (§5) nunca sai, com a API respondendo 200 no
# `/health` o tempo todo. Descoberto rodando a imagem, não no build.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# `requirements.txt` antes do código: a camada de dependências só é reconstruída
# quando ele muda, e não a cada alteração de uma linha de serviço.
# Só wheels: nenhuma dependência atual precisa de toolchain de compilação
# (`psycopg[binary]`, `shapely` e `bcrypt` trazem binário pronto), então a imagem
# não carrega gcc. Se um dia uma dependência exigir build, isto falha NO BUILD,
# que é onde se quer descobrir.
COPY requirements.txt ./
RUN pip install --only-binary=:all: --no-compile -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./

# Usuário sem privilégio. O Cloud Run já isola o container, mas a aplicação não
# tem motivo para rodar como root — e um dia esta imagem pode rodar em outro
# lugar que não isole.
RUN useradd --create-home --uid 10001 vaivem && chown -R vaivem:vaivem /app
USER vaivem

# Cloud Run injeta $PORT (8080 por padrão) e não aceita porta fixa.
#
# `--workers 1` é deliberado: a escala é horizontal, feita pelo Cloud Run, e
# cada worker teria o SEU pool de conexões — multiplicando o total contra o
# limite do Cloud SQL sem que `db_pool_size` refletisse isso (ver
# `app/core/db.py`).
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers"]
