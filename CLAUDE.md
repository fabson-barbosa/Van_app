# VaiVem — Especificação de Domínio e Contrato de Implementação

> Este documento é a fonte de verdade do domínio. Antes de qualquer alteração de
> comportamento, releia as seções "Máquina de estados" e "Regras invioláveis".
> Se uma tarefa exigir contrariar uma regra inviolável, pare e pergunte.

---

## 1. O que é

SaaS de gestão de transporte escolar para pequenos operadores de van no Brasil.
Três apps: **Motorista**, **Responsável**, **Gestor**.

Esta rodada implementa **backend + Motorista + Responsável (leitura)**.
Gestor permanece como mockup HTML — não implementar.

## 2. Decisões de arquitetura já tomadas (não reabrir)

| Decisão | Motivo |
|---|---|
| **Sem GPS em tempo real nesta versão** | Custo de Maps API, foreground service e Doze/OEM killers. Progresso da rota vem dos eventos do motorista. |
| **Sem NFC nesta versão** | Custo de tags, aluno esquece cartão. Confirmação é manual pelo motorista. |
| **Mapa "virtual"** | O Responsável vê progresso da rota por paradas, não posição geográfica. |
| **Multi-tenant com Row-Level Security no Postgres** | Isolamento por operador é requisito de LGPD, não pode depender da camada de aplicação. |
| **Android apenas**, mínimo API 26 (Android 8) | Parque de aparelhos antigos nas vans. |
| **Timestamps são o motor** | Toda estimativa de tempo é aritmética entre eventos. Sem geometria, sem rotas. |

## 3. Stack

- **Backend**: FastAPI, PostgreSQL (+PostGIS reservado para o futuro), Redis, Alembic
- **Mobile**: React Native / Expo, Android
- **Push**: FCM
- **Deploy**: Cloud Run
- **Auth**: JWT + RBAC. Enum de papéis já migrado e **canônico**:
  `admin` · `motorista` · `motorista_backup` · `responsavel`.
  Não renomear `admin` para `gestor`. `motorista_backup` é mantido de
  propósito: é a mitigação do celular do motorista como ponto único de falha
  (outro aparelho assume a viagem em andamento). Ver §11.

---

## 4. Máquina de estados do aluno na viagem

Estado por `trip_student` (aluno × viagem). Estados terminais: `entregue`, `ausente`.

```
                    [Cheguei]              [Checkin]                [Checkout]
      aguardando ──────────────> chegou ─────────────────> a_bordo ─────────────────> entregue
          │  ↑                     │  ↑                         │
          │  └──[Desfazer chegada]─┘  └────[Desfazer checkin]────┘
          │                         │
          └────────[Marcar ausente]─┴───────────────────────> ausente
```

- `aguardando` → `chegou`: motorista aperta **Cheguei** (exige confirmação, ver §6)
- `chegou` → `a_bordo`: **Checkin** (sem confirmação; undo de 30s)
- `chegou` → `ausente`: um toque, sem diálogo
- `aguardando` → `ausente`: um toque, sem diálogo. Cobre o caso do responsável avisar
  antecipadamente que o aluno não vai pegar a van. **Sem `chegou_em` não há dwell** —
  não gravar dwell nem como zero. O evento fica marcado como pulado (sem `Cheguei`
  antecedente), então o trajeto que atravessa esta parada não pode virar amostra de
  `leg_duration` (o consumo é do B3; a marcação de que foi pulado nasce aqui, no B2).
- `a_bordo` → `entregue`: **Checkout** no destino
- Desfazer chegada (`chegou` → `aguardando`) é permitido enquanto não houver Checkin.
  **Não dispara notificação de correção** — só corrige estado interno e cronômetro.
- Desfazer checkin (`a_bordo` → `chegou`): janela de **30s na UI**, **60s aceitos no
  servidor** (latência + fila offline). Fora da janela, o servidor rejeita a
  transição. Reabre o dwell e cancela o cronômetro do trajeto em andamento; cancela
  também o aviso agendado para N+2 se ainda não tiver sido enviado (o agendamento em
  si é do B3 — aqui só o estado é revertido).

Todo evento grava `timestamp` (servidor) e `device_timestamp` (cliente), para
reconciliar viagens registradas offline.

## 5. Motor de tempos

Duas grandezas **separadas** — essa separação é o coração do sistema:

```
trajeto(N → N+1) = Cheguei(N+1) − Checkin(N)
dwell(N)         = Checkin(N)   − Cheguei(N)
```

- `leg_duration(rota_id, ordem, faixa_horaria, dia_semana, segundos, amostras)`
  — média móvel alimentada pelos trajetos reais. Semente: estimativa do motorista.
  Convenção: `dia_semana` = `date.weekday()` (0=segunda); `faixa_horaria` = hora
  cheia 0–23.
- **Agregação progressiva (obrigatório).** A chave completa cria 7×24 baldes por
  trecho, e uma rota matinal gera **uma amostra por balde por semana** — a média
  levaria meses para convergir. A leitura deve subir de granularidade conforme a
  amostragem permite:
  1. `(rota_id, ordem)` — sempre disponível, é o fallback
  2. `(rota_id, ordem, dia_semana)` — só quando o balde tiver ≥ 5 amostras
  3. `(rota_id, ordem, dia_semana, faixa_horaria)` — só quando ≥ 5 amostras
  Escreva sempre na chave completa; a escolha acontece na **leitura**. Isso é
  decisão de query, não de schema — não gerar migration para isso.
- `dwell` é estatística separada, usada para diagnóstico (quais casas atrasam a rota).
  **Dwell de aluno ausente não entra na média.** Mas o trajeto seguinte parte
  do instante em que ele foi marcado ausente.
- `atraso_acumulado` na viagem: diferença entre o previsto e o real até a parada
  atual. Todos os avisos seguintes já nascem corrigidos por ele.
- Botão **"Estou atrasado"** no app do motorista: empurra manualmente a cauda da
  rota e notifica os responsáveis pendentes.

### Cascata de notificações

| Evento | Dispara |
|---|---|
| `Cheguei(N)` | Responsável N: "Chegamos, estamos esperando" (notificação **persistente** com tempo de espera correndo). Responsável N+1: "É a próxima!". Recalcula ETA da cauda. |
| `Checkin(N)` | Fecha dwell, inicia cronômetro do trajeto, agenda aviso de preparação para N+2 ("faltam ~X min"). |

Avisos usam **faixa** de minutos, nunca minuto exato. Sem GPS, precisão falsa
destrói a confiança do responsável.

## 6. Diálogo de confirmação do "Cheguei"

Único diálogo bloqueante do app. Conteúdo:

- **Nome do aluno em destaque** (o erro que importa é Cheguei na parada errada,
  não o toque acidental — um "Confirmar?" genérico vira reflexo em três dias)
- Rua e número abaixo, peso leve, cor secundária, ~13sp
- Dois botões: Confirmar / Cancelar. Nada mais no diálogo.
- Push sai **imediatamente** após confirmar (sem delay cancelável)

## 7. Regras invioláveis

1. **Varredura final bloqueante.** A viagem não pode ser finalizada enquanto
   houver aluno em estado não terminal. Sem NFC, esta é a única rede de segurança.
   Se algum aluno estiver `a_bordo` ao fim, alerta duro + notificação ao gestor.
2. **Cheguei sem Checkin anterior pendente**: se o motorista aperta Cheguei na
   parada N+1 com a parada N ainda em `chegou`, forçar resolução na tela
   imediatamente. Não deixar acumular até o fim da rota.
3. **RLS ativa em toda tabela com `tenant_id`.** Nenhuma query da aplicação pode
   depender de filtro manual por tenant.
4. **Trilha de auditoria imutável** para todo evento de aluno (append-only).
5. **Retenção LGPD**: dados de viagem expiram conforme política configurável por
   tenant. Separação de papéis controlador (operador) / operador (VaiVem).
   Implementação atribuída ao **B6**, fora desta rodada. Até lá, nenhum dado
   pode ser hard-deleted — a política ainda não existe para autorizar o expurgo.

## 8. UI do Motorista — restrições

Ele está dirigindo. A interface é dimensionada para pressa, não para conforto.

- Alvo de toque mínimo **56dp**
- Uma ação por linha de aluno
- Estado visível sem abrir nada: aguardando / chegou / a bordo / entregue / ausente
- "Ausente" em um toque
- Undo de 30s no Checkin
- Reordenar paradas permitido **antes** do Cheguei (senão o trajeto é atribuído
  ao par errado)
- Fila offline: eventos persistem localmente e reenviam ao recuperar sinal

## 9. Ordem de implementação

| Bloco | Escopo | Modelo sugerido |
|---|---|---|
| **B1** | Modelos, Alembic, RLS por tenant, JWT/RBAC, seed | ✅ concluído |
| **B2** | Máquina de estados, Cheguei/Checkin/Checkout, varredura final, auditoria | Opus |
| **B3** | `leg_duration`, média móvel, atraso acumulado, agendador FCM | Sonnet |
| **B4** | App Motorista | Sonnet |
| **B5** | App Responsável (push + mapa virtual) | Sonnet |
| **B6** | Hardening LGPD: retenção, expurgo, exportação de dados | fora desta rodada |

### Portão de validação antes do B2

O B1 foi validado apenas com `alembic upgrade head --sql` (offline). Isso **não**
exercita policy de RLS nem trigger — exatamente as duas coisas que todo evento do
B2 vai atravessar. Antes de escrever qualquer linha do B2, rodar contra um
Postgres+PostGIS real e confirmar:

1. RLS é **fail-closed**: consulta sem tenant setado na sessão retorna zero
   linhas, não todas.
2. O trigger de `eventos_aluno` rejeita `UPDATE` e `DELETE`.
3. O seed roda limpo: 2 rotas, 12 alunos.

Regras de trabalho:
- Um bloco por sessão. `/clear` entre blocos.
- Ao concluir um bloco, atualizar `PROGRESSO.md` com o que foi feito e o que ficou
  pendente, antes do `/clear`.
- Testes: cobrir a máquina de estados e a aritmética de tempos. O resto é opcional
  nesta rodada.
- Não gerar código para Gestor, billing ou painel web.

## 10. Fora de escopo (registrar como TODO, não implementar)

GPS em tempo real · NFC · confirmação de desembarque pelo responsável ·
Gestor funcional · billing/assinaturas · painel web · iOS

## 11. Documentos anteriores (não seguir)

`docs/planejamento/arquitetura.md` é um plano **anterior e mais amplo**, que
inclui GPS em tempo real, NFC e módulo financeiro. Está **superado** por este
documento. Serve como referência histórica e como backlog do que virá depois —
nunca como fonte de requisito para implementação.

Em caso de conflito entre os dois, **CLAUDE.md vence**, sempre.

Exceção deliberada: `motorista_backup` no enum de papéis vem daquele plano e é
mantido de propósito (§3).
