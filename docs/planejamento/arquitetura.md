# ARQUITETURA.md — VaiVem

> Como o sistema é construído. O **quê** e o **porquê** do domínio estão em
> `CLAUDE.md` (fonte de verdade). Este documento cobre estrutura, infra e o
> registro de decisões estruturais já tomadas.
>
> Itens marcados **⚠️ verificar** foram inferidos do `PROGRESSO.md` e precisam
> ser conferidos contra o código antes de virarem referência.

---

## 1. Forma do sistema

```
App Motorista (Expo/Android) ─┐
                              ├─→ API FastAPI ─→ PostgreSQL (RLS por tenant)
App Responsável (Expo/Android)┘        │        └─ Redis (cache/filas)
                                       └─→ FCM (push)
```

Um serviço, um banco. Sem microsserviços, sem fila de mensagens dedicada nesta
rodada — o volume não justifica e cada peça extra é custo operacional para um
produto que ainda não vendeu.

Deploy em **Cloud Run**. Stateless: nenhum estado de viagem vive em memória do
processo, porque a instância pode morrer entre um Cheguei e um Checkin.

## 2. Layout de módulos

```
backend/
  app/
    models/       SQLAlchemy — um arquivo por agregado
    api/          rotas HTTP; deps.py concentra auth e injeção de tenant
    core/         security.py (JWT), config, sessão de banco
    services/     regras de domínio (máquina de estados, motor de tempos)
  migrations/     Alembic — numeradas 0001…
  scripts/        seed_demo.py e utilitários
mobile/           Expo, Android — SDK 54 (ver §9). UM projeto só, servindo
                  Motorista E Responsável (ver §9) — `src/motorista/`,
                  `src/responsavel/`, `src/shared/` (client HTTP, auth,
                  tema, componentes, push).
docs/
  planejamento/   BACKLOG-futuro.md (histórico, não é requisito)
```

Regra: **regra de domínio não mora em `api/`.** Endpoints validam entrada,
chamam `services/` e serializam saída. A máquina de estados do B2 precisa ser
testável sem HTTP.

## 3. Multi-tenancy

Isolamento por **Row-Level Security no Postgres**, não por filtro na aplicação.

- Toda tabela de dados de cliente tem `tenant_id` **próprio** — nunca isolamento
  por join com a tabela pai. Foi essa a lacuna corrigida na migration `0003`
  (`paradas` e `responsaveis`).
- Policies são **fail-closed**: sessão sem tenant setado enxerga zero linhas.
- O tenant da sessão é setado no início de cada request, em `api/deps.py`.
  ⚠️ verificar o mecanismo exato (`SET LOCAL` por transação é o correto —
  variável de sessão em pool de conexões vaza entre requests).

Esquecer o `tenant_id` numa tabela nova é a falha mais cara possível neste
sistema. Ao criar qualquer model, a pergunta obrigatória é: tem `TenantMixin`?

## 4. Autenticação e papéis

JWT em `core/security.py`, RBAC em `api/deps.py`.

Enum canônico: `admin` · `motorista` · `motorista_backup` · `responsavel`.

`motorista_backup` existe para mitigar o celular do motorista como ponto único
de falha — outro aparelho assume uma viagem em andamento. A tomada de posse
ainda **não está implementada**; hoje o papel só existe no enum.

## 5. Decisões estruturais registradas (B1)

Estas moldam código futuro. Não reinventar no B2–B5.

| Decisão | Por quê |
|---|---|
| `motoristas` é tabela de **perfil** (`user_id`, CNH, telefone), e `Viagem.motorista_id` aponta para ela — não para `users` | Mesmo padrão de `Responsavel`. Dados de habilitação não pertencem à tabela de autenticação. |
| `TripStudent.parada_id` é **snapshot** do ponto de embarque | Endereço do aluno muda; o histórico da viagem não pode mudar junto. |
| `TripStudent.ordem` é da **viagem**, não da rota (`Parada.ordem_base`) | Permite reordenar antes do Cheguei sem alterar o gabarito da rota. |
| `eventos_aluno` é append-only por **trigger de banco** | Imutabilidade da auditoria não pode depender de disciplina da API. |
| `Viagem` carrega `atraso_acumulado_segundos` e `varredura_confirmada` como colunas | Estado derivado, mas consultado a cada push; recalcular por evento sairia caro. |
| `leg_durations`: `dia_semana` = `date.weekday()` (0=segunda), `faixa_horaria` = hora cheia 0–23 | Convenção fixada porque o CLAUDE.md não especificava. |

## 6. Migrations

Alembic, numeradas sequencialmente. Estado atual: `0001`–`0008`.

- `0003_rls_paradas_responsaveis` — fecha a lacuna de RLS
- `0004_trip_domain` — domínio de viagem + trigger de imutabilidade
- `0008_reconciliacao_temporal` — reconciliação de relógio + idempotência de
  evento (Bloco B4, ver §8). Precisou desligar/religar o trigger de `0004`
  em volta do próprio backfill — ele bloqueia UPDATE mesmo pro owner da
  migration.
- `0009_device_tokens` — registro de token de push (Bloco B5, ver §9).
  Nasce direto com o guard `NULLIF` da `0006` — não precisou de migration
  de correção depois, diferente da `0004`.

**Toda migration que cria tabela com dados de cliente deve criar a policy de RLS
na mesma migration.** Tabela sem policy é tabela pública.

Validação só com `alembic upgrade head --sql` não basta: modo offline não
exercita policy nem trigger. Exigir Postgres real.

## 7. Testes

Prioridade nesta rodada, nesta ordem:

1. Máquina de estados (transições válidas e, principalmente, as **inválidas**)
2. Aritmética do motor de tempos (trajeto vs. dwell, aluno ausente)
3. Isolamento de RLS entre tenants
4. Varredura final bloqueante

O resto é opcional. Estes quatro são onde erro vira criança esquecida na van ou
vazamento entre operadores.

## 9. Mobile — SDK e arquitetura do app único (Blocos B4/B5)

- **Expo SDK 54** (não 51, a versão original do B4). Upgrade feito no meio
  do B4, testando em aparelho físico: o Expo Go instalado vem sempre com o
  SDK mais recente publicado na loja, e o cliente publicado só abre
  projetos do MESMO SDK major com que foi compilado — o projeto precisa
  acompanhar o que está na Play Store, não o contrário. Se o Expo Go da
  loja subir de major de novo, repetir o fluxo documentado em PROGRESSO.md
  (Bloco B4): `npm install expo@<nova>` → `npx expo install --fix` →
  ajuste manual de `@types/react`/`jest-expo` → conferir se
  `babel-preset-expo` ainda precisa ser dependência explícita.
- **Um único projeto Expo para Motorista E Responsável** (Bloco B5),
  ramificado por `role` (claim do JWT, decodificado só pra escolher a
  stack — `shared/auth/jwt.ts`, nunca é fonte de autorização). CLAUDE.md
  fala em "três apps" como três EXPERIÊNCIAS/produtos; na prática, sem
  tooling de monorepo no projeto e com o pedido explícito de reaproveitar
  `mobile/src/shared`, um app único com roteamento por papel é a
  interpretação adotada nesta rodada. `app.json` (nome "VaiVem Motorista",
  `package br.com.vaivem.motorista`) ficou como estava — cosmético,
  reavaliar se um dia isso precisar virar dois apps de verdade na Play
  Store (dois `package`, duas fichas).
- **Push real via Expo Push Service, não FCM direto** (Bloco B5). O app
  roda em Expo Go — token nativo de FCM não funciona nesse modo (exigiria
  um dev client custom via EAS build). O Expo Push Service entrega no
  Android via FCM por baixo, sem exigir projeto Firebase próprio.
  `device_tokens.provider` (migration `0009`) guarda isso desde já —
  trocar de provider no futuro (se o app sair do Expo Go) é um novo
  `FCMSender` (`app/services/expo_push.py`), não uma migration. Registro
  de token exige um `projectId` de EAS (gratuito, `eas init`) mesmo dentro
  do Expo Go — tratado como best-effort no app: sem isso configurado, o
  app funciona normalmente, só sem push.
- **Notificação persistente sem foreground service**: confirmado que
  `usesChronometer`/`showWhen` do `Notification.Builder` nativo não são
  expostos pela API cross-platform do `expo-notifications` — exigiria
  native module próprio (mesma parede que descarta FCM direto). Fallback:
  `sticky: true` (nunca some sozinha) + texto reescrito a cada ~45s
  enquanto o app está vivo. Ver PROGRESSO.md Bloco B5 para o detalhe.

## 10. Lacunas conhecidas

- Tomada de posse por `motorista_backup` — não implementada
- Retenção/expurgo LGPD — B6, fora desta rodada
- ~~Envio de push (`StubFCMSender`)~~ — **fechado no B5.** `app/services/expo_push.py::ExpoPushSender`
  entrega de verdade via Expo Push Service (ver §9). `StubFCMSender` continua existindo só para teste.
- ~~Reconciliação de eventos offline~~ — **fechada no B4.**
  `eventos_aluno` tem três relógios: `ocorrido_em` (instante reconciliado —
  `device_timestamp` + offset contra o servidor, `app/services/reconciliacao.py`;
  alimenta `chegou_em`/`checkin_em` e o motor de tempos), `registrado_em`
  (quando o servidor recebeu — auditoria, e é contra ELE, nunca contra o
  aparelho, que a janela de 60s do desfazer-checkin é medida —
  `trip_students.checkin_registrado_em` guarda o lado do Checkin dessa
  comparação), `device_timestamp` (valor cru, forense). Offset com clamp de
  ±24h; fora disso ou faltando dado do aparelho, cai no relógio do servidor
  com `confiavel=False` (não vira amostra de `leg_duration`). Migration
  `0008_reconciliacao_temporal`. Idempotência de reenvio via `event_id`
  (gerado no aparelho, único no banco) resolvida junto, no mesmo bloco.
- ⚠️ verificar: estratégia de índices em `eventos_aluno`, que é a tabela que mais
  cresce