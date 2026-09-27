# Deploy — Cloud Run + Cloud SQL

Tira o backend da máquina de desenvolvimento. Hoje o app só funciona com o
celular na mesma Wi-Fi do PC, `uvicorn --host 0.0.0.0` e uma regra de firewall
manual (ver PROGRESSO.md, B4) — um motorista não testa nada dentro de uma van
com isso.

> **Nada aqui foi executado.** Não havia `gcloud` nem credenciais no ambiente em
> que este material foi escrito. O que **foi** verificado, contra o Postgres real
> do `docker-compose`, está na seção "O que já está provado". Rode
> `provisionar.sh` etapa por etapa, conferindo cada saída.

## O que sobe

| Peça | O quê | Por quê |
|---|---|---|
| Cloud Run **service** `vaivem-api` | `uvicorn app.main:app` | a API que o app consome |
| Cloud Run **job** `vaivem-migrate` | `alembic upgrade head` | migrations, como **owner** |
| Cloud Run **job** `vaivem-agendador` | `scripts/processar_notificacoes.py` | **é o que faz o aviso de preparo existir** |
| Cloud Scheduler | dispara o job a cada minuto, em horário de rota | granularidade que o §5 exige |
| Cloud SQL Postgres 16 | `db-f1-micro`, backup diário | o banco |
| Secret Manager | URLs de banco e `JWT_SECRET` | credencial nunca em variável de texto |

**Uma imagem só**, três comandos diferentes. O agendador importa
`app.services.agendador` e o job de migration importa `app.core.config` —
separá-los em três imagens criaria três conjuntos de dependências que divergem,
e a divergência apareceria no envio de uma notificação, não no build.

### Duas peças que o CLAUDE.md prevê e que NÃO sobem

- **Redis / Memorystore.** O `redis_url` existe em `config.py` desde o Sprint 0 e
  **nenhum módulo importa `redis`** (conferido em `app/` e `scripts/`).
  Provisionar Memorystore custaria ~US$35/mês mais um VPC connector para uma
  dependência que não é usada. Quando algum recurso precisar de cache ou fila,
  entra junto com ele.
- **Gestor / painel web.** Fora de escopo (CLAUDE.md §10). Consequência prática
  em "Antes de chamar um motorista", abaixo.

## O buraco que isto fecha

A cascata de notificações do §5 está **2 de 3 funcionando** hoje:

| Notificação | Como sai | Sem este deploy |
|---|---|---|
| `chegada` ("chegamos, esperando") | síncrona, dentro do request | ✅ funciona |
| `iminencia` ("é a próxima!") | síncrona, dentro do request | ✅ funciona |
| `preparo` ("faltam ~X min") | linha `agendado` na tabela | ❌ **nunca dispara** |

`scripts/processar_notificacoes.py` existe desde o B3, é idempotente e tem teste
de corrida — mas **nada o invocava periodicamente**. O PROGRESSO do B3 registrou
isso como "decisão de deploy", e a decisão nunca foi tomada. Os testes não pegam
porque chamam a função direto.

É o aviso que serve para o responsável **preparar a criança** — o mais útil dos
três para um pai.

## Ordem

```bash
export PROJETO=meu-projeto-gcp
cd deploy && chmod +x provisionar.sh

./provisionar.sh apis
./provisionar.sh registry
./provisionar.sh sql         # ~10 min
./provisionar.sh segredos
./provisionar.sh papeis      # imprime instruções — passo MANUAL, ver abaixo
./provisionar.sh iam
./provisionar.sh build
./provisionar.sh jobs
./provisionar.sh migrar
./provisionar.sh deploy
./provisionar.sh scheduler
./provisionar.sh verificar
```

Depois, aponte o app para a URL que `verificar` imprime:

```
# mobile/.env
EXPO_PUBLIC_API_BASE_URL=https://vaivem-api-xxxxx.a.run.app
```

## O passo manual, e por que ele não é automatizado

`./provisionar.sh papeis` só imprime instruções. Ele precisa de `psql` conectado
como `postgres`, e automatizar isso exigiria abrir IP público de forma permanente
ou subir um bucket intermediário — mais superfície do que o passo merece.

O que esse SQL (`deploy/sql/001_papeis_e_extensoes.sql`) faz, e por que é a parte
mais importante de todo o deploy:

**Todo superusuário do Postgres tem `BYPASSRLS` e ignora as policies**, inclusive
com `FORCE ROW LEVEL SECURITY`. Se a aplicação conectasse como owner, o
isolamento entre operadores existiria no schema e não em runtime — e os 45 testes
de integração de RLS passariam **sem provar nada**, porque estariam medindo um
papel que não é o que atende requisição. Daí os dois papéis:

- `vaivem` — owner. Roda migrations (DDL). Nunca atende requisição.
- `vaivem_app` — API, agendador e testes. Sem DDL, sem `BYPASSRLS`.

Confira antes de seguir:

```sql
SELECT rolname, rolsuper, rolbypassrls FROM pg_roles
 WHERE rolname IN ('vaivem','vaivem_app');
```

`vaivem_app` **tem** que aparecer com `rolbypassrls = f`. Se aparecer `t`, pare:
o isolamento entre operadores não existe, e nenhum teste vai te avisar.

Esse SQL nasceu aqui, mas cobre o ambiente local também — o `vaivem_app` do
`docker-compose` foi montado à mão nas sessões do B1/B2 e só existia descrito em
prosa no PROGRESSO.md.

## Decisões embutidas, para não serem descobertas na fatura ou no incidente

**`--allow-unauthenticated` é necessário, não descuido.** O app do motorista é
nativo e não tem identidade do Google Cloud. A autenticação é o JWT da própria
aplicação e o isolamento é o RLS. O IAM do Cloud Run não substitui isso aqui.

**`--max-instances=4` conversa com o pool de `app/core/db.py`.** Cada instância
do Cloud Run tem o seu pool; 3 conexões × 4 instâncias = 12, dentro do limite de
25 do `db-f1-micro`, com folga para os dois jobs. O padrão do SQLAlchemy
(5 + 10 = 15 por instância) daria 60 e produziria
`FATAL: remaining connection slots are reserved` sob pico — exatamente quando o
motorista está registrando embarque. **Mexer num sem o outro é como se esgotam
conexões em produção.**

**`--min-instances=1`** evita cold start (~5s) no primeiro toque do dia. Custa
~US$10-15/mês. Para economizar, troque por `0`: a fila offline absorve eventos de
embarque, mas o login e a lista de rotas ficam lentos.

**O cron do agendador é `* 5-9,11-19 * * 1-5`** (a cada minuto, dias úteis, em
horário de rota). A cada minuto porque o `preparo` é agendado para um instante
calculado e uma janela de 5 min atrasaria em até 5 min um aviso cuja premissa é
"faltam ~5-10 min" — tornando-o falso. Restrito às faixas porque transporte
escolar não roda às 3h; corta ~70% das execuções e mantém tudo na camada
gratuita do Cloud Run.

**Os jobs recebem `JWT_SECRET` mesmo sem usar token.** `app/core/config.py` valida
os segredos no import e `migrations/env.py` importa as settings. Sem ele, o job
morre na validação com uma mensagem que parece problema de banco.

**A guarda de segredo recusa subir em produção com o valor de exemplo.** É a pior
configuração incorreta possível aqui e a mais silenciosa: o `jwt_secret` assina
os tokens que carregam `tenant_id` e `role`, e o valor padrão está no
`.env.example`, versionado e público — com ele, qualquer pessoa forja um token de
admin de qualquer tenant e o RLS não protege nada, porque a sessão passa a setar
o `app.tenant_id` que o atacante escolheu. Sem a guarda, um deploy que esquecesse
de montar o segredo subiria saudável e passaria todo teste de fumaça.

## O que já está provado

Rodado de verdade, com a imagem construída localmente contra o Postgres do
`docker-compose`, em `ENV=production` com segredo real:

| Verificação | Resultado |
|---|---|
| `docker build` | ✅ só wheels, sem toolchain de compilação |
| Job de migration (`alembic upgrade head`, como owner) | ✅ |
| Job do agendador (`scripts/processar_notificacoes.py`) | ✅ processou 28 notificações vencidas |
| API: `GET /health` | ✅ 200 |
| API: `POST /api/auth/login` | ✅ 200, JWT emitido |
| API: `GET /api/viagens` autenticado (depende de RLS) | ✅ só as viagens do tenant do motorista |
| Guarda de segredo com `ENV=production` sem `JWT_SECRET` | ✅ recusa subir |

**Um bug foi encontrado exatamente aqui** e não teria aparecido de outra forma: o
job do agendador quebrava com `ModuleNotFoundError: No module named 'app'`, porque
invocar `python scripts/x.py` coloca `sys.path[0]` em `/app/scripts`. Corrigido
com `PYTHONPATH=/app` na imagem. Sem rodar o container, isso apareceria em
produção como "o aviso de preparo não chega", com a API saudável em `/health` o
tempo todo.

O que **não** está provado: nada específico do Google Cloud — socket do Cloud SQL,
montagem de segredos, permissões de IAM, disparo do Scheduler. Isso só se verifica
com um projeto real.

## Antes de chamar um motorista

1. **`eas init`** (seu, um comando, gratuito). Sem `projectId`, o
   `registrarPushToken()` desiste em silêncio e **nenhum** push funciona — nem os
   dois que já estão prontos.
2. **Popule dados.** Rotas, alunos, paradas e viagens só nascem de
   `scripts/seed_demo.py`, porque o Gestor é mockup (§10). Para um piloto com um
   motorista conhecido, rodar o seed apontando para o Cloud SQL resolve. Para um
   segundo cliente, não — aí o Gestor deixa de estar fora de escopo. **É uma
   decisão de produto, não uma tarefa.**
3. **Rode o roteiro em aparelho.** B4, B5, B7 e B8 nunca foram validados ponta a
   ponta: viagem inteira, finalizar com aluno a bordo, modo avião com 6 eventos,
   os 4 sons dentro da van, o tema escuro à noite.
