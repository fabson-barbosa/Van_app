-- Papéis, extensões e privilégios do banco VaiVem.
--
-- Rodar UMA VEZ por banco, como superusuário (`postgres` no Cloud SQL; `vaivem`
-- no docker-compose local), ANTES da primeira migration. Idempotente: pode ser
-- reaplicado sem erro.
--
-- ## Por que dois papéis, e por que isso não é detalhe de infraestrutura
--
-- A regra inviolável 7.3 do CLAUDE.md ("RLS ativa em toda tabela com
-- `tenant_id`") depende de um fato do Postgres: **todo superusuário tem
-- `BYPASSRLS` e ignora as policies**, inclusive com `FORCE ROW LEVEL SECURITY`.
-- Se a aplicação conectasse como owner, o isolamento entre operadores existiria
-- no schema e não em runtime — e os testes de RLS passariam sem provar nada,
-- porque estariam medindo um papel que não é o que atende requisição.
--
-- Então:
--
--   vaivem      — owner. Roda migrations (DDL). Nunca atende requisição.
--   vaivem_app  — aplicação, agendador e testes. Sem DDL, sem BYPASSRLS.
--
-- Este arquivo nasceu no deploy para Cloud Run, mas o ambiente local foi
-- montado à mão nas sessões do B1/B2 e só existia descrito em prosa no
-- PROGRESSO.md. Agora é o mesmo SQL nos dois lugares.

-- ---------------------------------------------------------------------------
-- Extensões
-- ---------------------------------------------------------------------------
-- A migration `0001_initial_schema` também as cria, com `IF NOT EXISTS`. Criar
-- aqui primeiro, como superusuário, é o que permite o job de migration rodar
-- como `vaivem` (sem privilégio para instalar extensão): encontrando-as já
-- instaladas, o `IF NOT EXISTS` retorna sem checar privilégio.
--
-- `postgis` está reservada para o futuro (CLAUDE.md §3 — sem GPS nesta versão);
-- `pgcrypto` é usada de verdade, pelo `gen_random_uuid()` do backfill da
-- migration 0008.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Papéis
-- ---------------------------------------------------------------------------
-- As senhas NÃO ficam aqui. `provisionar.sh` as injeta via `psql -v`, lendo do
-- Secret Manager; um arquivo versionado com senha é o que este projeto passou o
-- B5 inteiro evitando.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vaivem') THEN
    CREATE ROLE vaivem LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vaivem_app') THEN
    CREATE ROLE vaivem_app LOGIN;
  END IF;
END
$$;

-- Explícito, mesmo sendo o padrão: é a linha de que os testes de RLS dependem, e
-- deixá-la implícita convida alguém a "só promover o papel para resolver um
-- permission denied" sem perceber que desliga o isolamento entre tenants.
ALTER ROLE vaivem_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

-- Os atributos de `vaivem` NÃO são alterados de propósito. No docker-compose
-- local ele é o `POSTGRES_USER` (superusuário criado pela imagem oficial), e as
-- fixtures de integração contam com isso para DDL e para instalar as extensões
-- num volume recém-criado. Restringi-lo aqui quebraria o ambiente local sem
-- ganho: o que precisa ser incapaz de contornar RLS é quem ATENDE requisição, e
-- isso é `vaivem_app`. No Cloud SQL o `vaivem` já nasce sem superusuário real.

-- ---------------------------------------------------------------------------
-- Privilégios
-- ---------------------------------------------------------------------------
-- O owner precisa poder criar objetos no schema; a aplicação, apenas usá-los.
GRANT ALL ON SCHEMA public TO vaivem;
GRANT USAGE ON SCHEMA public TO vaivem_app;

-- Tabelas/sequências que JÁ existem (reaplicação, ou banco migrado antes deste
-- arquivo existir).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO vaivem_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vaivem_app;

-- E as que vierem de migrations FUTURAS, criadas por `vaivem`. Sem isto, toda
-- migration que adiciona tabela exige um GRANT manual depois — e o sintoma é um
-- `permission denied` em produção, não no deploy.
ALTER DEFAULT PRIVILEGES FOR ROLE vaivem IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vaivem_app;
ALTER DEFAULT PRIVILEGES FOR ROLE vaivem IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO vaivem_app;

-- Deliberadamente NÃO concedido a `vaivem_app`: TRUNCATE (contorna o trigger de
-- imutabilidade de `eventos_aluno`, regra 7.4) e qualquer DDL. A retenção LGPD
-- (§7.5) é do B6 e vai precisar de um caminho próprio, auditado — não de DELETE
-- amplo concedido de antemão.
