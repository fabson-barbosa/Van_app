# BACKLOG-futuro.md

> **Não é requisito.** Nada aqui deve virar código sem uma decisão explícita de
> promover o item ao `CLAUDE.md`.
>
> Este arquivo substitui `docs/planejamento/arquitetura.md`. O conteúdo original
> descrevia um produto mais amplo; o que ainda vale foi promovido ao
> `ARQUITETURA.md`, e o que foi cortado está registrado abaixo com o motivo.
>
> Fonte de verdade para implementação: **`CLAUDE.md`**.

---

## Cortado da rodada atual

### GPS em tempo real
**Por quê saiu:** custo do Routes API, mais foreground service com notificação
persistente, mais Doze e os "otimizadores de bateria" de Xiaomi/Samsung/Motorola
matando o serviço — causa nº 1 de rastreamento fantasma. Some a isso o formulário
de declaração da Play Store para `ACCESS_BACKGROUND_LOCATION`, que exige vídeo
demonstrativo e costuma travar na revisão.

**O que o substitui hoje:** os eventos Cheguei/Checkin do motorista são o sensor
de progresso, e o mapa do Responsável é virtual (paradas, não coordenadas).

**Quando promover:** quando o motor de tempos já tiver histórico suficiente para
comparação, e houver receita que absorva o custo de API. O schema já reserva
PostGIS.

**Cuidado ao retomar:** validar em aparelho barato real, nunca em emulador.

### NFC
**Por quê saiu:** custo de tags por aluno, aluno esquece o cartão, e dependência
de hardware antes de haver cliente pagante.

**O que o substitui hoje:** confirmação manual pelo motorista, com diálogo de
confirmação nomeando o aluno, e a varredura final bloqueante como rede de
segurança.

**Quando promover:** só se a confirmação manual se mostrar insuficiente em campo.
A varredura final continua obrigatória mesmo com NFC.

### Módulo financeiro / billing
**Por quê saiu:** o gargalo do VaiVem é comercial — vender para pequenos
operadores de van — não técnico. Construir cobrança antes de ter cliente é
otimizar a etapa errada.

**Quando promover:** com os primeiros contratos assinados. Até lá, cobrança
manual resolve.

### App Gestor funcional
Permanece como mockup HTML. O operador de van pequeno é o próprio motorista na
maioria dos casos; o Gestor só ganha valor com frota de verdade.

### iOS
Parque de aparelhos dos motoristas é majoritariamente Android antigo. Reavaliar
quando houver demanda de responsáveis, não de motoristas.

---

## Ideias registradas, ainda não avaliadas

- **Confirmação de desembarque pelo responsável** — o pai confirma no app que
  recebeu a criança. Seria o segundo par de olhos que o NFC daria, e mais barato.
  Forte candidato ao próximo ciclo.
- **Tomada de posse por `motorista_backup`** — outro aparelho assume a viagem em
  andamento. O papel já existe no enum; falta o fluxo.
- **Diagnóstico de dwell** — o tempo de porta por casa já é coletado. Serve para
  o operador conversar com o responsável que atrasa a rota toda.
- **Painel web** — provavelmente antes do app Gestor, e mais barato.

---

## Aprendizados que não devem se perder

- **ETA sobre raio**: gatilho por tempo estimado, nunca por raio geográfico fixo.
- **Trajeto e dwell são grandezas separadas.** Misturá-las polui a média e foi o
  erro que o botão "Cheguei" corrigiu.
- **Figma MCP** se mostrou pouco confiável para prototipagem rápida (contextos de
  execução isolados, quota de escrita no plano Starter, `exportAsync` instável).
  HTML standalone rendeu mais.
- **Contraste puro cansa**: preto puro com amarelo puro causa fadiga visual.
  Fundos dessaturados, grafite quente e dourado aplicado com parcimônia.