# Roteiro de apresentação — VaiVem (Sprint 1)

Combina uma demo ao vivo da API (backend real, multi-tenant, com dados
seedados) com um tour pelos protótipos navegáveis em HTML. Duração estimada:
15–20 min.

## 0. Preparação (antes de abrir a sala)

1. Verifique se o projeto Supabase está com status **Healthy** no dashboard
   (projetos free-tier pausam após inatividade — restaure antes da reunião).
2. Suba a API localmente:

   ```bash
   cd backend
   source .venv/bin/activate   # ou o ambiente que você usa
   uvicorn app.main:app --reload
   ```

3. Confirme em `http://localhost:8000/docs` que o Swagger carrega.
4. Se o banco estiver vazio (primeira vez, ou ambiente novo), rode o seed:

   ```bash
   cd backend
   PYTHONPATH=. python scripts/seed_demo.py
   ```

   Isso cria um tenant de demonstração com 3 usuários, 1 veículo, 1 rota com
   1 parada, 1 aluno e 1 responsável — coerentes entre si. É idempotente: se
   o tenant já existir, o script avisa e não duplica nada.

### Credenciais de demonstração

| Papel | E-mail | Senha |
|---|---|---|
| Admin | admin@demo.vaivem.com.br | demo12345 |
| Motorista | motorista@demo.vaivem.com.br | demo12345 |
| Responsável | responsavel@demo.vaivem.com.br | demo12345 |

> Senhas só valem para este ambiente de demonstração.

## 1. Abertura (1 min)

Contexto rápido: VaiVem é uma plataforma B2B2C para transporte escolar —
transportadoras (tenants) gerenciam vans, rotas, motoristas e alunos; pais
acompanham o trajeto dos filhos. Hoje mostramos o que já está rodando: o
backend (API real, com banco de dados de produção na Supabase) e os
protótipos de tela das três pontas (motorista, responsável, gestor).

## 2. Demo ao vivo da API (8–10 min)

Abra `http://localhost:8000/docs` (Swagger).

### 2.1 Login e multi-tenancy

1. Em `POST /api/auth/login`, use as credenciais do **admin** acima.
2. Copie o `access_token` retornado e cole no botão **Authorize** (ícone de
   cadeado, topo da página), como `Bearer <token>`.
3. Explique o conceito: o token carrega o `tenant_id` do usuário. A partir
   daqui, toda consulta ao banco passa por uma política de **Row-Level
   Security** do Postgres que filtra automaticamente pelo tenant — nenhuma
   query da aplicação vê dados de outro cliente, mesmo que haja um bug na
   lógica de filtro da API (segurança "fail-closed": sem `tenant_id` setado,
   zero linhas voltam).

### 2.2 Tour pelo CRUD multi-tenant

Com o token de admin autorizado, demonstre, na ordem:

1. **`GET /api/veiculos`** — lista a van já cadastrada (Fiat Ducato, placa
   ABC1D23).
2. **`GET /api/rotas`** — mostra a "Rota Centro - Manhã".
3. **`GET /api/rotas/{rota_id}/paradas`** — a parada "Praça Central" dessa
   rota (use o `rota_id` retornado no passo anterior).
4. **`GET /api/alunos`** — o aluno "João da Silva", já vinculado à parada.
5. **`GET /api/alunos/{aluno_id}/responsaveis`** — a responsável "Maria",
   com permissões de ver localização e receber notificações.
6. **`GET /api/tenants/me`** — dados do tenant atual (plano, status de
   billing).
7. **`POST /api/veiculos`** — cadastre um veículo novo na hora, ao vivo,
   para mostrar a escrita funcionando (não só leitura).

### 2.3 RBAC (opcional, se houver tempo)

Repita o login com o usuário **motorista** ou **responsável** e mostre que
endpoints administrativos (ex.: `PATCH /api/tenants/me`) retornam `403` —
o controle de papel (admin / motorista / motorista_backup / responsável)
é checado em cada rota.

### 2.4 Consentimento LGPD

`GET /api/tenants/me/consentimentos/status` — mostra que o onboarding do
tenant inclui aceite formal do DPA (Data Processing Agreement), com versão
controlada, alinhado à LGPD.

## 3. Tour pelos protótipos (5–7 min)

Os protótipos são HTML estático (sem backend) em `docs/prototipos/` — abra
direto no navegador.

1. **`00-visao-geral-3-apps.html`** — visão panorâmica: como os três apps
   conversam entre si (motorista atualiza status → responsável recebe
   notificação → gestor acompanha tudo).
2. **`01-app-motorista.html`** — tela do motorista: escolha de turno,
   check-in de cada aluno, verificação obrigatória antes de sair, aviso a
   responsáveis, botão de emergência, registro de manutenção do veículo.
3. **`02-app-responsavel.html`** — tela do responsável: acompanhamento em
   tempo real ("Sofia está a caminho"), aviso de ausência, pagamentos,
   histórico de viagens, notificações.
4. **`03-app-gestor.html`** — painel do gestor: visão geral da operação,
   frota ao vivo, financeiro, cadastro de alunos e rotas, gestão de
   motorista backup, incidentes.

> Importante deixar claro: estas telas são protótipo visual (mockup
> navegável), ainda não conectado à API. A integração real é o próximo
> passo planejado (painel do gestor em mobile/web consumindo os endpoints
> já demonstrados na seção 2).

## 4. Encerramento (2 min)

Resumo do que está pronto vs. próximos passos:

- **Pronto e funcionando de ponta a ponta**: backend multi-tenant com RLS,
  autenticação JWT, RBAC por papel, CRUD completo de veículos/rotas/
  paradas/alunos/responsáveis, consentimento LGPD.
- **Pronto como protótipo visual**: as três interfaces (motorista,
  responsável, gestor).
- **Próximo passo**: implementar as telas reais (mobile) consumindo a API
  já demonstrada.

## Apêndice — comandos de referência

```bash
# Subir a API
cd backend && uvicorn app.main:app --reload

# (Re)criar dados de demonstração
cd backend && PYTHONPATH=. python scripts/seed_demo.py

# Swagger
# http://localhost:8000/docs
```
