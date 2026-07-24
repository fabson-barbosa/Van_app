# Plano de Sprints — Fase 1 (MVP)

**Base:** Roadmap "Fase 1 — MVP" do `arquitetura.md`.
**Estado atual do projeto (concepção):** documentação de arquitetura/financeiro pronta, protótipos de alta fidelidade dos 3 apps prontos, scaffold inicial de backend (FastAPI, só `/health`) e mobile (Expo, sem telas).
**Formato:** sprints de 2 semanas. Total estimado: 7 sprints (~14 semanas / 3,5 meses) até um MVP testável com tenant piloto.

---

## Sprint 0 — Fundamentos técnicos (setup)
**Objetivo:** sair da "concepção" para um esqueleto executável e versionado.

- Repositório e CI: pipeline (lint, testes, build) a partir do `.github/workflows/ci.yml` existente.
- Banco PostgreSQL + PostGIS provisionado (dev/staging); Redis (Upstash) configurado.
- Modelagem inicial das tabelas-núcleo (`tenants`, `users`, `veiculos`, `rotas`, `paradas`, `alunos`, `responsaveis`) com migrations (Alembic).
- `tenant_id` + Row-Level Security ativos desde a primeira tabela (decisão da arquitetura — não é opcional depois).
- Autenticação base (JWT, hashing) e estrutura de RBAC (papéis: Admin, Motorista, Motorista Backup, Responsável).
- Estrutura inicial dos 3 apps Expo (motorista, responsável, gestor) com navegação básica e build rodando.

**Entrega:** API com auth + CRUD mínimo de tenant/usuário rodando em ambiente de dev; apps mobile com tela de login.

---

## Sprint 1 — Cadastros e multi-tenancy
**Objetivo:** modelar a hierarquia `Tenant → Veículos → Rotas → Paradas → Alunos → Responsáveis`.

- CRUD completo (API + telas no app gestor) de: tenant, veículos, rotas, paradas (com geolocalização PostGIS), alunos, responsáveis.
- Vínculo aluno ↔ parada ↔ responsável (N:1 responsáveis por aluno, conforme módulo 3.6).
- Painel do gestor: listagem e edição dessas entidades, baseado no protótipo `03-app-gestor.html`.
- Onboarding do tenant: aceite do DPA (contrato de operador LGPD).

**Entrega:** um tenant consegue cadastrar sua frota, rotas, alunos e responsáveis pelo painel gestor.

---

## Sprint 2 — Tracking por evento + motor de ETA
**Objetivo:** núcleo técnico do produto — "o cérebro é o ETA, não o raio geográfico".

- Endpoint de ingestão de posição do motorista (push a cada 10–15s).
- Integração com API de rotas (Google Maps Matrix/Directions ou Mapbox) para cálculo de ETA por parada.
- Cache de ETA no Redis (mitigar custo de API — ver seção de riscos).
- Recalculo dinâmico: a cada posição nova, recalcula só as paradas pendentes.
- Fila de notificações derivada do ETA recalculado (fonte única de verdade — necessário para skipping futuro).

**Entrega:** dado um fluxo simulado de posições, o sistema calcula e atualiza ETAs por parada em tempo real.

---

## Sprint 3 — App Motorista: execução de rota
**Objetivo:** o motorista consegue rodar uma rota do início ao fim.

- Tela de seleção de rota e início de turno (`viagens`), baseada no protótipo `01-app-motorista.html`.
- Compartilhamento de posição em background com ajuste de frequência por velocidade/proximidade (economia de bateria).
- Check-in/out de alunos (NFC ou QR) e registro em `checkins`/`eventos`.
- Navegação GPS com cache de mapas da rota do dia (pré-requisito para modo offline).

**Entrega:** motorista roda uma viagem completa simulada com check-in/out funcionando.

---

## Sprint 4 — Notificações e App Responsável
**Objetivo:** levar o ETA até o responsável.

- Integração com Firebase Cloud Messaging (push como canal primário).
- Gatilho "Chegando" quando `ETA(parada) <= limiar` configurável por tenant, com anti-duplicação (1 push por par parada/responsável/turno).
- App responsável: tela de status da rota/criança e histórico de notificações, baseada no `02-app-responsavel.html`.
- Push de "chegada segura" ao final da rota.

**Entrega:** responsável recebe notificações de aproximação e chegada em tempo real durante uma viagem simulada.

---

## Sprint 5 — Segurança da criança (módulo crítico)
**Objetivo:** implementar o que a arquitetura marca como "não negociável" para Fase 1.

- Varredura obrigatória de fim de rota: app **bloqueia** finalização do turno até confirmação de "veículo vazio", com timer.
- Alerta automático à escola/responsáveis se a confirmação não ocorrer em X minutos.
- Heartbeat: detecção de ausência de sinal do motorista → alerta passivo ("rota sem sinal").
- Fila local de eventos persistida no device + sincronização automática ao recuperar sinal (modo offline básico).

**Entrega:** finalização de turno é bloqueada sem varredura confirmada; sistema alerta sobre falhas de sinal.

---

## Sprint 6 — Hardening, LGPD e piloto
**Objetivo:** preparar para operar com um tenant real.

- Revisão de RLS/RBAC ponta a ponta; testes de isolamento entre tenants.
- Consentimento in-app versionado (`consentimentos`), criptografia de dados sensíveis (médicos/localização) at rest e in transit.
- Registro de operações de tratamento (auditoria de acesso a dados de menores).
- Testes de carga do motor de ETA (custo de API sob volume real) e ajuste de cache.
- Testes end-to-end dos 3 apps com uma rota piloto real; correção de bugs críticos.

**Entrega:** MVP pronto para onboarding do primeiro tenant piloto, com compliance LGPD básica revisada.

---

## Notas de sequenciamento

- **Sprint 0 e 1 são bloqueantes** para todo o resto — sem cadastros e RLS multi-tenant, nada do motor de ETA ou apps faz sentido.
- **Sprint 2 (motor de ETA) é pré-requisito** das Sprints 3 e 4 — ambas consomem a fila derivada do ETA.
- O **botão de pânico**, **broadcast de comunicação**, **financeiro** e demais itens das Fases 2–4 ficam fora deste plano (ver `arquitetura.md`, seção 6) e devem virar um plano de sprints separado após validação do MVP.
- Risco a monitorar desde o Sprint 2: custo da API de mapas — reavaliar plano a partir de ~15–20 vans (ver `financeiro.md`).
