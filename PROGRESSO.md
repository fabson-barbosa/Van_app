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
- `pytest` (73 passed) e `pytest -m integration` (20 passed) limpos. Seed
  roda idempotente sem quebrar com as colunas novas.

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
