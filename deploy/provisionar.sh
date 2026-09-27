#!/usr/bin/env bash
# Provisionamento do VaiVem no Google Cloud (Cloud Run + Cloud SQL).
#
# LEIA `deploy/README.md` ANTES. Este script não foi executado por quem o
# escreveu — não havia `gcloud` nem credenciais no ambiente de desenvolvimento.
# Rode passo a passo, conferindo cada saída, não de uma vez.
#
# Ele é dividido em etapas nomeadas. Rode uma por vez:
#
#     ./provisionar.sh apis
#     ./provisionar.sh registry
#     ...
#     ./provisionar.sh tudo        # só depois de entender cada etapa
#
# As etapas de criação toleram "já existe" (a mensagem aparece e segue), então
# reexecutar é seguro. As de deploy são idempotentes por natureza.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuração — ajuste antes de rodar
# ---------------------------------------------------------------------------
PROJETO="${PROJETO:-SEU_PROJECT_ID}"
REGIAO="${REGIAO:-southamerica-east1}"   # São Paulo: menor latência para as vans
INSTANCIA_SQL="${INSTANCIA_SQL:-vaivem-db}"
BANCO="${BANCO:-vaivem}"
SERVICO="${SERVICO:-vaivem-api}"
REPO="${REPO:-vaivem}"

# db-f1-micro (0,6GB) atende o piloto. A extensão `postgis` é instalada mas não
# usada (CLAUDE.md §3 — sem GPS nesta versão), então não há consulta espacial
# competindo por memória. Se a base crescer, `db-g1-small` é o próximo passo e
# não exige mudança de código.
TIER_SQL="${TIER_SQL:-db-f1-micro}"

CONEXAO_SQL="${PROJETO}:${REGIAO}:${INSTANCIA_SQL}"
IMAGEM="${REGIAO}-docker.pkg.dev/${PROJETO}/${REPO}/api"
SA_RUN="vaivem-run@${PROJETO}.iam.gserviceaccount.com"
SA_SCHED="vaivem-scheduler@${PROJETO}.iam.gserviceaccount.com"

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()  { printf '    %s\n' "$*"; }

verificar_projeto() {
  if [[ "$PROJETO" == "SEU_PROJECT_ID" ]]; then
    echo "ERRO: defina PROJETO (export PROJETO=meu-projeto) antes de rodar." >&2
    exit 1
  fi
  gcloud config set project "$PROJETO" >/dev/null
}

# ---------------------------------------------------------------------------
# 1. APIs
# ---------------------------------------------------------------------------
etapa_apis() {
  log "Habilitando APIs"
  # `cloudbuild` está aqui porque a imagem é construída NA NUVEM
  # (`gcloud builds submit`) — assim o deploy não depende de Docker na máquina de
  # quem publica.
  gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudbuild.googleapis.com
  ok "ok"
}

# ---------------------------------------------------------------------------
# 2. Artifact Registry
# ---------------------------------------------------------------------------
etapa_registry() {
  log "Criando repositório de imagens"
  gcloud artifacts repositories create "$REPO" \
    --repository-format=docker \
    --location="$REGIAO" \
    --description="Imagens do VaiVem" || ok "(já existe, seguindo)"
}

# ---------------------------------------------------------------------------
# 3. Cloud SQL
# ---------------------------------------------------------------------------
etapa_sql() {
  log "Criando instância Cloud SQL (leva ~10 min)"
  # `--availability-type=zonal`: sem alta disponibilidade. É piloto; HA dobra o
  # custo e o modo de falha que ela cobre (zona inteira cair) não é o risco
  # relevante aqui. Backup diário, sim — dado de viagem de criança não se perde.
  gcloud sql instances create "$INSTANCIA_SQL" \
    --database-version=POSTGRES_16 \
    --tier="$TIER_SQL" \
    --region="$REGIAO" \
    --storage-size=10GB \
    --storage-auto-increase \
    --availability-type=zonal \
    --backup \
    --backup-start-time=07:00 \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=8 || ok "(já existe, seguindo)"

  gcloud sql databases create "$BANCO" --instance="$INSTANCIA_SQL" || ok "(banco já existe)"
}

# ---------------------------------------------------------------------------
# 4. Segredos
# ---------------------------------------------------------------------------
# Tudo que é credencial vive no Secret Manager. As URLs de banco INTEIRAS são
# segredo (carregam a senha), não só a senha — assim o Cloud Run recebe uma
# variável pronta e nenhum passo de montagem de string existe para errar.
etapa_segredos() {
  log "Gerando e guardando segredos"

  criar_segredo() {  # nome, valor
    if gcloud secrets describe "$1" >/dev/null 2>&1; then
      ok "segredo '$1' já existe — mantido (NÃO sobrescrevo: rotação é ato deliberado)"
    else
      printf %s "$2" | gcloud secrets create "$1" --data-file=- --replication-policy=automatic
      ok "segredo '$1' criado"
    fi
  }

  local senha_owner senha_app jwt
  senha_owner="$(openssl rand -base64 32 | tr -d '\n=/+' | cut -c1-32)"
  senha_app="$(openssl rand -base64 32 | tr -d '\n=/+' | cut -c1-32)"
  jwt="$(openssl rand -base64 64 | tr -d '\n' )"

  criar_segredo vaivem-db-senha-owner "$senha_owner"
  criar_segredo vaivem-db-senha-app   "$senha_app"
  criar_segredo vaivem-jwt-secret     "$jwt"

  # Lê de volta (pode ter sido criado numa execução anterior) para montar as URLs.
  senha_owner="$(gcloud secrets versions access latest --secret=vaivem-db-senha-owner)"
  senha_app="$(gcloud secrets versions access latest --secret=vaivem-db-senha-app)"

  # Socket Unix: é como o Cloud Run fala com o Cloud SQL sem IP público nem
  # VPC connector. O `host=` no query string é o caminho do socket que o Cloud
  # Run monta a partir de `--add-cloudsql-instances`.
  criar_segredo vaivem-database-url-app \
    "postgresql+psycopg://vaivem_app:${senha_app}@/${BANCO}?host=/cloudsql/${CONEXAO_SQL}"
  criar_segredo vaivem-database-url-owner \
    "postgresql+psycopg://vaivem:${senha_owner}@/${BANCO}?host=/cloudsql/${CONEXAO_SQL}"

  log "Criando usuários do Postgres com essas senhas"
  gcloud sql users create vaivem     --instance="$INSTANCIA_SQL" --password="$senha_owner" || \
    gcloud sql users set-password vaivem     --instance="$INSTANCIA_SQL" --password="$senha_owner"
  gcloud sql users create vaivem_app --instance="$INSTANCIA_SQL" --password="$senha_app" || \
    gcloud sql users set-password vaivem_app --instance="$INSTANCIA_SQL" --password="$senha_app"
  ok "ok"
}

# ---------------------------------------------------------------------------
# 5. Papéis e extensões no banco — passo MANUAL, de propósito
# ---------------------------------------------------------------------------
etapa_papeis() {
  log "Papéis e extensões (interativo)"
  cat <<INSTRUCOES

  Este passo é interativo porque precisa de psql conectado como 'postgres'
  (superusuário), e é o único que não dá para automatizar sem abrir IP público
  de forma permanente.

  Rode:

      gcloud sql connect ${INSTANCIA_SQL} --user=postgres --database=${BANCO}

  E dentro do psql:

      \\i ${RAIZ}/deploy/sql/001_papeis_e_extensoes.sql

  Confira ao final que 'vaivem_app' NÃO pode contornar RLS — é disso que o
  isolamento entre operadores depende em runtime (CLAUDE.md §7.3):

      SELECT rolname, rolsuper, rolbypassrls FROM pg_roles
       WHERE rolname IN ('vaivem','vaivem_app');

  'vaivem_app' tem que aparecer com rolbypassrls = f. Se aparecer 't', PARE:
  os testes de RLS passariam e o isolamento não existiria.

INSTRUCOES
}

# ---------------------------------------------------------------------------
# 6. Identidades e permissões
# ---------------------------------------------------------------------------
etapa_iam() {
  log "Contas de serviço e permissões"

  gcloud iam service-accounts create vaivem-run \
    --display-name="VaiVem API (Cloud Run)" || ok "(já existe)"
  gcloud iam service-accounts create vaivem-scheduler \
    --display-name="VaiVem agendador (Cloud Scheduler)" || ok "(já existe)"

  # A conta do serviço só pode: falar com o Cloud SQL e ler os segredos. Nada de
  # storage, nada de admin — se a API for comprometida, o raio de alcance para.
  gcloud projects add-iam-policy-binding "$PROJETO" \
    --member="serviceAccount:${SA_RUN}" --role="roles/cloudsql.client" --condition=None >/dev/null

  for s in vaivem-jwt-secret vaivem-database-url-app vaivem-database-url-owner; do
    gcloud secrets add-iam-policy-binding "$s" \
      --member="serviceAccount:${SA_RUN}" \
      --role="roles/secretmanager.secretAccessor" >/dev/null
  done
  ok "ok"
}

# ---------------------------------------------------------------------------
# 7. Build da imagem
# ---------------------------------------------------------------------------
etapa_build() {
  log "Construindo a imagem na nuvem"
  gcloud builds submit "${RAIZ}/backend" --tag "${IMAGEM}:latest"
  ok "imagem: ${IMAGEM}:latest"
}

# ---------------------------------------------------------------------------
# 8. Jobs (migrations e agendador)
# ---------------------------------------------------------------------------
# Ambos recebem JWT_SECRET mesmo sem usar token: `app/core/config.py` valida os
# segredos no import, e `migrations/env.py` importa as settings. Sem ele, o job
# morre na validação com uma mensagem que parece problema de banco.
etapa_jobs() {
  log "Criando jobs"

  criar_ou_atualizar_job() {  # nome, url_do_banco, comando, args
    local acao=create
    gcloud run jobs describe "$1" --region="$REGIAO" >/dev/null 2>&1 && acao=update
    gcloud run jobs "$acao" "$1" \
      --image="${IMAGEM}:latest" \
      --region="$REGIAO" \
      --service-account="$SA_RUN" \
      --add-cloudsql-instances="$CONEXAO_SQL" \
      --set-env-vars="ENV=production" \
      --set-secrets="DATABASE_URL=${2}:latest,JWT_SECRET=vaivem-jwt-secret:latest" \
      --command="$3" \
      --args="$4" \
      --max-retries=1 \
      --task-timeout=10m
  }

  # Migrations rodam como OWNER (o papel da aplicação não tem DDL — de propósito).
  criar_ou_atualizar_job vaivem-migrate vaivem-database-url-owner alembic "upgrade,head"

  # O agendador roda como a APLICAÇÃO: ele lê e escreve dados de tenant e tem
  # que estar sujeito ao RLS igual a qualquer requisição.
  criar_ou_atualizar_job vaivem-agendador vaivem-database-url-app python "scripts/processar_notificacoes.py"
  ok "ok"
}

etapa_migrar() {
  log "Executando as migrations"
  gcloud run jobs execute vaivem-migrate --region="$REGIAO" --wait
  ok "ok"
}

# ---------------------------------------------------------------------------
# 9. O serviço
# ---------------------------------------------------------------------------
etapa_deploy() {
  log "Publicando a API"
  # `--allow-unauthenticated` é necessário e não é descuido: o app do motorista é
  # nativo, não tem identidade do Google Cloud. A autenticação é o JWT da própria
  # aplicação (`app/api/auth.py`) e o isolamento é o RLS (§7.3). O IAM do Cloud
  # Run não tem como substituir isso aqui.
  #
  # `--max-instances=4` conversa com o pool de `app/core/db.py`: 3 conexões por
  # instância × 4 = 12, dentro do limite de 25 do db-f1-micro, com folga para os
  # dois jobs. Mexer num sem o outro é como se esgotam conexões em produção.
  #
  # `--min-instances=1` evita cold start (~5s) no primeiro toque do motorista.
  # Custa ~US$10-15/mês. Para economizar no piloto, troque por 0 e aceite que o
  # primeiro login do dia demora — a fila offline absorve eventos, mas o login e
  # a lista de rotas não.
  gcloud run deploy "$SERVICO" \
    --image="${IMAGEM}:latest" \
    --region="$REGIAO" \
    --service-account="$SA_RUN" \
    --add-cloudsql-instances="$CONEXAO_SQL" \
    --set-env-vars="ENV=production" \
    --set-secrets="DATABASE_URL=vaivem-database-url-app:latest,JWT_SECRET=vaivem-jwt-secret:latest" \
    --allow-unauthenticated \
    --cpu=1 --memory=512Mi \
    --concurrency=40 \
    --min-instances=1 --max-instances=4 \
    --timeout=30s

  log "URL do serviço"
  gcloud run services describe "$SERVICO" --region="$REGIAO" --format='value(status.url)'
}

# ---------------------------------------------------------------------------
# 10. Cloud Scheduler — o que faz o aviso de preparo existir
# ---------------------------------------------------------------------------
etapa_scheduler() {
  log "Agendando o processador de notificações"

  gcloud run jobs add-iam-policy-binding vaivem-agendador \
    --region="$REGIAO" \
    --member="serviceAccount:${SA_SCHED}" \
    --role="roles/run.invoker" >/dev/null

  # A cada minuto, em dias úteis, nas faixas em que rota escolar existe.
  #
  # A cada minuto porque o `preparo` é agendado para um instante calculado
  # (ETA(N+2) − 5min, com teto — CLAUDE.md §5): uma janela de 5 min atrasaria em
  # até 5 min um aviso cuja premissa é "faltam ~5-10 min", o que o torna falso.
  #
  # E só nessas faixas porque transporte escolar não roda às 3h da manhã — isso
  # corta ~70% das execuções e mantém tudo dentro da camada gratuita do Cloud Run.
  local uri="https://run.googleapis.com/v2/projects/${PROJETO}/locations/${REGIAO}/jobs/vaivem-agendador:run"
  local acao=create
  gcloud scheduler jobs describe vaivem-agendador-cron --location="$REGIAO" >/dev/null 2>&1 && acao=update

  gcloud scheduler jobs "$acao" http vaivem-agendador-cron \
    --location="$REGIAO" \
    --schedule="* 5-9,11-19 * * 1-5" \
    --time-zone="America/Sao_Paulo" \
    --uri="$uri" \
    --http-method=POST \
    --oauth-service-account-email="$SA_SCHED" \
    --attempt-deadline=120s
  ok "ok"
}

# ---------------------------------------------------------------------------
etapa_verificar() {
  log "Verificação"
  local url
  url="$(gcloud run services describe "$SERVICO" --region="$REGIAO" --format='value(status.url)')"
  ok "GET ${url}/health"
  curl -fsS "${url}/health" && echo
  ok "Execute o agendador uma vez à mão para conferir que ele conecta:"
  ok "  gcloud run jobs execute vaivem-agendador --region=${REGIAO} --wait"
  ok "E aponte o app para esta URL: mobile/.env -> EXPO_PUBLIC_API_BASE_URL=${url}"
}

# ---------------------------------------------------------------------------
verificar_projeto
case "${1:-}" in
  apis)       etapa_apis ;;
  registry)   etapa_registry ;;
  sql)        etapa_sql ;;
  segredos)   etapa_segredos ;;
  papeis)     etapa_papeis ;;
  iam)        etapa_iam ;;
  build)      etapa_build ;;
  jobs)       etapa_jobs ;;
  migrar)     etapa_migrar ;;
  deploy)     etapa_deploy ;;
  scheduler)  etapa_scheduler ;;
  verificar)  etapa_verificar ;;
  tudo)
    etapa_apis; etapa_registry; etapa_sql; etapa_segredos
    etapa_papeis
    echo "PARE AQUI: rode o SQL acima antes de continuar, então:" >&2
    echo "  ./provisionar.sh iam && ./provisionar.sh build && ./provisionar.sh jobs \\" >&2
    echo "  && ./provisionar.sh migrar && ./provisionar.sh deploy && ./provisionar.sh scheduler" >&2
    ;;
  *)
    echo "uso: $0 {apis|registry|sql|segredos|papeis|iam|build|jobs|migrar|deploy|scheduler|verificar|tudo}" >&2
    exit 1 ;;
esac
