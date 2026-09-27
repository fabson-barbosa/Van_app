# VaiVem — Backend (API)

API FastAPI da plataforma de transporte escolar. O domínio está especificado em
`CLAUDE.md` (raiz) — leia-o antes de mudar comportamento. O andamento por bloco
está em `PROGRESSO.md`.

## Ambiente local

Sobe Postgres 16 + PostGIS e Redis (este último **ainda não usado** por nenhum
módulo — ver `deploy/README.md`):

```bash
docker compose up -d          # na raiz do repositório
cp .env.example .env
pip install -r requirements.txt
```

### Papéis do banco — não use um só

O `.env` aponta para **`vaivem_app`**, e isso não é detalhe: todo superusuário do
Postgres tem `BYPASSRLS` e ignora as policies, inclusive com `FORCE ROW LEVEL
SECURITY`. Se a aplicação (ou os testes) conectassem como owner, o isolamento
entre operadores existiria no schema e não em runtime, e os testes de RLS
passariam sem provar nada.

```
vaivem      → owner. Roda migrations (DDL). Nunca atende requisição.
vaivem_app  → API, agendador e testes. Sem DDL, sem BYPASSRLS.
```

Criar os papéis num banco novo (idempotente, como superusuário):

```bash
docker exec -i vanapp-db-1 psql -U vaivem -d vaivem < ../deploy/sql/001_papeis_e_extensoes.sql
```

### Migrations

Rodam como **owner** — o papel da aplicação não tem DDL de propósito. Esquecer
isso produz `permission denied for table alembic_version`:

```bash
DATABASE_URL="postgresql+psycopg://vaivem:vaivem@localhost:5432/vaivem" \
  python -m alembic upgrade head
```

### A API

```bash
uvicorn app.main:app --reload
```

`http://localhost:8000/docs` para o Swagger. Para testar em **aparelho físico** na
mesma rede, `--host 0.0.0.0` e liberar a porta no firewall (ver PROGRESSO.md,
B4) — ou publicar de verdade (`deploy/README.md`).

### Scripts — exigem `PYTHONPATH=.`

Eles são invocados por caminho, e nesse modo o `sys.path[0]` é `scripts/`, não a
raiz do backend: sem a variável, todos falham com
`ModuleNotFoundError: No module named 'app'`. (Na imagem Docker isso é resolvido
por `PYTHONPATH=/app`, no Dockerfile.)

```bash
PYTHONPATH=. python scripts/seed_demo.py              # idempotente: 1 tenant, 2 rotas, 12 alunos,
                                                       # + as viagens 'planejada' de hoje
PYTHONPATH=. python scripts/simular_viagem.py         # timeline completa de uma viagem, com
                                                       # rollback no fim — não suja a base
PYTHONPATH=. python scripts/processar_notificacoes.py # entrega os avisos de 'preparo' vencidos
```

**`processar_notificacoes.py` precisa rodar periodicamente.** Sem isso, o aviso de
preparo ("faltam ~X min", CLAUDE.md §5) nunca chega — as outras duas notificações
da cascata saem no próprio request e funcionam sem ele. Em produção quem o dispara
é o Cloud Scheduler (`deploy/README.md`); localmente, rode à mão quando quiser
observar o efeito.

Login do seed: `motorista.centro@demo.vaivem.com.br` / `demo12345`.

## Testes

```bash
pytest                  # unitários, sem banco
pytest -m integration   # contra o Postgres do docker-compose
```

Os de integração são excluídos por padrão (`pytest.ini`) porque exigem banco de
verdade. Eles **commitam e não limpam a base** — daí os identificadores aleatórios
em fixtures; ver `tests/integration/test_expo_push.py`.

## Estrutura

```
app/
├── main.py         # entrypoint
├── core/           # config (+ guarda de segredos), engine/pool, segurança
├── models/         # SQLAlchemy (+ PostGIS reservado para o futuro)
├── schemas/        # Pydantic
├── api/            # rotas; `deps.get_tenant_db` é o que ativa o RLS por request
└── services/       # máquina de estados, motor de tempos, notificações, push
migrations/         # Alembic
scripts/            # seed, simulação, agendador
```

Deploy em `deploy/` (Cloud Run + Cloud SQL).
