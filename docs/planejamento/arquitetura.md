# Plano Arquitetural — Plataforma de Gestão de Transporte Escolar

**Versão:** 1.0
**Modelo de negócio:** SaaS multi-tenant B2B2C (vende para transportadores/empresas, que atendem responsáveis)

---

## 1. Decisões Fundamentais (definir antes de qualquer código)

### 1.1 Multi-tenancy

A plataforma é **SaaS multi-tenant**. Cada transportador (de van autônoma MEI a empresa com frota) é um *tenant* isolado.

- **Isolamento de dados:** estratégia *shared database, separate schema* por tenant, ou *row-level security* com `tenant_id` em toda tabela. Recomendado iniciar com `tenant_id` + RLS no PostgreSQL (mais simples de operar, escala bem até centenas de tenants).
- **Billing da plataforma:** assinatura do transportador para usar o SaaS (por veículo ativo ou por aluno ativo), separada da cobrança que o transportador faz aos pais.
- **Hierarquia:** `Tenant → Veículos → Rotas → Paradas → Alunos → Responsáveis`.

### 1.2 LGPD — Papéis definidos

- **Controlador:** o transportador (decide finalidade do tratamento dos dados dos alunos).
- **Operador:** a plataforma SaaS (trata dados sob instrução do controlador).
- Contrato de operador (DPA) obrigatório no onboarding de cada tenant.
- Base legal para localização de menor: **execução de contrato** + **consentimento do responsável** para dados sensíveis (saúde/alergias).

### 1.3 O cérebro do sistema é o ETA, não o raio geográfico

Toda lógica de notificação de aproximação usa **tempo estimado de chegada (ETA)** calculado pela API de rotas, não distância fixa. Isso resolve o problema de "500m em congestionamento ≠ 500m em via livre".

---

## 2. Arquitetura Técnica

### 2.1 Stack sugerido

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Backend API | FastAPI (Python) ou NestJS | Tipagem forte, async nativo p/ I/O de localização |
| Banco principal | PostgreSQL + PostGIS | RLS multi-tenant + funções geoespaciais |
| Cache / Fila de eventos | Redis (Upstash) | ETA cache, rate-limit, fila de notificações |
| Tempo real | WebSocket (sob demanda) + push | Evitar streaming contínuo (custo/bateria) |
| Mapas / Rotas | Google Maps Directions/Matrix ou Mapbox | ETA dinâmico, recálculo |
| Push | Firebase Cloud Messaging (FCM) | Canal primário, gratuito |
| WhatsApp | API oficial (Meta) — secundário | Fallback; custo por template |
| Pagamentos | Asaas ou Mercado Pago | PIX + cartão recorrente + NF/MEI |
| App mobile | React Native (Expo) | Código único iOS/Android |
| Infra | Cloud Run / containers | Escala automática |

### 2.2 Princípio de tracking (corrige custo + bateria)

```
Motorista (app) ──push de posição (ex: a cada 10-15s)──> Backend
                                                            │
                                            calcula ETA por parada (cache Redis)
                                                            │
                        ┌───────────────────────────────────┤
                        │                                   │
              Dispara EVENTOS (gatilhos)          Mapa sob demanda (WebSocket
              via push aos responsáveis           só quando o pai ABRE o mapa)
```

- Pais recebem **eventos + ETA**, não o pin em movimento contínuo por padrão.
- Streaming ao vivo só quando o responsável abre a tela de mapa (conexão efêmera).
- App do motorista ajusta frequência de GPS por velocidade/proximidade de parada (economia de bateria).

### 2.3 Modo Offline (corrige single point of failure)

O celular do motorista é o ponto mais crítico. Mitigações:

- **Fila local de eventos** (embarques, check-ins, alertas) persistida no device.
- Sincronização automática ao recuperar sinal; eventos carregam timestamp de origem.
- **Heartbeat:** backend detecta ausência de sinal por X minutos → alerta passivo à escola/admin ("rota sem sinal").
- Navegação GPS funciona offline (mapas em cache da rota do dia).

---

## 3. Módulos

### 3.1 Roteirização e Notificação por ETA

- **Recálculo dinâmico:** a cada atualização de posição, recalcula ETA de todas as paradas pendentes via Matrix API (com cache para não estourar custo).
- **Gatilho de notificação:** dispara quando `ETA(parada) <= limiar` (ex: 3 min configurável por tenant).
- **Fila de avisos coerente:** como skipping e reordenação alteram a sequência, a fila de notificações é **derivada do ETA recalculado**, nunca de ordem fixa. Skipping e cadeia de avisos compartilham a mesma fonte de verdade (o motor de ETA).
- **Anti-duplicação:** cada par (parada, responsável) recebe no máximo 1 push de aproximação por turno.

### 3.2 Broadcast de Comunicação

- Painel de 1 clique com templates: atraso da escola, trânsito na via, falha mecânica + veículo de apoio.
- **Push é o canal primário.** WhatsApp é secundário (custo por template + regras anti-spam da Meta podem bloquear envio em massa).
- Broadcast atinge apenas responsáveis **pendentes** na rota (não quem já embarcou/desembarcou).
- Toda mensagem registrada (auditoria/LGPD).

### 3.3 Segurança da Criança (módulo crítico — risco de vida)

- **Check-in/out NFC ou QR** na tag da mochila/crachá da criança.
- **Varredura obrigatória de fim de rota:** o app **bloqueia a finalização** do turno até o motorista confirmar "veículo vazio" (varredura física dos bancos). Timer ativo.
- Se a confirmação não ocorrer em X minutos após a última parada → **alerta automático** à escola e aos responsáveis ("verificação de veículo pendente").
- **Botão de pânico/emergência:** aciona contatos de emergência + escola + admin com localização atual em caso de acidente.

### 3.4 Financeiro (B2C — transportador cobra os pais)

- Mensalidade recorrente (cartão) + PIX automatizado via gateway.
- Dashboard de inadimplência e conciliação.
- **Gestão de contratos:** valor por aluno, reajuste anual, data de vencimento.
- **Emissão de recibo/NF** compatível com MEI.
- **Split payment** caso a plataforma opere como marketplace (repasse ao transportador menos a taxa SaaS).
- Comprovante automático ao responsável a cada pagamento.

### 3.5 Perfis, Acessos e Compliance LGPD

- **Minimização:** Nome, endereço, contato de emergência, alergias/condições médicas críticas.
- **RBAC (papéis):** Admin do tenant, Motorista, Motorista Backup, Responsável.
- **Motorista Backup:** acesso temporário de 24h só à rota + navegação; sem financeiro, sem histórico de conversas.
- **Consentimento:** termo in-app renovável anualmente, versionado.
- **Retenção e expurgo:** rotina de exclusão dos dados do menor após saída da rota (prazo definido em contrato). Pseudonimização de logs antigos.
- **Criptografia:** dados sensíveis de menores em armazenamento isolado, criptografia *at rest* e *in transit*. Localização tratada como dado sensível.
- **Registro de operações de tratamento** (log de quem acessou o quê).

### 3.6 Gestão de Responsáveis

- **Múltiplos responsáveis por aluno** (mãe, pai, avó), cada um com seu device e push.
- Permissões por responsável (quem pode notificar ausência, quem recebe quais alertas).

### 3.7 Diário de Frota (Manutenção Preventiva)

- Alertas por quilometragem: óleo, pneus, vistoria Detran/prefeitura.
- Documentos do veículo com data de vencimento.

### 3.8 Auditoria e Comunicação Registrada

- **Histórico/replay de rota:** trajeto gravado para auditoria e disputas ("a van não passou aqui").
- **Chat responsável ↔ motorista** com registro persistente (prova + LGPD).

---

## 4. Fluxo Lógico de Rota (revisado)

```
[INÍCIO DO TURNO]
   │
   ├──> Motorista seleciona Rota ("Manhã - Escola X")
   ├──> Sistema carrega alunos ativos
   │      └──> Aplica SKIPPING: remove paradas com ausência notificada (>1h antes)
   ├──> Motor de ETA calcula sequência otimizada + ETAs iniciais
   │
[EXECUÇÃO — loop por atualização de posição]
   │
   ├──> Backend recebe posição → recalcula ETA de paradas pendentes
   │
   ├──> ETA(Parada N) <= limiar (ex: 3 min)?
   │      └──> SIM (1x): push "Chegando" aos responsáveis da Parada N
   │
   ├──> Chegada Parada N
   │      ├──> Motorista: check-in NFC/QR de cada criança → "Embarcado"
   │      └──> Recalcula fila → avisa próxima parada por ETA (não por ordem fixa)
   │
   ├──> [Exceção] Trânsito / falha
   │      └──> Botão de broadcast → só responsáveis pendentes
   │
   ├──> [Emergência] Botão pânico → escola + emergência + localização
   │
[FINALIZAÇÃO]
   │
   ├──> Chegada na Escola → check-out NFC/QR de cada criança
   ├──> ⚠ VARREDURA OBRIGATÓRIA: app BLOQUEIA finalização até
   │      "veículo vazio" confirmado (anti-esquecimento)
   │      └──> Sem confirmação em X min → alerta auto p/ escola + responsáveis
   └──> Confirmado → push "Chegada segura" a todos da rota
          └──> Replay da rota arquivado para auditoria
```

---

## 5. Modelo de Dados (núcleo)

```
tenants          (id, plano, status_billing)
users            (id, tenant_id, role, ...)        -- RBAC
veiculos         (id, tenant_id, placa, km_atual)
manutencoes      (id, veiculo_id, tipo, km_alvo, vencimento)
rotas            (id, tenant_id, turno, escola)
paradas          (id, rota_id, ordem_base, geo POINT)  -- PostGIS
alunos           (id, tenant_id, nome, parada_id, dados_medicos[cifrado])
responsaveis     (id, aluno_id, user_id, permissoes)   -- N:1 com aluno
viagens          (id, rota_id, veiculo_id, motorista_id, data, status)
eventos          (id, viagem_id, tipo, aluno_id?, timestamp, payload)  -- fila/auditoria
checkins         (id, viagem_id, aluno_id, tipo[in/out], metodo[nfc/qr], ts)
notificacoes     (id, viagem_id, responsavel_id, tipo, canal, ts)
pagamentos       (id, tenant_id, aluno_id, valor, status, gateway_ref)
consentimentos   (id, responsavel_id, versao, data, escopo)
```

Toda tabela com dado de tenant carrega `tenant_id` + política RLS.

---

## 6. Roadmap de Desenvolvimento (fases)

**Fase 1 — MVP (segurança + core)**
Multi-tenancy + RBAC, cadastro de rota/aluno/responsável, tracking por evento, motor de ETA, push de aproximação, check-in/out, varredura obrigatória de fim de rota, modo offline básico.

**Fase 2 — Comunicação e financeiro**
Broadcast com templates, chat registrado, mensalidade recorrente + PIX + NF/MEI, dashboard de inadimplência.

**Fase 3 — Diferenciação**
Skipping dinâmico, replay de rota, diário de frota, motorista backup temporário, botão de pânico, múltiplos responsáveis, WhatsApp como canal secundário.

**Fase 4 — Escala**
Split payment/marketplace, otimização de custo de API (cache agressivo de ETA), analytics por tenant.

---

## 7. Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| Criança esquecida no veículo | Varredura obrigatória + alerta automático (Fase 1, não negociável) |
| Celular do motorista falha | Fila offline + heartbeat + alerta de "sem sinal" |
| Custo de API de mapas explode | ETA por cache, recálculo só de paradas pendentes |
| WhatsApp bloqueado por spam | Push como primário, WhatsApp secundário |
| Vazamento de dados de menor | Isolamento + criptografia + RLS + expurgo |
| Notificações inconsistentes c/ skipping | Fila derivada do motor de ETA (fonte única) |
