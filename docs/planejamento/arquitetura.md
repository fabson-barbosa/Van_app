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
mobile/           Expo, Android
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

Alembic, numeradas sequencialmente. Estado atual: `0001`–`0004`.

- `0003_rls_paradas_responsaveis` — fecha a lacuna de RLS
- `0004_trip_domain` — domínio de viagem + trigger de imutabilidade

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

## 8. Lacunas conhecidas

- Tomada de posse por `motorista_backup` — não implementada
- Retenção/expurgo LGPD — B6, fora desta rodada
- Reconciliação de eventos offline: `device_timestamp` é gravado, mas a regra de
  resolução de conflito ainda não existe (definir no B4)
- ⚠️ verificar: estratégia de índices em `eventos_aluno`, que é a tabela que mais
  cresce