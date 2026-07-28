# PROGRESSO.md

> Atualizado ao final de cada bloco (CLAUDE.md §9), antes do `/clear`.

## Bloco B1 — Modelos, Alembic, RLS, JWT/RBAC, seed — **concluído**

### Contexto encontrado

Já existia uma implementação parcial (`Tenant`, `User`, `Veiculo`, `Rota`,
`Parada`, `Aluno`, `Responsavel`, `Consentimento` + JWT/RBAC + RLS básica),
construída contra `docs/planejamento/arquitetura.md` — um plano mais antigo,
de escopo maior que o CLAUDE.md atual (GPS em tempo real, NFC, financeiro).
O B1 reaproveitou essa base e completou o que faltava para fechar o bloco.

### Decisões tomadas com o usuário (ambiguidades do CLAUDE.md)

1. **RBAC**: CLAUDE.md §3 cita papéis `gestor/motorista/responsavel`, mas o
   enum já migrado é `admin/motorista/motorista_backup/responsavel`.
   **Decisão: manter o enum como está** (não renomear `admin`→`gestor`, não
   remover `motorista_backup`). Nenhuma migration de enum foi criada.
2. **`motorista` como modelo**: criado como tabela de perfil própria
   (`motoristas`: `user_id`, `cnh_numero`, `cnh_categoria`, `telefone`,
   `ativo`), vinculada a um `User` com `role=motorista` — mesmo padrão já
   usado por `Responsavel`. `Viagem.motorista_id` referencia `motoristas.id`,
   não `users.id` diretamente.
3. **Lacuna de RLS pré-existente**: `paradas` e `responsaveis` não tinham
   `tenant_id` nem RLS (isolamento dependia de join manual com
   `rotas`/`alunos` na aplicação — contraria a decisão "não pode depender da
   camada de aplicação"). **Corrigido**: migration `0003` adiciona
   `tenant_id` (backfill do pai) + policy fail-closed nas duas tabelas.
   Os endpoints `POST /api/rotas/{id}/paradas` e
   `POST /api/alunos/{id}/responsaveis` foram ajustados para preencherem
   `tenant_id` no INSERT (antes não precisavam, porque a coluna não existia).

### O que foi feito

- **Models novos** (`backend/app/models/`): `motorista.py`, `viagem.py`
  (`ViagemStatus`), `trip_student.py` (`TripStudentEstado`),
  `evento_aluno.py` (`EventoAlunoTipo`), `leg_duration.py`. Todos com
  `TenantMixin` (RLS direta, sem depender de join).
- **Models existentes ajustados**: `Parada` e `Responsavel` passaram a
  herdar `TenantMixin`.
- **Migrations** (`backend/migrations/versions/`):
  - `0003_rls_paradas_responsaveis`: fecha a lacuna de RLS descrita acima.
  - `0004_trip_domain`: cria `motoristas`, `viagens`, `trip_students`,
    `eventos_aluno`, `leg_durations` + RLS fail-closed em todas + **trigger
    de banco que bloqueia UPDATE/DELETE em `eventos_aluno`** (regra
    inviolável 7.4 — imutabilidade não depende de disciplina da API).
  - Validado com `alembic upgrade head --sql` (modo offline, sem banco): as
    4 migrations aplicam em sequência sem erro e o SQL gerado foi revisado
    manualmente (tabelas, FKs, índices, enums, policies, trigger).
  - **Não foi possível rodar contra um Postgres real** (nenhuma instância
    Postgres/Docker disponível neste ambiente). Antes do B2, rodar
    `alembic upgrade head` num Postgres com PostGIS de verdade para
    confirmar o trigger de imutabilidade e as policies de RLS em runtime.
- **Auth JWT + RBAC**: mecanismo já existia (`core/security.py`,
  `api/deps.py`, `api/auth.py`) e não precisou mudar — decisão 1 manteve o
  enum atual.
- **Seed** (`backend/scripts/seed_demo.py`): reescrito para 1 tenant, 2 rotas
  (`Rota Centro - Manhã`, `Rota Jardim das Flores - Manhã`), 12 alunos (6 por
  rota, cada um com parada e responsável próprios), 2 motoristas (perfil +
  user), 2 veículos, 1 admin. Idempotente (mesmo padrão anterior — aborta se
  o tenant demo já existir). Confirmado: `len(ROTAS_DEMO)==2`,
  soma de alunos `==12`.
- Rodado: `python -m py_compile` em todos os arquivos tocados, import de
  `app.main` e `app.models` (registra as 13 tabelas em `Base.metadata`),
  `alembic upgrade head --sql`.

### Design decisions não bloqueantes (documentadas nos docstrings dos models)

- `TripStudent.ordem` é específico da viagem (não `Parada.ordem_base`) —
  permite reordenar antes do Cheguei (§8) sem alterar o gabarito da rota.
- `TripStudent.parada_id` é um snapshot do ponto de embarque no momento da
  viagem (endereço do aluno pode mudar depois sem afetar histórico).
- `leg_durations`: `dia_semana` = `date.weekday()` (0=segunda), `faixa_horaria`
  = hora cheia 0-23. Convenção definida aqui pois o CLAUDE.md não especifica.
- `Viagem` carrega `atraso_acumulado_segundos` e `varredura_confirmada` como
  colunas; a lógica que os popula/valida é do **B2**.

### Pendências / TODOs explícitos

- **Retenção LGPD (regra inviolável 7.5)**: não está atribuída a nenhum
  bloco em §9. B1 não criou tabela/coluna de política de retenção — ficou
  como TODO para um bloco futuro (hardening/LGPD), já que não está no
  escopo de modelos do B1.
- Validar migrations contra Postgres+PostGIS real (ver acima).
- B2 (próximo bloco): máquina de estados (Cheguei/Checkin/Checkout),
  varredura final bloqueante, escrita em `eventos_aluno` — nada disso foi
  implementado agora, só o schema.

### Fora de escopo (não implementado, conforme CLAUDE.md §10)

GPS em tempo real, NFC, confirmação de desembarque pelo responsável, Gestor
funcional, billing/assinaturas, painel web, iOS.

---

## Bloco B2 — Máquina de estados, Cheguei/Checkin/Checkout, varredura final, auditoria — **concluído (lógica); validação de banco PENDENTE**

### Ambiguidades do CLAUDE.md §4/§7/§8 — decididas com o usuário antes de codar

1. **Ausente direto de `aguardando`** (sem passar por `chegou`): **permitido**
   — cobre o responsável avisando antecipadamente que o aluno não vai pegar a
   van. Sem `chegou_em`, não há dwell (não grava nem como zero). CLAUDE.md §4
   foi atualizado com essa seta antes da implementação.
2. **Undo do Checkin** (§8 menciona "undo de 30s", mas o diagrama do §4 não
   desenhava a seta): é transição real e server-side, `a_bordo` → `chegou`,
   evento `DESFAZER_CHECKIN` (novo valor no enum `evento_aluno_tipo`, migration
   `0005`). Janela: 30s na UI, **60s aceitos no servidor** (latência + fila
   offline); fora da janela, `JanelaDesfazerExpiradaError`. CLAUDE.md §4
   atualizado com essa seta também.
3. **§7.2 (resolução forçada)**: `Cheguei(alvo)` é bloqueado
   (`ParadaAnteriorPendenteError`) se existir outro `trip_student` da mesma
   viagem com **ordem menor** ainda em `chegou`. Alunos da mesma parada (mesma
   ordem) não bloqueiam entre si. O erro carrega a lista de pendentes, para a
   UI abrir direto na resolução.
4. **Ciclo de vida de `Viagem` pertence ao B2** (varredura final depende
   dele): `planejada` → `em_andamento` → `finalizada`.
   - `iniciar_viagem`: monta os `trip_students` a partir do gabarito da rota
     (join `Aluno`→`Parada` por `rota_id`, alunos ativos), congelando
     `ordem`/`parada_id` no momento do início.
   - Nenhum evento de aluno é aceito fora de `em_andamento` — guarda
     (`ViagemStatusInvalidoError`) em toda transição, inclusive reordenar.
   - `finalizar_viagem`: varredura final bloqueante (regra inviolável 7.1);
     `VarreduraFinalPendenteError.algum_a_bordo` sinaliza o caso mais grave
     (aluno esquecido a bordo) para a camada de API disparar alerta duro —
     o envio da notificação ao gestor em si **não** está implementado (é
     integração de agendador, fora do escopo do B2; ver TODO abaixo).
   - Reordenar (`PATCH /trip-students/reordenar`): só alunos ainda
     `aguardando` (`ReordenacaoInvalidaError` caso contrário).
   - Status `cancelada` fica **fora do B2** — ver TODO.

### O que foi feito

- **`services/` (lógica pura, sem HTTP, sem sessão de banco)**:
  `trip_state_machine.py` — todas as transições do §4, `iniciar_viagem`,
  `finalizar_viagem`, `reordenar`; `exceptions.py` — exceções de domínio
  explícitas (`TransicaoInvalidaError`, `ParadaAnteriorPendenteError`,
  `JanelaDesfazerExpiradaError`, `ViagemStatusInvalidoError`,
  `ReordenacaoInvalidaError`, `TripStudentDesconhecidoError`,
  `VarreduraFinalPendenteError`). Toda função recebe o relógio (`now=`) como
  parâmetro — testável sem banco.
- **`api/viagens.py`** (fino): CRUD de viagem (criação é `admin`-only, como os
  outros cadastros), `iniciar`/`finalizar`, listagem/leitura de
  `trip_students`, reordenação, e os 6 endpoints de evento (Cheguei, Checkin,
  Checkout, Ausente, Desfazer chegada, Desfazer checkin). Papéis autorizados:
  `admin`, `motorista`, `motorista_backup` (mitigação de dispositivo único de
  falha, CLAUDE.md §3/§11). Fora do papel admin, acesso restrito às viagens do
  próprio motorista (404 em vez de 403, para não vazar existência).
- **Modelos ajustados**:
  - `EventoAluno`: novo campo `estado_anterior` (reaproveita o enum
    `trip_student_estado`) — é o que distingue, sem ambiguidade, um `ausente`
    direto de `aguardando` (pulado) de um `ausente` vindo de `chegou`. Novo
    valor `desfazer_checkin` no enum `evento_aluno_tipo`.
  - `TripStudent`/`Viagem`: corrigido `chegou_em`/`checkin_em`/`checkout_em`/
    `ausente_em`/`iniciada_em`/`finalizada_em` para `DateTime(timezone=True)`
    explícito — as migrations do B1 já criavam essas colunas como `TIMESTAMP
    WITH TIME ZONE`, mas o mapeamento Python inferia naive; isso quebraria a
    aritmética da janela de 60s do desfazer-checkin (e geraria diff espúrio
    em `alembic revision --autogenerate`, já que `env.py` usa
    `compare_type=True`). Nenhuma migration nova foi necessária para esse
    ajuste (o tipo da coluna no banco já estava certo).
- **Migration `0005_desfazer_checkin`**: adiciona `desfazer_checkin` ao enum
  `evento_aluno_tipo` e a coluna `eventos_aluno.estado_anterior`. Validada com
  `alembic upgrade head --sql` (offline) em sequência com 0001-0004.
- **Testes unitários** (`tests/test_trip_state_machine.py`, 27 casos, **sem
  banco**): caminho feliz completo, ausente de `aguardando` vs. de `chegou`,
  todas as transições inválidas (§4), §7.2 (bloqueio e não-bloqueio por
  ordem), desfazer chegada, desfazer checkin (dentro/fora da janela), guarda
  de status da viagem, iniciar/finalizar (incluindo `algum_a_bordo`),
  reordenar (sucesso, aluno inválido, id desconhecido). `pytest` roda tudo
  isso por padrão (`27 passed`).
- **Testes de integração** (`tests/integration/`, `@pytest.mark.integration`
  — não rodam no `pytest` padrão, `pytest.ini` exclui via `addopts`): RLS
  fail-closed nas tabelas do domínio de viagem, trigger de imutabilidade de
  `eventos_aluno` (UPDATE e DELETE), fluxo ponta-a-ponta iniciar → Cheguei →
  Checkin → Checkout → finalizar contra Postgres real. **Escritos mas não
  executados** (sem Postgres neste ambiente).
- Rodado: `python -m py_compile` em todos os arquivos tocados/criados, import
  de `app.main`/`app.models`, `alembic upgrade head --sql`.

### Portão de validação (CLAUDE.md §9) — **quitado**

Ambiente local: `docker-compose.yml` (raiz do repo) sobe `postgis/postgis:16-3.4`
+ `redis:7-alpine`. Role `vaivem` (superuser, criado pela imagem oficial via
`POSTGRES_USER`) é o owner e roda as migrations; role `vaivem_app` (LOGIN,
sem superuser/createdb/createrole/bypassrls, GRANTs table-a-table + `ALTER
DEFAULT PRIVILEGES` para migrations futuras) é quem a aplicação e os testes
usam — necessário porque um role com `BYPASSRLS` (todo superuser) ignora RLS
mesmo com `FORCE ROW LEVEL SECURITY`, o que tornaria os testes de RLS inúteis
se rodassem como owner. `backend/.env` aponta para `vaivem_app`.

Resultado dos 6 itens do gate, validados em runtime (Postgres real, não
`--sql` offline):

| Item | Resultado |
|---|---|
| (a) RLS fail-closed sem tenant setado | ✅ PASS |
| (b) Isolamento entre tenants (leitura + escrita cruzada rejeitada) | ✅ PASS |
| (c) `SET LOCAL` por transação, não `SET` de sessão | ❌ FALHOU na 1ª rodada → **corrigido** (ver abaixo) → ✅ PASS na revalidação |
| (d) Trigger de `eventos_aluno` rejeita UPDATE/DELETE (mesmo para o owner) | ✅ PASS |
| (e) `alembic downgrade base` + `upgrade head` | ✅ PASS |
| (f) Seed roda 2x sem duplicar (2 rotas, 12 alunos) | ✅ PASS |

**Achado estrutural em (c) e correção.** `app/api/deps.py::get_tenant_db` e
`scripts/seed_demo.py` chamavam `set_config('app.tenant_id', valor, false)`
— terceiro argumento `false` = escopo de **sessão**, não de transação. A
engine usa pool de conexões (`app/core/db.py`); uma conexão física é
reaproveitada entre requests de tenants diferentes. Provado em runtime: com
`false`, o `app.tenant_id` de um request sobrevive ao `COMMIT` e fica
"grudado" na conexão até o próximo `set_config` explícito — qualquer código
futuro que reutilizasse essa conexão sem passar por `get_tenant_db` herdaria
silenciosamente o tenant do request anterior em vez de falhar fechado
(contradiz o próprio comentário do arquivo e a regra 7.3 do CLAUDE.md).

Correção aplicada (`false` → `true`, escopo de transação) trouxe dois efeitos
colaterais que só apareceram testando contra Postgres real, também corrigidos
antes de fechar o gate:

1. **Uma sessão pode abrir mais de uma transação por request** — cada
   `db.commit()` de um endpoint fecha a corrente; a próxima query reabre uma
   nova via autobegin do SQLAlchemy, e `set_config(..., true)` só vale para a
   transação em que foi chamado. `get_tenant_db` agora registra um listener
   `after_begin` na sessão que reaplica o `set_config` toda vez que uma
   transação nova começa — não só uma vez no início do generator.
2. **GUC placeholder tocada reseta para string vazia (`''`), não `NULL`.**
   Uma vez que `app.tenant_id` é setada numa conexão (mesmo com escopo
   local, mesmo já resetada), `current_setting('app.tenant_id', true)` volta
   `''` no fim da transação — e o cast `::uuid` das políticas de RLS
   quebrava com `invalid input syntax for type uuid: ""` em vez de devolver
   zero linhas. Nova migration `0006_rls_guard_empty_tenant_guc` blinda as
   11 políticas (`NULLIF(current_setting(...), '')::uuid`) para que o reset
   vire fail-closed silencioso, não erro 500.

Também documentado (não removido — é necessário para o login funcionar antes
de saber o tenant, ver comentário em `migrations/0001_initial_schema.py`):
`app/core/db.py::get_db` (usado só por `app/api/auth.py`) agora tem aviso
explícito de que não seta `app.tenant_id` e não deve ser usado em nenhuma
rota que toque tabela com `tenant_id`.

**Testes de regressão** (`tests/integration/test_rls_and_triggers.py`,
`pytest -m integration`) travam a correção:
- `test_set_config_local_nao_vaza_para_proxima_transacao_na_mesma_conexao`:
  duas transações seguidas na mesma conexão física, tenants diferentes — a
  segunda, sem setar tenant, tem que ver zero linhas.
- `test_set_config_local_guc_tocada_e_resetada_nao_gera_erro_de_cast`: prova
  o efeito colateral 2 acima e que a migration `0006` neutraliza o erro.
- `test_get_tenant_db_reaplica_tenant_apos_commit_no_meio_do_request`: prova
  o efeito colateral 1 acima direto na dependency `get_tenant_db`.

De brinde: a suíte de integração já existia mas nunca tinha rodado contra um
Postgres real (o comentário do próprio arquivo dizia isso). Ao rodar pela
primeira vez, `_alembic_upgrade_head` em `conftest.py` falhava porque tentava
rodar migrations com as credenciais de `vaivem_app` (sem privilégio de DDL)
— corrigido para sempre usar a URL do owner nesse fixture, independente do
`DATABASE_URL` usado pelo resto da suíte. E `test_rls_fail_closed_sem_tenant_setado`
acessava `viagem.id` depois do `commit()` (atributo expirado) dentro de uma
transação onde o tenant já tinha sido limpo — o refresh implícito, barrado
pelo RLS, virava `ObjectDeletedError` em vez de devolver lista vazia; corrigido
capturando o id antes do commit. `pytest -m integration` (6 testes) e
`pytest` padrão (27 testes) passam limpos.

### Pendências / TODOs explícitos

- **Cascata de notificações (§5)** e **agendador FCM**: não implementados —
  são do B3. O B2 só garante que a informação necessária (ex.: `algum_a_bordo`
  na varredura final, `estado_anterior` nos eventos) existe para o B3
  consumir.
- **`leg_duration`/`atraso_acumulado_segundos`**: não populados neste bloco —
  B3.
- **Status `cancelada` da viagem**: fora do B2. Falta definir o que acontece
  com alunos já `a_bordo` quando uma viagem é cancelada no meio.
- **Notificação ao gestor quando há aluno esquecido a bordo (§7.1)**: o
  serviço sinaliza `algum_a_bordo=True` na exceção de varredura final
  pendente, mas o envio real da notificação não está implementado (depende
  do agendador do B3).

---

## Bloco B3 — Aprendizado de tempos, projeção da cauda, agendador de notificações — **concluído**

### Desenho aprovado antes de codar

Apresentei o modelo de dados do agendador (`notificacoes_agendadas`: estado
`agendado/enviado/cancelado` persistido, índice único PARCIAL
`WHERE estado='agendado'` em `(trip_student_id, destinatario_user_id, tipo)`
como mecanismo de idempotência) e as ambiguidades do CLAUDE.md §5. Decisões
tomadas com o usuário:

1. **Média móvel de `leg_duration`**: EWMA com `alpha=0.3` (não cumulativa).
   Amostra inválida (negativa/zero, ou > 3x a média de referência — relógio
   torto em evento offline) é descartada, nunca incorporada.
2. **`atraso_acumulado_segundos`**: só diagnóstico/exibição (gestor).
   `chegou_em(parada atual) - iniciada_em - previsto`. **NÃO** entra em
   `projetar_cauda` — a projeção ancora no último evento real, que já embute
   o atraso; somar de novo contaria em dobro. Criado um segundo campo,
   `atraso_manual_segundos` (novo, só do botão "Estou atrasado"), que É o
   que entra na projeção — são dois números com papéis diferentes, não
   intercambiáveis.
3. **Semente do trajeto**: `Parada.duracao_estimada_segundos` (nova coluna,
   nullable — migration `0007`), preenchida no cadastro da rota. `None` ->
   padrão de 240s.
4. **Dwell**: calculado sob demanda a partir de `trip_students`
   (`app/services/dwell.py`), sem tabela nova — CLAUDE.md pede estatística
   de diagnóstico, não memória entre viagens como `leg_duration` tem.
5. **Correção pedida no agendador**: proteger contra corrida entre o worker
   e um cancelamento concorrente — `SELECT ... FOR UPDATE SKIP LOCKED`,
   processando uma linha por vez, cada uma em sua própria transação.

### Achado durante a implementação — efeito colateral do `atraso_manual_segundos`

Ao formalizar "estou atrasado empurra a cauda", ficou claro que
`atraso_acumulado_segundos` (só diagnóstico, decisão 2 acima) não dava conta
disso sozinho — a projeção precisava de um número que sobrevivesse entre
eventos e fosse somado por cima do `anchor`. Resolvido com uma segunda coluna
nova (`Viagem.atraso_manual_segundos`, migration `0007`) em vez de sobrecarregar
o campo já definido como diagnóstico — documentado no docstring de
`app/models/viagem.py` para não se confundirem de novo no futuro.

### Decisões de implementação não levadas de volta para aprovação (documentar aqui, não silenciar)

- **Antecedência do aviso de preparo**: CLAUDE.md não define quando,
  exatamente, o aviso "faltam ~X min" deve disparar antes da chegada.
  Escolhido `PREPARO_ANTECEDENCIA_SEGUNDOS = 5min` (`app/services/pos_evento.py`)
  — o agendamento é `ETA(N+2) - 5min`, e a faixa exibida no payload reflete
  essa MESMA antecedência (~5-10min), para o texto continuar batendo com a
  realidade no momento em que a notificação realmente dispara, não no
  momento em que foi agendada.
- **"N+1"/"N+2" pulam quem já é terminal**: interpretação de "próximas
  paradas" como as próximas NÃO resolvidas (pula `ausente`), não
  literalmente `ordem+1`/`ordem+2` — notificar o responsável de um aluno já
  marcado ausente sobre "é a próxima" não faz sentido. `_n_esimo_nao_terminal`
  em `pos_evento.py`.
- **`atraso_acumulado_segundos` usa `leg_durations` "de agora", não um
  snapshot congelado no instante exato do início da viagem**: uma previsão
  verdadeiramente congelada exigiria uma coluna nova por `trip_student`
  (fora do que foi aprovado). Como o campo é só exibição/diagnóstico (decisão
  2), uma pequena deriva ao longo da viagem foi aceita como simplificação —
  documentado no docstring de `app/services/projecao.py`.
- **Desfazer um evento depois que uma amostra de `leg_duration` já foi
  gravada não desfaz a amostra** (reverter um EWMA já misturado exigiria
  guardar histórico completo, não pedido). Impacto pequeno, janela curta
  (60s pro desfazer checkin) — documentado em `pos_evento.py`.
- **`desfazer_checkin` cancela o preparo recalculando "quem seria N+2 agora"**,
  não rastreando qual notificação aquele checkin específico originou (o
  modelo não guarda essa proveniência). Na janela de 60s isso quase sempre
  acerta o alvo certo; no raro caso de outro evento ter mudado a posição de
  N+2 no meio do caminho, o próximo evento real corrige via
  `_recalcular_e_reagendar` de qualquer forma.
- **Recipientes de notificação respeitam `Responsavel.permissoes.receber_notificacoes`**
  (campo que já existia desde o seed do B1) — permissivo por padrão se a
  chave não existir, pra não quebrar responsáveis cadastrados antes dessa
  flag existir.

### O que foi feito

- **Migration `0007_notificacoes_e_estimativas`**: tabela `notificacoes_agendadas`
  (RLS fail-closed com o guard `NULLIF` da `0006`, índice único parcial), coluna
  `paradas.duracao_estimada_segundos`, coluna `viagens.atraso_manual_segundos`.
  Validada em runtime: `alembic downgrade -1` + `upgrade head` isolados, e um
  ciclo completo `downgrade base` + `upgrade head` também rodado (ver seção
  do gate acima).
- **`app/services/leg_duration.py`** (puro): `validar_amostra`, `registrar_amostra`
  (EWMA, semente como prior só na 1ª amostra real de um bucket), `escolher_estimativa`
  (agregação progressiva §5 — dia+hora ≥5 amostras -> dia ≥5 -> geral >0 -> semente).
- **`app/services/projecao.py`** (puro): `previsao_acumulada_ate`,
  `calcular_atraso_acumulado`, `projetar_cauda`.
- **`app/services/notificacoes.py`** (puro): `faixa_minutos`/`montar_payload_preparo`
  (payload ESTRUTURADO, não texto pronto — redação é do app cliente, B4/B5),
  `deve_notificar`, `FCMSender` (Protocol) + `StubFCMSender`.
- **`app/services/dwell.py`** (puro): `calcular_dwell_segundos` — `None`
  (nunca zero) se aluno pulado ou ainda sem checkin.
- **`app/services/pos_evento.py`** (orquestração — DB, chamado pela API na
  mesma transação de cada evento): grava amostra de trajeto em `Cheguei`
  (descarta se a parada anterior foi pulada), atualiza
  `atraso_acumulado_segundos`, dispara `chegada`/`iminência` imediatas,
  agenda `preparo` em `Checkin`, cancela nos gatilhos críticos (`ausente`,
  `desfazer_checkin`, `reordenar`), reagenda em qualquer recálculo
  (`estou_atrasado` incluso).
- **`app/services/agendador.py`**: `processar_notificacoes_pendentes` —
  `SELECT ... FOR UPDATE SKIP LOCKED`, uma linha por transação, idempotente.
- **`backend/scripts/processar_notificacoes.py`**: entrypoint (cron/Cloud
  Scheduler externo — cadência é decisão de deploy, fora de escopo). Itera
  tenant por tenant (não há sessão RLS "global"), com o mesmo listener
  `after_begin` de `get_tenant_db` (necessário pelo mesmo motivo do achado
  do gate: `set_config` local morre a cada `commit()`, e o processador
  comita uma vez por notificação enviada).
- **`app/api/viagens.py`**: todos os 6 endpoints de evento + `reordenar`
  passam a chamar `pos_evento` antes do commit; novo endpoint
  `POST /{viagem_id}/estou-atrasado`.
- **Schemas**: `ParadaCreate/Update/Out` ganham `duracao_estimada_segundos`;
  novo `EstouAtrasadoRequest`.

### Testes

- **Unitários, sem banco** (73 no total, incluindo B1/B2): `test_leg_duration.py`
  (EWMA exato, outlier, agregação progressiva), `test_projecao.py` (soma
  cumulativa, atraso não entra na projeção, atraso manual entra),
  `test_notificacoes.py` (faixa de minutos, permissão), `test_dwell.py`
  (aluno ausente/sem checkin -> `None`, nunca zero), `test_pos_evento_helpers.py`
  (posicionamento N+1/N+2 pulando terminal, âncora da parada anterior —
  inclusive "casa pulada" sem `checkin_em`).
- **Integração, Postgres real** (20 no total, incluindo B1/B2):
  `test_leg_duration_integracao.py` (amostra persistida corretamente, casa
  pulada não gera linha nenhuma, agregação progressiva lê certo do banco),
  `test_notificacoes_agendamento.py` (imediatas enviadas corretas, preparo
  agendado, e — o pedido mais crítico — cada gatilho de cancelamento
  realmente cancela: `desfazer_checkin`, `ausente`, `reordenar`; "estou
  atrasado" reagenda em vez de duplicar), `test_agendador.py` (idempotência:
  reprocessar não duplica envio; **corrida**: cancelamento concorrente
  durante o processamento — duas `Session`/conexões físicas separadas,
  `FOR UPDATE SKIP LOCKED` — nunca envia).
- `pytest` (79 passed) e `pytest -m integration` (21 passed) limpos. Seed
  roda idempotente sem quebrar com as colunas novas.

### Correção pós-revisão — antecedência do preparo é POSICIONAL, não temporal

Revisão apontou um bug real no piso fixo de 5min: se o trecho até a PRÓXIMA
parada (N+1) é curto, "é a próxima" (iminência de N+2, disparada quando
Cheguei(N+1) acontece) pode disparar DEPOIS do preparo de N+2 ser agendado
com um "5min antes do ETA de N+2" ingênuo — a cascata inverte (preparo, que
deveria ser o aviso mais cedo/suave, chegando depois do aviso mais tardio/
urgente). A causa raiz: a antecedência do preparo precisa ser ancorada na
POSIÇÃO (nunca depois de quando a parada anterior é alcançada), não só num
número fixo de minutos antes do alvo.

**Correção** (`app/services/pos_evento.py`):
`agendado_para = min(max(agora, ETA(N+2) − 5min), ETA(N+1))` — o piso de
5min continua a intenção por padrão, mas nunca pode passar do ETA da parada
FISICAMENTE anterior ao alvo (`_eta_parada_anterior`, `_agendado_para_preparo`).
Isso exigiu expor `projecao.etas_por_ordem` (ETA por ORDEM, não só por
`trip_student` pendente — inclui paradas de alunos já terminais, porque o
trecho físico ainda é percorrido) como a base de onde tirar o teto; `projetar_cauda`
foi refatorado para usá-la por baixo (assinatura pública inalterada). O
payload da notificação (`faixa_min_baixo/alto`) agora reflete a antecedência
REAL (depois do clamp), não sempre os 5min nominais — o texto continua
batendo com a realidade mesmo quando o teto encurtou o aviso.

Registrado como parâmetro de produto em **CLAUDE.md §5** (piso de 5min +
fórmula do teto), para o B4 não reinventar isso ao construir a UI do app
Motorista/Responsável.

6 testes novos travam a regressão: `test_pos_evento_helpers.py`
(`_eta_parada_anterior`, `_agendado_para_preparo` — piso normal, trecho curto
que força o teto, nunca no passado) e `test_projecao.py` (`etas_por_ordem`),
mais um teste de integração (`test_checkin_agenda_preparo_com_trecho_curto_nao_inverte_com_iminencia`,
Postgres real, trecho de 2,5min forçando o teto contra um trecho seguinte de
10min).

### `scripts/simular_viagem.py` — timeline legível para revisão manual

Roda uma viagem completa contra os dados do seed e imprime a timeline de
eventos + cada notificação que SERIA enviada (destinatário, instante,
conteúdo), inclusive canceladas — sem precisar de push real (`StubFCMSender`).
Cobre de propósito: uma casa pulada (mostra "nenhuma amostra de trajeto
gravada"), um `desfazer_checkin` dentro da janela (mostra o cancelamento do
`preparo` correspondente) e um trecho propositalmente curto (mostra o teto
da correção acima em ação). Roda tudo dentro de uma transação com `rollback`
no final — não deixa lixo na base de demo (confirmado: `viagens` do tenant
demo continua em 0 depois de rodar).

### Pendências / TODOs explícitos

- **Integração FCM real**: `FCMSender` é só interface + `StubFCMSender`.
  Trocar por uma implementação real é B5 (app Responsável) ou além.
- **Cadência de execução do agendador**: `scripts/processar_notificacoes.py`
  existe e é idempotente, mas rodar periodicamente (cron/Cloud Scheduler) é
  decisão de deploy, não foi configurado aqui.
- **Notificação ao gestor de aluno esquecido a bordo (§7.1, TODO do B2)**:
  ainda não implementada — o agendador do B3 dá a infraestrutura (`NotificacaoAgendada`
  poderia cobrir isso), mas não foi pedido explicitamente no escopo do B3 e
  não foi adicionado.
- **App Motorista/Responsável (B4/B5)**: nada implementado, conforme pedido
  — a projeção/cascata só existe no backend.

---

## Bloco B4 — App Motorista (Expo/Android) — **concluído (código); validação de banco e emulador PENDENTE**

### Duas lacunas bloqueantes encontradas antes de codar — resolvidas com o usuário

1. **O motorista não tinha como montar nenhuma tela.** `TripStudentOut` só
   trazia `aluno_id`/`parada_id` (UUIDs), e `/api/alunos`, `/api/rotas`,
   `/api/rotas/{id}/paradas` são `require_role("admin")` — sem exceção para
   `motorista`/`motorista_backup`. O diálogo do Cheguei (§6) exige nome do
   aluno e endereço.
2. **Reconciliação de relógio não existia** (lacuna registrada em
   `ARQUITETURA.md` §8, atribuída ao B4 desde o B3). `eventos_aluno.timestamp`
   era o relógio do servidor no momento do processamento HTTP, e alimentava
   direto `chegou_em`/`checkin_em` — um lote offline sincronizado de uma vez
   colapsaria os trajetos reais para perto de zero, corrompendo o EWMA do B3.

Decisões tomadas com o usuário (nenhum `require_role("admin")` existente foi
afrouxado — minimização de dados, LGPD):

1. `TripStudentOut` ganhou `aluno_nome`/`parada_endereco` (join direto, sem
   parser de logradouro/número — heurística erraria em endereços atípicos,
   e o diálogo do Cheguei é exatamente onde errar pesa mais). `ViagemOut`
   ganhou `rota_nome`/`rota_turno`/`rota_escola`/`total_alunos`. Nenhum dos
   dois expõe `dados_medicos` nem o cadastro inteiro do tenant.
2. Reconciliação: `ocorrido_em = device_timestamp + (agora_servidor −
   device_enviado_em)`, com clamp de offset em ±24h (estourou → cai pro
   relógio do servidor, `confiavel=False`, `leg_duration` não grava amostra
   a partir desse evento). A janela de 60s do desfazer-checkin mede **dois
   relógios de servidor** — nunca o aparelho — para não abrir undo infinito
   com relógio manipulado (ver achado extra abaixo).
3. Idempotência via `event_id`: gerado no aparelho no toque, reenviado sem
   trocar; reenvio nunca duplica evento nem devolve 409 espúrio.
4. Viagens `planejada` do dia nascem no `seed_demo.py` (não existe endpoint
   de criação de viagem pro motorista — isso é do Gestor, fora desta rodada).

### Achado durante a implementação — a janela do desfazer-checkin precisava de uma âncora nova

Medir a janela de 60s como "agora do servidor − `checkin_em`" não bastava:
`checkin_em` virou o instante **reconciliado** (`ocorrido_em`), que o
cliente influencia via `device_timestamp`/`device_enviado_em`. Um cliente
adversarial poderia declarar esses dois campos livremente e manter
`checkin_em` artificialmente "recente" pra sempre, driblando os 60s.
Corrigido com uma coluna nova, `trip_students.checkin_registrado_em`
(relógio do servidor no momento em que o Checkin foi recebido — nunca
reconciliado), e a janela agora compara **dois valores de servidor**: `agora
− checkin_registrado_em`. `checkin_em` continua alimentando o motor de
tempos normalmente.

### O que foi feito — Backend

- **Migration `0008_reconciliacao_temporal`**: `eventos_aluno.timestamp` →
  `ocorrido_em` (rename); colunas novas `registrado_em` (NOT NULL, backfill
  = `ocorrido_em`) e `event_id` (UUID único, backfill = `gen_random_uuid()`);
  `trip_students.checkin_registrado_em` (nullable, sem backfill — não há
  fonte de dado pra viagens já em andamento no momento da migração, então
  fica `NULL` e o `desfazer_checkin` trata isso como janela expirada,
  fail-safe). **Achado**: o backfill é um `UPDATE`, e o trigger de
  imutabilidade de `0004` bloqueia `UPDATE` mesmo pro owner — a migration
  desliga o trigger (`DROP TRIGGER`) antes do backfill e religa
  (`CREATE TRIGGER`, mesma definição) depois, dentro da mesma transação.
- **`app/services/reconciliacao.py`** (puro): `reconciliar()` — offset,
  clamp de ±24h, clamps de sanidade (nunca no futuro, nunca antes de
  `viagem.iniciada_em`), retorna `confiavel: bool`.
- **`app/services/trip_state_machine.py`**: todas as transições trocam
  `now=` por `ocorrido_em=`/`registrado_em=` (+ `event_id=` opcional,
  repassado ao `EventoAluno`). `registrar_checkin` grava
  `checkin_registrado_em`; `desfazer_checkin` mede a janela contra ele (não
  contra `checkin_em`) e trata `checkin_registrado_em is None` como janela
  expirada.
- **`app/services/pos_evento.py`**: `processar_cheguei` ganhou
  `registrar_amostra: bool = True` — quando a reconciliação não é confiável,
  a cascata de notificações roda normalmente, mas nenhuma amostra vai pro
  `leg_duration`.
- **`app/api/viagens.py`**: os 6 endpoints de evento passam a reconciliar
  antes de chamar `trip_state_machine`, checam `event_id` já processado
  antes de reprocessar (`_evento_ja_processado`), e capturam `IntegrityError`
  do índice único (`_registrar_evento`) para devolver o estado do vencedor
  em vez de 500 numa corrida. `ViagemOut`/`TripStudentOut` são montados via
  `_viagem_out`/`_trip_student_out` (join em lote, sem N+1).
- **`app/schemas/viagens.py`**: `EventoAlunoRequest` ganhou `event_id`
  (obrigatório) e `device_enviado_em`; `TripStudentOut`/`ViagemOut`
  enriquecidos (ver decisão 1).
- **`scripts/seed_demo.py`**: reestruturado para não abortar mais quando o
  tenant já existe — em vez disso garante (idempotente, chave
  `rota_id + data`) uma viagem `planejada` de **hoje** por rota, tanto no
  primeiro run quanto em runs seguintes em dias diferentes.
- **`scripts/simular_viagem.py`**: assinaturas atualizadas para
  `ocorrido_em=`/`registrado_em=`.

### O que foi feito — App Motorista (`mobile/`)

Expo SDK 54 (react 19.1.0, react-native 0.81.5 — upgrade a partir do SDK 51
original, feito ao testar em aparelho físico: o Expo Go instalado só aceita
o SDK exato com que foi publicado, então o projeto precisa acompanhar o que
está na Play Store, não o contrário; `npx expo install --fix` + `expo-doctor`
para alinhar todo o resto, `babel-preset-expo` precisou virar dependência
explícita — SDK 54 não traz mais transitivamente), TypeScript estrito,
Android only (`minSdkVersion 26` via `expo-build-properties`). Sem bottom
nav — stack única (Login → RotaDoDia → Viagem → FinalizarViagem);
Alunos/Frota/Perfil/Emergência/Broadcast do
protótipo antigo (`docs/prototipos/01-app-motorista.html`) são do plano
superado (CLAUDE.md §10/§11), fora do B4.

- **`shared/api/`**: `client.ts` (fetch + timeout 15s + `ApiError`/
  `NetworkError` tipados), `endpoints.ts`, `types.ts` (espelho manual dos
  schemas Pydantic — sem gerador de cliente nesta rodada).
- **`shared/auth/AuthContext.tsx`**: token em `expo-secure-store`. Resolução
  aprovada para "token expira (60min, sem refresh no backend) no meio de uma
  viagem offline": a fila já pausa sozinha em qualquer 401
  (`pausadoPorAuth`, sem descartar itens); o contexto só expõe
  `sessaoExpirada`, e o `RootNavigator` renderiza um prompt de reautenticação
  **por cima** da tela atual (não navega pra longe, não perde o estado da
  viagem). Depois do login, `retomarAposRelogin()` destrava a fila.
- **`shared/offline/queue.ts`**: fila persistente (`AsyncStorage`, um blob
  JSON), FIFO por `seq`, toda leitura-modificação-escrita serializada por
  encadeamento de promises (`serializado()`) — sem isso, dois toques rápidos
  perderiam um item. Cobre só os 6 eventos por aluno.
- **`shared/offline/sync.ts`**: drenagem estritamente sequencial (a máquina
  de estados do servidor valida ordem — §7.2, janela do undo). Tratamento
  por tipo de falha: 2xx remove + aplica o `TripStudentOut` do servidor
  sobre o estado local; 401 pausa tudo sem descartar; 4xx/409 remove +
  manda pra bandeja de conflitos (a tela ressincroniza via GET); rede/5xx
  **para a drenagem inteira** (não pula, não remove) e agenda nova tentativa
  com backoff exponencial (2s→60s). Gatilhos automáticos: reconexão
  (`NetInfo`), app voltando ao primeiro plano (`AppState`), e o backoff.
- **Decisão de escopo não pedida explicitamente, mas necessária**: iniciar
  viagem, finalizar viagem, reordenar e "estou atrasado" são **online-only**
  (chamada direta, erro claro + tentar de novo) — não entram na fila
  offline. São ações de fronteira (início/fim do turno, raras), o CLAUDE.md
  usa "van sem sinal" no contexto do fluxo contínuo de embarque, e finalizar
  em particular precisa da resposta do servidor pra varredura bloqueante
  fazer sentido. Documentado no topo de `queue.ts`.
- **`motorista/state/ViagemStore.tsx`**: estado otimista — aplica a
  transição local na hora do toque, enfileira, e substitui pelo
  `TripStudentOut` do servidor quando `sincronizado` chega. Em `conflito`,
  ressincroniza a tela inteira via GET (mais simples e mais seguro que
  tentar aplicar um patch depois de uma rejeição de domínio). §7.2 é checado
  no cliente antes de abrir o diálogo do Cheguei (guard de UX — a
  autoridade continua sendo o 409 do servidor).
- **UI (CLAUDE.md §6/§8)**: `Botao56`/`TOQUE_MIN=56` em toda ação;
  `EstadoBadge` sempre visível; **interpretação de "uma ação por linha"**
  (ambiguidade sinalizada antes de codar): o botão primário é único e muda
  com o estado (Cheguei→Checkin→Checkout), "Ausente" é uma affordance
  secundária deliberadamente menor, sem competir visualmente; `DialogoCheguei`
  é o único diálogo bloqueante (nome em destaque, endereço 13sp peso leve,
  Confirmar/Cancelar, nada mais); `BarraUndo` (30s na UI — a janela do
  servidor é 60s) cancela localmente se o Checkin ainda está na fila, ou
  enfileira `desfazer_checkin` de verdade se já foi enviado; reordenar via
  `ModoReordenar` + setas por linha, só alunos `aguardando`; `PillSync`
  mostra conectividade + pendentes sempre que há algo não sincronizado
  (requisito explícito do offline-first).
- **Telas**: `LoginScreen` (reaproveitada, modo `embutido`, no prompt de
  reautenticação), `RotaDoDiaScreen`, `ViagemScreen`, `FinalizarViagemScreen`
  (varredura bloqueante — botão travado com qualquer não-terminal ou item
  ainda na fila; cabeçalho de alerta duro se alguém está `a_bordo`).

### Testes

- **Backend, unitários (93 no total, sem banco)**: `test_reconciliacao.py`
  (11 casos — offset, clamp ±24h, sanidade), `test_trip_state_machine.py`
  (30 casos, +7 sobre o B2: `event_id` repassado, janela do desfazer-checkin
  medida contra `registrado_em` e não `checkin_em`, fail-safe sem
  `checkin_registrado_em`).
- **Backend, integração (27 no total, Postgres real via docker-compose —
  `pytest -m integration`, todos passando; ver "Validação contra Postgres
  real" abaixo)**:
  - `test_lote_offline.py` — **teste obrigatório pedido pelo usuário**: um
    lote de 6 eventos (3 pares Cheguei/Checkin) com deriva de relógio real
    (+3min) e sincronizado de uma vez, 45min depois, produz os MESMOS
    `leg_durations` (média e nº de amostras, bucket a bucket) que os mesmos
    6 eventos enviados ao vivo, relógio certo. + caso de offset além do
    clamp não gravando amostra.
  - `test_migration_0008_com_dados.py` — **obrigatório**: monta o grafo de
    suporte via ORM, faz `alembic downgrade` pra antes da 0008, insere um
    `EventoAluno` via SQL cru no formato pré-migration, `upgrade head` de
    novo, confere backfill (`ocorrido_em`/`registrado_em`/`event_id`) e que
    o trigger de imutabilidade continua bloqueando UPDATE/DELETE depois de
    ter sido religado pela própria migration.
  - `test_idempotencia_evento.py` — **obrigatório**: mesmo `event_id`
    enviado 2x grava um único `EventoAluno` e devolve 200 (não 409); dois
    `event_id` diferentes para a mesma ação continuam gerando 409 de
    verdade (idempotência não mascara erro de domínio); corrida simulada
    (dois INSERTs com o mesmo `event_id` chegando quase juntos) resolvida
    pelo índice único, sem 500.
  - Os testes de integração pré-existentes (`test_leg_duration_integracao.py`,
    `test_notificacoes_agendamento.py`, `test_rls_and_triggers.py`) tiveram
    as assinaturas atualizadas para `ocorrido_em=`/`registrado_em=`.
- **App Motorista (Jest + jest-expo, 19 casos, `npm test` dentro de
  `mobile/`)**: `queue.test.ts` (FIFO, persistência real via
  `@react-native-async-storage/async-storage/jest/async-storage-mock`,
  escritas concorrentes não se perdem, fila corrompida não trava),
  `sync.test.ts` (2xx/401/409/rede-5xx tratados como no CLAUDE.md, ordem
  estritamente sequencial, drenagem concorrente é no-op), `relogio.test.ts`.
  **`npx tsc --noEmit` limpo** (zero erros) — validado neste ambiente
  (`npm install` + testes + typecheck rodaram; emulador Android não estava
  disponível, ver "Pendências").

### Validação contra Postgres real — feita (docker-compose local)

Com o Docker subido pelo usuário: `alembic upgrade head` (como owner —
`vaivem_app`, do `.env`, não tem privilégio de DDL, igual ao B1) rodou limpo
sobre um banco com dados reais de sessões anteriores (98 tenants, 87
`eventos_aluno`), `scripts/seed_demo.py` reconheceu o tenant existente e
criou as 2 viagens do dia, e **os 27 testes de integração passam** (`pytest
-m integration`), incluindo os 3 obrigatórios. Dois bugs só apareceram
rodando de verdade — nenhum dos dois estava no código de produção, os dois
estavam nos testes novos:

1. **Deadlock do próprio teste da migration.** `test_migration_0008_com_dados.py`
   montava o grafo de suporte via ORM, comitava, e retornava `tenant.id`/
   `trip_student.id` **depois** do commit — acessar um atributo expirado
   (`expire_on_commit=True`, padrão do SQLAlchemy) dispara um refresh que
   abre uma nova transação. Essa transação ficava "idle in transaction"
   seguindo um lock em `trip_students` pelo resto do teste — e como o
   próximo passo era `alembic downgrade` (que precisa de lock exclusivo na
   MESMA tabela pra `ALTER TABLE ... DROP COLUMN`), o teste travava
   esperando a si mesmo. Confirmado ao vivo: `pg_stat_activity` mostrou a
   sessão do teste "idle in transaction" e o subprocesso do alembic "active"
   parado no `ALTER TABLE` havia 25 minutos. Corrigido capturando os ids
   ANTES do commit.
2. **Bug de RLS no teste de lote offline** (não no RLS em si — o RLS fez
   exatamente o que devia). `test_lote_offline.py` cria dois tenants (cenário
   "ao vivo" e cenário "lote") na mesma sessão; depois de trocar o tenant
   ativo pra ler os buckets do cenário "lote", a leitura dos buckets do
   cenário "ao vivo" (mesma sessão, sem trocar o tenant de volta) via RLS
   fail-closed e devolveu zero linhas — o filtro é pelo `tenant_id` da GUC
   da sessão, não pelo `rota_id` do `WHERE`. Corrigido chamando `set_tenant`
   de volta antes de cada leitura.

Nenhum dos dois bugs afeta o backend em produção — os dois eram só os testes
não replicando corretamente a disciplina de sessão que `app/api/deps.py::get_tenant_db`
já implementa em runtime (listener `after_begin`, ids capturados antes de
qualquer commit). Fica registrado porque é exatamente o tipo de coisa que só
aparece contra Postgres real — a mesma lição do portão B1→B2.

### Teste em aparelho físico via Expo Go — setup

Sessão separada, já com Docker/migrations/seed prontos. Passos que não
existem sozinhos no código (documentar para não repetir a investigação):

- **baseURL não pode ser `localhost`/`10.0.2.2` num aparelho físico** — isso
  resolveria para o próprio celular. `shared/api/client.ts` lê
  `EXPO_PUBLIC_API_BASE_URL` (`mobile/.env`, gitignored — `.env.example`
  documenta) como ponto único de configuração.
- **Cuidado com adaptadores virtuais ao pegar o IP da máquina**: em máquina
  com WSL2, `Get-NetIPAddress`/`ipconfig` lista o adaptador `vEthernet (WSL
  ...)` (ex.: `192.168.48.1`) junto com o adaptador físico real — só o
  físico (o que está na mesma rede do roteador/Wi-Fi do celular) funciona.
  Confirmar com `Get-NetAdapter` (Status `Up` + é o que tem IP da faixa do
  roteador).
- **Backend precisa de `--host 0.0.0.0`**: `uvicorn app.main:app --host
  0.0.0.0 --port 8000` — sem isso só aceita conexões da própria máquina.
- **Firewall do Windows**: se o perfil de rede do adaptador estiver como
  "Público" (`Get-NetConnectionProfile`), há bloqueio de entrada por padrão
  e pode existir regra explícita bloqueando Python nesse perfil
  (`Get-NetFirewallRule`). Liberar a porta é ação de sistema — não é
  automatizado, o comando (rodar como admin) é
  `New-NetFirewallRule -DisplayName "VaiVem API dev (8000)" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Any`.
- **Expo Go trava no SDK exato instalado** — desde que o modelo "multi-SDK"
  do Expo Go foi descontinuado, o cliente publicado na loja só abre projetos
  do MESMO SDK major com que foi compilado. O projeto tinha nascido no SDK
  51 (decisão original do B4); o Expo Go da loja estava no SDK 54 — upgrade
  necessário, não opcional. Fluxo que funcionou:
  `npm install expo@54.0.36` → `npx expo install --fix` (resolve o grosso:
  react 19.1.0, react-native 0.81.5, e as libs `expo-*`/RN community) →
  ajuste manual de dev deps que o `--fix` não cobre (`@types/react`
  `~19.1.10`, `jest-expo` `~54.0.0`) → `babel-preset-expo` precisou virar
  dependência EXPLÍCITA (`~54.0.12`) — no SDK 54 não vem mais transitivo via
  `expo`, e sem ele todo o Jest quebra com "Cannot find module
  'babel-preset-expo'". `npx expo-doctor` (18/18) e `npx tsc --noEmit`
  (limpo) validam o upgrade; os 19 testes Jest continuam passando sem
  alteração de código de app, só de dependências.
- Módulos nativos confirmados "Included in Expo Go" na doc oficial (sem
  precisar de development build): `@react-native-async-storage/async-storage`,
  `expo-secure-store`, `@react-native-community/netinfo`,
  `react-native-screens`, `react-native-safe-area-context`.
  `expo-build-properties` é plugin de config só — inerte sob Expo Go.

### Bugs achados testando em aparelho físico real — os 3 só apareceram aí

Nenhum reproduzia no bundling, no `tsc --noEmit` nem nos 19 testes Jest —
exatamente o tipo de coisa que só aparece com timing/hardware reais, mesma
categoria de lição do gate B1→B2 com Postgres.

1. **Loading infinito no 1º abrir do app.** `AuthContext` lia o token salvo
   do `SecureStore` sem `try/catch` — se essa leitura rejeitasse por
   qualquer motivo (comum em 1º launch), `carregando` nunca virava `false`
   e a tela de loading travava pra sempre, sem erro visível. Corrigido:
   falha na leitura vira "sem sessão salva" (fallback seguro), nunca trava.
2. **"E-mail ou senha inválidos" mesmo com o backend respondendo 200.** O
   `catch` de `LoginScreen`/`RootNavigator` era genérico demais — qualquer
   erro depois da autenticação (ex.: `SecureStore.setItemAsync` falhando ao
   salvar o token, que tem falhas de escrita esporádicas documentadas em
   alguns Android/Expo Go) virava a mesma mensagem de credencial errada.
   Corrigido em duas frentes: `login()` não deixa falha de persistência
   derrubar uma autenticação que já foi validada pelo servidor (`catch`
   próprio, log de aviso, segue); as telas só mostram "credenciais
   inválidas" quando o erro É de fato um 401 do endpoint de login
   (`mensagemErroLogin`, novo helper exportado de `LoginScreen.tsx`).
3. **"Sessão expirada" na cara logo após um login bem-sucedido — CRÍTICO,
   corrida de verdade, não intermitência de rede.** Ao logar, a tela
   autenticada (RotaDoDia) monta e busca dados reagindo à mudança do
   `token` do contexto. O React roda o efeito do FILHO recém-montado antes
   do efeito do ANCESTRAL (`AuthProvider`) na mesma leva de renderização —
   então a primeira requisição podia sair ANTES do efeito que atualizava o
   `getToken` do cliente HTTP rodar, sem `Authorization` nenhum, voltando
   401 na hora. Corrigido trocando a fonte de verdade: `configurarApi` é
   chamado UMA VEZ (não mais reativo a `token` via `useEffect`), e
   `getToken` lê de um `tokenRef` atualizado SINCRONAMENTE dentro de
   `definirToken` — antes de qualquer `setState`, então nunca existe uma
   janela em que o cliente HTTP tem uma versão desatualizada do token.
4. **(relacionado a #3, achado ao corrigir) Precisava recarregar manualmente
   depois de reautenticar pelo modal.** `useFocusEffect` só reage a eventos
   de NAVEGAÇÃO — o modal de reautenticação fica por cima da tela atual sem
   trocar de tela, então ele nunca retriggava a busca. `RotaDoDiaScreen` e
   `ViagemStore` (usado por `ViagemScreen`/`FinalizarViagemScreen`) ganharam
   um `useEffect` extra que refaz a busca sempre que `token` muda de
   verdade — cobre login inicial e qualquer reautenticação em campo.

Confirmado pelo usuário: login, navegação e fluxo funcionando corretamente
em aparelho Android físico via Expo Go depois dos 4 fixes acima.

### Pendências / TODOs explícitos

- **Teste manual em aparelho físico**: confirmado funcionando pelo usuário
  (login, navegação, Rota do dia) em Android físico via Expo Go, backend em
  `0.0.0.0:8000`, Metro em `exp://<IP-da-máquina>:8081`. O roteiro completo
  (viagem inteira, finalizar com aluno a bordo, modo avião com 6 eventos)
  ainda não foi confirmado ponta a ponta. Login
  `motorista.centro@demo.vaivem.com.br` / `demo12345` (seed cria a viagem de
  hoje automaticamente).
- **"Estou atrasado"**: endpoint já existe (B3) mas não ganhou botão na UI
  do B4 — não estava nas 4 telas pedidas explicitamente; fica como TODO.
- **App Responsável (B5)**: nada implementado, conforme pedido.
- Parser de logradouro/número de `Parada.endereco`: descartado de propósito
  (decisão do usuário) — vira colunas reais quando o cadastro do Gestor
  existir.

---

## Bloco B5 — App Responsável, push real, "Estou atrasado" — **concluído (código); validação de banco e emulador PENDENTE**

Último bloco desta rodada (backend + Motorista + Responsável).

### Estrutura apresentada e aprovada antes de codar

Mostrado ao usuário antes de qualquer linha de código: telas, endpoints
novos, e o desenho do registro de token FCM. Duas decisões vieram como
resposta a perguntas explícitas feitas antes de codar:

1. **Push: Expo Push Service, não FCM direto.** O app roda em Expo Go (SDK
   exato instalado, sem dev client — mesma restrição do B4). Token nativo de
   FCM não funciona dentro do Expo Go; FCM direto (HTTP v1 + service
   account) exigiria migrar pra um dev client custom (EAS build), fora do
   escopo deste bloco. `DeviceToken.provider` (`expo`/`fcm`) existe desde já
   no schema — trocar de provider no futuro é um novo `FCMSender`, não uma
   migration.
2. **Notificação persistente sem foreground service.** Confirmado ANTES de
   codar (pesquisa na doc oficial do `expo-notifications`) que
   `usesChronometer`/`showWhen`/`when` do `Notification.Builder` nativo NÃO
   são expostos pela API cross-platform da lib — exigiria native module
   próprio, a mesma parede que descartou FCM direto. Fallback adotado (já
   aprovado como obrigatório pelo usuário antes dessa descoberta):
   `sticky: true` (ongoing — nunca some sozinha, é o requisito essencial) +
   texto com o horário fixo da chegada, reescrito a cada ~45s enquanto o
   app está vivo (bônus sem custo de infra — mostra minutos decorridos por
   cima do horário fixo; não é um cronômetro nativo por segundo). A tela de
   acompanhamento mostra o cronômetro exato em tempo real via JS puro.

Outra decisão registrada no desenho aprovado, não uma pergunta explícita:
**um único projeto Expo** pras duas experiências (Motorista e Responsável),
ramificado por `role` (claim do JWT, decodificado só pra UI — nunca
autorização de verdade). CLAUDE.md fala em "três apps", mas o pedido
explícito deste bloco foi "reaproveite `mobile/src/shared` em vez de
duplicar", e não há tooling de monorepo no projeto que justificasse um
segundo projeto Expo. Registrado em ARQUITETURA.md.

### Ambiguidade resolvida durante a implementação (não levada de volta)

`FCMSender.enviar()` (protocolo do B3) não carregava `viagem_id`/
`trip_student_id`/`aluno_id` — só `destinatario_user_id`/`tipo`/`payload`.
Sem isso o app Responsável não tem como saber pra qual filho abrir a tela ao
tocar numa notificação. Resolvido enriquecendo o `payload` (já é
ESTRUTURADO, JSONB) em vez de mudar a assinatura do protocolo —
`pos_evento._payload_com_rota` garante que todo payload (imediato ou
agendado, inclusive reagendamentos de `preparo`) carrega os 3 ids por cima
do payload de domínio. `chegada` também ganhou `chegou_em` no payload — sem
isso o app precisaria de um round-trip extra só pra saber o horário da
notificação persistente.

### O que foi feito — Backend

- **Migration `0009_device_tokens`**: tabela `device_tokens` (`tenant_id`,
  `user_id`, `token` único global, `provider` enum, `ativo`,
  `desativado_em`) + RLS fail-closed já nascendo com o guard `NULLIF`
  (0006/0007) — não precisa de migration de correção depois.
- **`app/api/dispositivos.py`** (`POST`/`DELETE /api/dispositivos/token`,
  qualquer role autenticado): upsert por `token` (aparelho compartilhado
  trocando de usuário reatribui a mesma linha). Conflito com um `token` de
  OUTRO tenant (RLS o torna invisível pra esta sessão) vira 409 — nunca
  contorna o filtro de tenant pra "resolver" a escrita.
- **`app/services/expo_push.py`** (`ExpoPushSender`, novo `FCMSender` real):
  consulta `DeviceToken` ativos do destinatário, monta mensagem (título/
  corpo genéricos só pro fallback de bandeja do SO — o `data` estruturado
  continua sendo a fonte de verdade, o app re-hidrata o texto de verdade a
  partir dele), envia em lote pro Expo Push Service. `dismiss_chegada` é
  `data-only` de propósito (nunca aparece na bandeja). **Nunca lança**:
  falha de rede ao falar com o Expo não pode derrubar a transação do evento
  de domínio que a originou (roda ANTES do commit) — mesmo contrato de
  "nunca falha" que `StubFCMSender` já tinha. `DeviceNotRegistered` marca o
  token `ativo=false` (nunca DELETE — token morto acumulado sem essa
  marcação é a causa clássica de push que "some"); outros erros (rate
  limit etc.) não desativam nada. Substitui `StubFCMSender` nos dois pontos
  reais de envio: `api/viagens.py::_registrar_evento` (chegada/iminência
  imediatas + sinal de dismiss) e `scripts/processar_notificacoes.py`
  (preparo agendado).
- **`app/services/pos_evento.py`**:
  - `_payload_com_rota` + `_enviar_dismiss_chegada` (novos helpers).
  - `processar_checkin`/`processar_ausente` ganharam `sender` opcional e
    disparam `dismiss_chegada` — `processar_checkin` sempre (Checkin só
    acontece a partir de `chegou`, garantia da máquina de estados);
    `processar_ausente` só se `atual.chegou_em is not None` (veio de
    `chegou`, não de `aguardando` direto — `chegou_em` não é limpo pela
    transição de ausente, ver `trip_state_machine.py`).
  - **`calcular_progresso_aluno`** (novo, público): mapa VIRTUAL pro app
    Responsável — progresso por PARADA (nunca coordenada, CLAUDE.md §2/§10),
    reusando o mesmo motor de ETA do B3 (`_anchor_atual`/`etas_por_ordem`)
    sob demanda em vez de via push. `faixa_min_*` só é calculada com o aluno
    em `aguardando` — depois de `chegou` o dado relevante é `chegou_em`, e
    `a_bordo`/terminal não têm ETA de embarque que faça sentido mostrar.
- **`app/api/responsavel.py`** (`/api/responsavel`, role `responsavel`,
  escopado por `Responsavel.user_id == current_user.id` em TODO endpoint —
  nunca por `aluno_id` cru da URL): `GET /filhos`, `GET
  /filhos/{aluno_id}/status`, `GET /filhos/{aluno_id}/historico?data=`.
  Minimização de dados (mesma postura do B4): sem `dados_medicos`, sem
  coordenada, sem lista completa da rota — só a posição relativa do PRÓPRIO
  filho. Histórico filtra pra fora `desfazer_chegada`/`desfazer_checkin`
  (mesmo espírito do CLAUDE.md §4: correção interna, não fato relevante pro
  responsável).

### Testes — Backend

- **Unitários, sem banco (99 no total, +6 sobre o B4)**:
  `tests/test_progresso_aluno.py` — contagem de paradas concluídas/
  restantes, os 4 ramos que NÃO tocam banco (`chegou`/`entregue`/`ausente`/
  `aguardando` sem viagem iniciada), múltiplos alunos na mesma parada
  contam uma parada só.
- **Integração, Postgres real (`pytest -m integration`, escritos mas NÃO
  executados neste ambiente — sem Docker disponível, mesma situação do
  gate B1→B2; rodar antes de considerar o bloco fechado de verdade)**:
  - `tests/integration/test_payload_e_dismiss.py`: payload de
    chegada/iminência/preparo carrega os 3 ids de roteamento (na criação E
    no reagendamento por "estou atrasado" — regressão explícita pro bug de
    `_recalcular_e_reagendar` sobrescrever o payload sem eles); Checkin
    dispara `dismiss_chegada`; Ausente dispara só quando veio de `chegou`.
  - `tests/integration/test_expo_push.py`: sem token ativo não faz
    chamada HTTP; token ativo recebe mensagem com `data`+título fallback;
    token inativo não recebe nada; `dismiss_chegada` é silencioso (sem
    title/body); `DeviceNotRegistered` desativa o token, outro erro não;
    múltiplos tokens do mesmo usuário recebem todos. Cliente HTTP é um fake
    injetado (`ExpoPushSender(db, cliente=...)`) — nunca sai da rede em
    teste.
  - `tests/integration/test_responsavel_endpoints.py` — **o ponto crítico
    do bloco**: um responsável NUNCA enxerga o filho de outro, mesmo
    sabendo o `aluno_id` (IDOR), tanto em `status_filho` quanto em
    `historico_filho` (404, não 403 — mesmo padrão do motorista em
    `api/viagens.py`, não confirma existência pra quem pergunta);
    `listar_filhos` não vaza aluno alheio; histórico mostra os eventos
    reais mas não os de "desfazer".
  - `pytest` (99 passed) roda limpo neste ambiente; `pytest -m integration`
    fica pendente do próximo acesso a Postgres real (docker-compose).

### O que foi feito — App (`mobile/`)

Continua Expo SDK 54 (nenhuma mudança de SDK neste bloco). Dependências
novas (`npx expo install`, todas SDK 54-compatíveis, `expo-doctor` 18/18
depois): `expo-notifications` (~0.32.17), `expo-device` (~8.0.10),
`expo-constants` (~18.0.13).

- **Decisão estrutural**: um único app Expo, `RootNavigator` ramifica pela
  claim `role` do JWT (`shared/auth/jwt.ts::decodeJwtPayload` — decodificação
  própria, sem `atob`/`Buffer`, por cautela de runtime Hermes/Expo Go, mesmo
  espírito dos bugs achados em aparelho físico no B4). `LoginScreen`
  promovido de `motorista/screens/` pra `shared/screens/` (é genérico, sempre
  foi). `app.json` mantém nome/`package` "Motorista" — cosmético, TODO se um
  dia isso virar dois apps de verdade na Play Store.
- **`shared/notifications/`**: `canal.ts` (3 canais Android — `chegada`
  MAX, `iminencia` HIGH, `preparo` DEFAULT, importância proporcional à
  urgência real de cada tipo), `token.ts` (registro best-effort: sem
  `Device.isDevice`, sem permissão concedida, ou sem EAS `projectId`
  configurado — `eas init`, gratuito, mas é conta do usuário, não algo que
  desse pra automatizar aqui — o app segue funcionando normalmente, só sem
  push; a tela de acompanhamento continua atualizando por polling/pull),
  `persistente.ts` (a notificação sticky de chegada, ver decisão 2 acima),
  `index.ts` (handler de foreground, listeners de recebimento/toque,
  roteamento pro filho certo via `navigationRef` — necessário porque o
  toque pode acontecer com nenhuma tela montada ainda). `AuthContext`
  chama `registrarPushToken()` depois de login bem-sucedido e
  `removerPushTokenAtual()` (best-effort, nunca trava o logout) antes de
  limpar a sessão.
- **Telas do Responsável** (`responsavel/screens/`): `ListaFilhosScreen`
  (nome + badge de estado do dia por filho — reusa `EstadoBadge` do B4),
  `AcompanharFilhoScreen` (mapa virtual: `BarraProgresso` — bolinhas por
  parada, preenchidas = percorridas, marcada = a do próprio filho; banner
  de chegada com cronômetro client-side quando `chegou`; faixa de minutos
  quando `aguardando`; nunca minuto exato), `HistoricoFilhoScreen` (lista
  simples do dia). Onboarding sem nome (toque numa notificação): a tela
  resolve o nome sozinha via `listarFilhos()`.
- **"Estou atrasado"** (`motorista/screens/ViagemScreen.tsx`): link no
  cabeçalho abre um painel com 4 atalhos (+5/+10/+15/+20 min, 56dp cada —
  CLAUDE.md §8), online-only (mesmo padrão de reordenar/iniciar/finalizar),
  banner de confirmação depois do envio.

### Testes — App

- **Jest (24 no total, +5 sobre o B4)**:
  `shared/auth/__tests__/jwt.test.ts` — decodifica payload bem formado,
  preserva UTF-8 (acentos), `null` pra token malformado/vazio/payload não-JSON.
  `npx tsc --noEmit` limpo, `npx expo-doctor` 18/18.
- **Emulador/aparelho físico**: **não testado nesta rodada** (sem Docker
  pro backend neste ambiente, então sem servidor real pra apontar o app).
  Fica como TODO explícito — mesmo perfil de pendência que o B4 teve até a
  sessão de teste físico dedicada.

### Pendências / TODOs explícitos

- **Validar contra Postgres real**: `alembic upgrade head` (migration
  `0009`), `pytest -m integration` (payload/dismiss, expo_push,
  responsavel — os 3 arquivos novos), seed continua rodando limpo.
- **Testar em aparelho físico via Expo Go**: login como responsável (seed
  do B1 já cria responsáveis — `permissoes.receber_notificacoes` default
  permissivo), registro de push (precisa de `eas init` — projeto EAS
  gratuito, feito pelo usuário), notificação de chegada persistente e seu
  dismiss, toque roteando pra tela certa, "Estou atrasado" no Motorista.
- **`eas init`**: sem `projectId` configurado, `registrarPushToken()`
  desiste silenciosamente (best-effort, log de aviso) — precisa ser feito
  uma vez pelo usuário pra push funcionar de verdade, mesmo dentro do Expo
  Go.
- **Receipts do Expo Push Service**: `ExpoPushSender` lê só a resposta
  imediata do `send` (erros de validação síncronos, incluindo
  `DeviceNotRegistered` quando ele vem nessa resposta). Não implementa o
  passo 2 (consultar `/getReceipts` horas depois) — deixa passar alguns
  casos de token morto que só aparecem no receipt assíncrono. Aceito como
  simplificação: o impacto é o mesmo de um token nunca desativado (só
  continua tentando até night eventualmente vir um erro síncrono), não um
  bug de dado.
- **App do Gestor** e qualquer coisa de billing/painel web: fora de escopo,
  como sempre (CLAUDE.md §10).
- Retenção/expurgo LGPD (§7.5): continua atribuída ao B6, fora desta
  rodada — nenhum dado novo deste bloco (device_tokens, notificações)
  muda essa pendência.

---

## Revisão de segurança (pós-B5) — correções aplicadas

Revisão de segurança/correção dos blocos B1–B5 (foco: isolamento de dados,
regras invioláveis §7, motor de tempos, superfície de auth). Os achados foram
priorizados como A1–A7 + uma discrepância do §11; **todos foram corrigidos**
nesta rodada (decisões do usuário: A3 por soft-delete, §11 implementando a
reatribuição de fato).

### O que foi corrigido

- **A1 — segredo JWT com fallback default (ALTO).** `app/core/config.py` ganhou
  um `model_validator` que **bloqueia o boot** se `jwt_secret` for o placeholder
  ou tiver < 32 chars quando `env != development`. Todo o isolamento
  multi-tenant tem raiz na integridade do token (a claim vira `app.tenant_id`
  do RLS e o papel do RBAC) — um segredo forjável colapsava tudo. `.env.example`
  documenta o requisito. Testes: `tests/test_revisao_seguranca.py`.
- **A2 — varredura final/eventos sem trava (TOCTOU) (MÉDIO).**
  `app/api/viagens.py::_get_viagem_ou_404` ganhou `lock=True` (`SELECT ... FOR
  UPDATE` na viagem), aplicado em TODOS os endpoints mutantes (6 eventos +
  iniciar/finalizar/reordenar/estou-atrasado/reatribuir). Serializa operações
  concorrentes na mesma viagem — fecha o furo da §7.1 (finalizar enquanto um
  Checkin move alguém para `a_bordo`) e a corrida de dois eventos no mesmo
  trip_student. Endpoints de leitura seguem sem lock.
- **A3 — hard-delete contra §7.5 (MÉDIO) → soft-delete.** Migration `0010`
  adiciona `ativo` a `responsaveis`/`paradas` (`alunos.ativo`/`rotas.ativa` já
  existiam). `remover_aluno`/`remover_responsavel`/`remover_rota`/
  `remover_parada` passam a marcar `ativo=False` (cascata na aplicação:
  remover aluno desativa seus responsáveis; remover rota desativa suas
  paradas). Todas as leituras (admin CRUD, app Responsável, recipientes de
  push) filtram `ativo=True`, então um registro soft-deleted se comporta como
  apagado. `remover_token` (logout) também virou soft-delete (o `ExpoPushSender`
  já só olha tokens ativos).
- **A4 — EWMA envenenável (BAIXO).** `app/services/leg_duration.py` ganhou
  `LEG_MAX_SEGUNDOS` (2h) — teto ABSOLUTO por amostra, independente da média
  que deriva. O clamp relativo "> 3x" sozinho deixava amostras sucessivas
  empurrarem a média sem limite (ratchet); o teto fixo corta isso. Limitação
  residual documentada (sentido de baixa, perto de zero, ainda passa — menos
  nocivo). Testes: `tests/test_leg_duration.py`.
- **A5 — token de push sem prova de posse (BAIXO).** Mantido o comportamento de
  reatribuição (é o fluxo REQUERIDO de aparelho compartilhado — a posse do
  token opaco é a prova implícita), com o risco residual documentado em
  `app/api/dispositivos.py`: é griefing, não exfiltração (`user_id` sempre vira
  o do chamador). Sem atestação de dispositivo (fora do Expo Go) não há como
  fechar no servidor.
- **A6 — `minutos` de "Estou atrasado" sem teto (BAIXO).** `EstouAtrasadoRequest`
  ganhou `le=ESTOU_ATRASADO_MAX_MINUTOS` (12h) — evita o overflow do `int4` de
  `atraso_manual_segundos`. Testes: `tests/test_revisao_seguranca.py`.
- **A7 — `_validar_user` atravessava tenants (BAIXO).** `app/api/alunos.py`
  passa a checar `usuario.tenant_id == tenant_id` explicitamente (`users` não
  tem RLS de propósito), fechando o vínculo de responsável a `user_id` de
  outro operador.

### §11 — reatribuição de condutor (implementada)

Antes, `motorista_backup` não conseguia assumir a viagem de outro motorista
(sem endpoint de reatribuição) — o exato ponto único de falha que §3/§11 dizem
mitigar. Agora:

- **`POST /api/viagens/{id}/reatribuir`** (`ReatribuirViagemRequest`): `admin`
  realoca qualquer viagem do tenant para qualquer motorista do tenant;
  `motorista_backup` só ASSUME PARA SI, e só uma viagem `em_andamento` (o
  cenário do §11 — a própria reatribuição é o que passa a dar acesso, por isso
  não exige acesso prévio). Viagem travada (`lock=True`) durante a troca.
- **Auditoria** em `viagem_reatribuicoes` (migration `0010`): tabela
  append-only por trigger de banco (mesma filosofia de `eventos_aluno`, §7.4),
  RLS fail-closed com o guard `NULLIF`. Registra anterior/novo/quem/motivo.
- **Seed** (`seed_demo.py`): passa a criar um usuário `motorista_backup` +
  perfil `Motorista` por tenant (login `motorista.backup@demo.vaivem.com.br`),
  para o fluxo ser exercitável.

### O que foi confirmado correto (não mexido)

IDOR do `/api/responsavel` (escopo por `Responsavel.user_id`), escopo do
motorista (`_garantir_acesso_viagem`), nenhum acesso a tabela com `tenant_id`
fora de `get_tenant_db`, `set_config` com escopo de transação em todos os
pontos, append-only de `eventos_aluno`, janela de 60s do desfazer-checkin
(servidor-vs-servidor), RLS `NULLIF` em todas as tabelas, JWT com
`algorithms=[HS256]`.

### Testes

- **Unitários (sem banco), `pytest`**: `109 passed` (+10 sobre os 99 do B5) —
  `test_leg_duration.py` (teto absoluto A4) e `test_revisao_seguranca.py`
  (guarda do segredo A1, teto de minutos A6).
- **Integração (Postgres real), `pytest -m integration`**:
  `tests/integration/test_revisao_seguranca.py` — reatribuição (admin,
  backup-para-si, backup-para-terceiro=403, backup-em-planejada=403, auditoria
  append-only) e soft-delete de aluno. **Escritos, não executados neste
  ambiente** (sem Postgres — mesma situação das pendências do B5).
- **Offline**: `alembic upgrade head --sql` (base→head) gera limpo com a `0010`;
  `python -c "import app.main"` importa; `py_compile` limpo.

### Pendências desta rodada de revisão

- Rodar `pytest -m integration` contra Postgres real (docker-compose) — cobre
  A2/A3/§11, que dependem de banco.
- Retenção/expurgo LGPD (§7.5) segue no B6: o soft-delete conforma o "não
  hard-delete até o B6", mas a política de expurgo em si continua fora de
  escopo.
