# Análise UI/UX — App do Motorista

> Análise do código em `mobile/src/motorista/` + `mobile/src/shared/` contra as
> restrições do CLAUDE.md §6 e §8. Foco: **conforto do motorista durante a rota**
> — dirigindo, encostando em fila dupla, sol na tela, aparelho antigo.
>
> Documento de análise. Nenhuma alteração de comportamento foi feita.

## Critério usado

O §8 do CLAUDE.md define a régua: *"Ele está dirigindo. A interface é dimensionada
para pressa, não para conforto."* Traduzi isso em quatro perguntas aplicadas a cada
tela:

1. O motorista consegue executar a ação certa **sem ler a tela inteira**?
2. Se ele errar, **existe saída**?
3. Ele sabe que o toque **pegou**, sem olhar?
4. A tela funciona **sem sinal, no sol, com uma mão**?

## O que já está correto (não mexer)

- `Botao56` garante `minHeight: 56` em todo botão primário, e o botão de ação de
  cada linha usa `flex: 1` — ocupa a largura toda menos "Ausente". Alvo generoso.
- Estado sempre visível via `EstadoBadge`, sem abrir nada (§8).
- `DialogoCheguei` é fiel ao §6: nome em 22sp, endereço 13sp secundário, dois
  botões, nada mais. É o único modal bloqueante.
- Fila offline com estado otimista + `PillSync` — o motorista nunca fica travado
  esperando rede para registrar um evento.
- `FinalizarViagemScreen` implementa a varredura bloqueante (§7.1) com o rótulo do
  botão contando o que falta. Boa aplicação de "o botão explica por que está
  desabilitado".
- Reordenar só libera alunos em `aguardando` (§8), com aviso explícito nos demais.

---

## Severidade 1 — Erro sem saída

### 1.1 "Desfazer chegada" existe no código e **não tem UI**

`ViagemStore.desfazerChegada` (`state/ViagemStore.tsx:201`) e
`endpoints.desfazerChegada` (`shared/api/endpoints.ts:38`) estão implementados,
a ação está na fila offline (`queue.ts`, `AcaoEvento`), o backend aceita — e
**nenhuma tela chama**. O `AlunoRow` não expõe nada em estado `chegou` além de
"Checkin" e "Ausente".

Por que isso é o item mais grave: o §6 diz que *"o erro que importa é Cheguei na
parada errada"*. É justamente esse erro que não tem correção. E o efeito é
composto:

- `Cheguei` dispara push **imediato** ao responsável errado (§6).
- §7.2 bloqueia o próximo `Cheguei` enquanto a parada anterior estiver em `chegou`
  — e o guard já está implementado em `paradasAnterioresPendentes`.

Ou seja, o motorista que errou fica **preso na tela** com duas saídas, ambas ruins:
fazer Checkin (registra um embarque que não houve, contamina `dwell` e vira amostra
de `leg_duration`) ou marcar Ausente (marca o aluno errado como ausente, e o evento
é append-only — não some nunca).

**Correção:** expor "Desfazer chegada" no `AlunoRow` quando `estado === "chegou"`.
O §4 é explícito que a transição é permitida enquanto não houver Checkin, e que ela
*não dispara notificação de correção*. Só falta o botão.

### 1.2 `Ausente` e `Checkout` são irreversíveis e ficam a 12dp do botão primário

`ausente` e `entregue` são estados terminais — a máquina de estados (§4) não tem
`desfazer_ausente` nem `desfazer_checkout`. Ao mesmo tempo:

- "Ausente" é um toque sem diálogo (§8, correto — não proponho mudar isso).
- Ele fica no mesmo `flexDirection: "row"` do botão primário, separado por
  `gap: espacamento.md` = **12dp** (`AlunoRow.tsx:157`).

Dedo grande, van tremendo, 12dp entre "Checkin" e uma ação permanente.

**Correção de baixo risco, sem tocar no domínio:** reaproveitar o mecanismo que
`desfazerCheckin` já usa — quando o evento ainda está na fila, ele é cancelado
localmente via `cancelarPendente()` (`ViagemStore.tsx:215`), sem nunca chegar ao
servidor. Dá para segurar `ausente`/`checkout` na fila por ~5s com uma `BarraUndo`
e cancelar localmente. Não cria transição nova, não muda o backend, não viola §4.

> **Ponto a validar com o domínio antes de implementar:** o §6 diz que o push do
> Cheguei sai *"imediatamente após confirmar (sem delay cancelável)"*. Isso é
> declarado sobre o Cheguei; segurar Ausente/Checkout por 5s é um caso diferente,
> mas está perto o bastante do espírito da regra para merecer uma decisão explícita.

### 1.3 O undo do Checkin é frágil demais para a janela que promete

`undo` é `useState` local da `ViagemScreen` (`ViagemScreen.tsx:34`). Três falhas:

- **Some ao navegar.** Ir até "Finalizar viagem" e voltar destrói o estado antes
  dos 30s. O `BarraUndo` promete um contador que a tela não sustenta.
- **Só cabe um.** `setUndo` sobrescreve. Dois checkins seguidos (irmãos na mesma
  parada — o modelo permite, o `PROGRESSO.md` até cita "múltiplos alunos na mesma
  parada") e o undo do primeiro desaparece sem aviso, ainda dentro dos 30s.
- **Não é ancorado.** Aparece no topo, empurrando a lista para baixo — a linha que
  o motorista estava olhando se move sozinha.

**Correção:** mover o undo pendente para o `ViagemStore` (sobrevive à navegação),
permitir fila de undos, e ancorar a barra no rodapé com `position: absolute` em vez
de deslocar o conteúdo.

---

## Severidade 2 — Custo de atenção durante a rota

### 2.1 Não existe "parada atual"

A `ViagemScreen` é uma `FlatList` uniforme: todos os alunos com o mesmo peso
visual, a mesma altura, o mesmo card. Não há destaque para o próximo.

O motorista precisa **ler e procurar** qual linha é a dele. Com a van parada em
fila dupla, esse é o pior custo da tela inteira. E piora com o tempo: a lista não
rola sozinha (sem `scrollToIndex`), então depois de oito alunos entregues o alvo
está fora da tela e ele rola para achar.

**Correção — a de maior impacto do documento:** um card fixo de **parada atual** no
rodapé (zona do polegar), com nome grande, endereço e o botão primário do estado
atual. A lista abaixo vira consulta, não operação. Alternativa mais barata:
`scrollToIndex` automático para a primeira linha não-terminal a cada mudança de
estado.

### 2.2 Alunos já resolvidos consomem a tela toda

`AlunoRow` renderiza um `<View style={estilos.botaoPrimario} />` **vazio** para
estados terminais (`AlunoRow.tsx:95`) só para preservar o layout. Cada aluno já
entregue continua gastando ~110dp de altura útil.

**Correção:** colapsar terminais numa linha compacta (nome + badge, ~44dp) ou
agrupá-los num bloco recolhido "N concluídos".

### 2.3 O contador do cabeçalho está errado e desanima no fim do turno

```
embarcados = tripStudents.filter(a_bordo || entregue).length   // ViagemScreen.tsx:49
<Text>{embarcados} / {total} concluídos</Text>                 // ViagemScreen.tsx:175
```

Dois problemas:

- **`a_bordo` conta como "concluído"** — mas a `FinalizarViagemScreen` trata
  `a_bordo` como pendente e dispara *alerta duro* (§7.1). A mesma viagem diz
  "concluído" numa tela e "Aluno a bordo!" na outra.
- **`ausente` não conta em lugar nenhum.** Numa rota com 2 ausentes o contador
  nunca passa de 10/12. O motorista termina o turno com a tela dizendo que
  faltou trabalho.

**Correção:** contar estados terminais (`entregue` + `ausente`) e rotular
"resolvidos" ou "N restantes". "Restantes" é melhor: é o número que ele usa.

### 2.4 Sem sinal ao abrir a viagem, a tela fica em branco e muda

`EstadoViagemStore.erro` é preenchido em `recarregar()` (`ViagemStore.tsx:93`) e a
`ViagemScreen` **nunca o renderiza** — ela mostra `conflito`, `erroReordenar` e
`erroAtraso`, mas não `erro`. A `FlatList` também não tem `ListEmptyComponent`.

Resultado: GET inicial falhando (o cenário normal numa van) = lista vazia, sem
explicação, sem botão de tentar de novo. E a `ViagemScreen` não tem
`RefreshControl` (a `RotaDoDiaScreen` tem) — a única saída é sair e voltar.

**Correção:** renderizar `store.erro`, adicionar `ListEmptyComponent` e
`RefreshControl` chamando `store.recarregar`.

### 2.5 O bloqueio do §7.2 avisa mas não resolve

O guard de parada anterior pendente usa `Alert.alert` nativo (`ViagemScreen.tsx:59`),
lista os nomes e oferece só "Entendi". Ele **interrompe** o motorista sem levá-lo a
lugar nenhum — ele fecha o alerta e ainda precisa achar a linha na lista.

**Correção:** banner inline (mesma linguagem visual do resto) com botão
"Ir para {nome}" que rola até a linha pendente. O §7.2 pede *"forçar resolução na
tela imediatamente"* — levar até lá é mais fiel ao requisito do que só avisar.

### 2.6 O motorista não vê nenhum dado de tempo

O backend calcula tudo (B3): `atraso_acumulado_segundos` vem no `ViagemOut` e a
tela **ignora**; `chegou_em` vem no `TripStudentOut` e a tela ignora.

Consequências concretas:

- O motorista não sabe se está no horário. Descobre quando um responsável liga.
- Parado numa casa, ele não vê **há quanto tempo está esperando** — que é
  exatamente a informação que decide "espero mais ou sigo". Ironicamente o
  responsável vê esse cronômetro (§5, notificação persistente); quem está esperando
  de fato, não.
- Ao abrir "Estou atrasado", ele não vê quanto já empurrou antes — e pode empurrar
  +10 em cima de +10.

**Correção:** cronômetro de espera na linha em estado `chegou` (aritmética simples
sobre `chegou_em`, client-side, igual ao que o app do Responsável já faz), e
"no horário" / "~8 min atrasado" no cabeçalho a partir de
`atraso_acumulado_segundos`.

### 2.7 "Estou atrasado" falha exatamente quando é necessário

É online-only por decisão registrada (`ViagemScreen.tsx:76-79`), coerente com o
tratamento das outras ações de fronteira. Mas as outras ações de fronteira
acontecem na garagem, com sinal. Esta acontece **no meio da rota**, e o CLAUDE.md
§8 assume que a van sem sinal é o caso normal.

Além disso está num `<Text onPress>` de 13sp no **canto superior direito** — o
ponto mais distante do polegar numa mão.

**Correção:** avaliar entrada na fila offline (é idempotente por natureza: empurrar
a cauda em N minutos) e mover o gatilho para a metade inferior da tela.

---

## Severidade 3 — Legibilidade e feedback físico

### 3.1 Nenhum feedback tátil ou sonoro

Zero háptico, zero som em todo o app — `expo-haptics` não está nas dependências. O
único retorno de um toque é `opacity: 0.85` no estado pressed (`Botao56.tsx:85`).

Isso obriga o motorista a **olhar a tela para saber se o toque pegou**, que é
precisamente o que o §8 existe para evitar. É a correção de melhor custo-benefício
do documento inteiro: uma dependência, poucas linhas.

**Correção:** `impactAsync(Medium)` em Cheguei/Checkin/Checkout,
`notificationAsync(Success)` na sincronização, `notificationAsync(Error)` em
conflito e no bloqueio do §7.2.

### 3.2 A tela apaga durante a rota

Sem `expo-keep-awake`. Entre uma parada e outra o Android apaga e trava a tela; o
motorista destrava o telefone a cada casa.

**Correção:** `useKeepAwake()` ativo **apenas** enquanto a `ViagemScreen` estiver
montada (não no app inteiro — em cima do painel da van, com viagem em andamento, é
justificado; fora disso é só consumo de bateria).

### 3.3 Contraste reprovado em texto pequeno

Medidas de contraste da paleta (`shared/theme.ts`) contra WCAG AA (4.5:1 para texto
pequeno):

| Uso | Cores | Contraste | AA |
|---|---|---|---|
| `dica` sobre `cartao` (hints, "volte e resolva…") | `#8a958f` / `#fff` | **2,85:1** | ✗ |
| `ambar` sobre `cartao` (link "Estou atrasado", 13sp) | `#ba7517` / `#fff` | **3,72:1** | ✗ |
| `ambar` sobre `ambarSuave` (painel de atraso, 12,5sp) | `#ba7517` / `#faeeda` | **3,25:1** | ✗ |
| `esmaecido` sobre `cartao` (endereço) | `#5d6b65` / `#fff` | 5,59:1 | ✓ |

Ao sol, num aparelho antigo com tela riscada — o parque de aparelhos que o §2
descreve —, 2,85:1 em 11,5sp é ilegível.

Agravante de tamanho: corpo 15sp, endereço **12sp**, badge **11,5sp**, hints
**11,5sp**. O endereço é o dado que confirma que a parada é a certa, e está em 12sp.

**Correção:** escurecer `dica` e `ambar`, subir o endereço para 13–14sp, subir o
piso de fonte do app para 13sp.

### 3.4 Safe area declarada e não usada

`SafeAreaProvider` está no `App.tsx`, mas **nenhuma tela** usa `useSafeAreaInsets`
ou `SafeAreaView` — os cabeçalhos usam `paddingTop: espacamento.xl` (24dp fixo) e
os rodapés `padding: espacamento.lg` (16dp).

Com edge-to-edge (padrão no Expo SDK 54, que é o que está no `package.json`) e
barra de gestos, "Finalizar viagem", "Reordenar paradas" e "Voltar para a viagem"
caem na zona da barra de navegação — onde o polegar bate.

**Correção:** aplicar `useSafeAreaInsets().bottom` nos rodapés e `.top` nos
cabeçalhos.

### 3.5 Ações secundárias violam o piso de 56dp

O §8 é taxativo: *"alvo de toque mínimo 56dp"*. São `<Text onPress>` sem `hitSlop`,
altura efetiva ~18dp:

| Elemento | Arquivo |
|---|---|
| "Estou atrasado" | `ViagemScreen.tsx:171` |
| "Reordenar paradas" | `ViagemScreen.tsx:261` |
| "Ok" dos banners de conflito/atraso | `ViagemScreen.tsx:205,218` |
| "Voltar para a viagem" | `FinalizarViagemScreen.tsx:113` |
| "Sair" | `RotaDoDiaScreen.tsx:91` |

"Sair" e "Voltar" são de fato secundários e o argumento de alvo pequeno até protege
contra toque acidental. Mas **"Estou atrasado" é ação de rota**, usada em
movimento, e "Ok" do banner de conflito aparece quando algo já deu errado — os dois
piores momentos para exigir precisão.

**Correção:** `hitSlop` generoso em todos; `Botao56` de verdade em "Estou atrasado".

### 3.6 Reordenar por setas é inviável fora da garagem

As setas ▲▼ movem **uma posição por toque** (`ViagemScreen.tsx:128`). Reordenar 8
paradas = dezenas de toques precisos em alvos de 56×56 dentro do card.

Isso é aceitável se o reordenar acontece parado na garagem — que é onde deve
acontecer (§8: "antes do Cheguei"). Mas nada na tela comunica isso, e o link fica
disponível durante a viagem inteira.

**Correção:** "mover para o topo" como atalho, ou drag-and-drop. Baixa prioridade
— o caso de uso real é raro e estacionado.

### 3.7 Tema claro fixo

`userInterfaceStyle: "light"` no `app.json` e paleta clara (`papel #f4f1ea`). Rota
matinal começa no escuro; a tela branca ofusca dentro da van à noite.

**Correção:** tema escuro, ou no mínimo um toggle de brilho reduzido. Baixa
prioridade, custo alto.

---

## Priorização

Ordem sugerida, por (impacto no conforto ÷ custo):

| # | Item | Esforço |
|---|---|---|
| 1 | Expor "Desfazer chegada" (1.1) | baixo |
| 2 | Háptico nas 3 ações primárias (3.1) | baixo |
| 3 | Renderizar `store.erro` + empty state + pull-to-refresh (2.4) | baixo |
| 4 | Corrigir o contador do cabeçalho (2.3) | baixo |
| 5 | `useKeepAwake` na ViagemScreen (3.2) | baixo |
| 6 | Safe area nos rodapés (3.4) | baixo |
| 7 | Contraste + piso de fonte (3.3) | baixo |
| 8 | Cronômetro de espera + atraso acumulado (2.6) | médio |
| 9 | Card de parada atual / auto-scroll (2.1) | médio |
| 10 | Colapsar alunos terminais (2.2) | médio |
| 11 | Undo no store, ancorado, com fila (1.3) | médio |
| 12 | Banner "Ir para {nome}" no bloqueio §7.2 (2.5) | médio |
| 13 | Undo local de Ausente/Checkout (1.2) | médio — **validar §6 antes** |
| 14 | "Estou atrasado" na fila offline (2.7) | médio |
| 15 | Tema escuro (3.7) | alto |

Os sete primeiros somam algo próximo de um dia de trabalho e cobrem os dois
problemas mais graves — erro sem saída e ausência de feedback físico.

## Questões que precisam de decisão de produto

1. **Undo de Ausente/Checkout** (1.2) — o §6 declara "sem delay cancelável" sobre o
   Cheguei. Segurar outros eventos na fila por 5s vale a mesma regra?
2. **Contador do cabeçalho** (2.3) — "resolvidos" (inclui ausentes) ou "restantes"?
   Muda o que o motorista sente ao fechar o turno.
3. **"Estou atrasado" offline** (2.7) — entra na fila ou continua sendo ação de
   fronteira online-only?
