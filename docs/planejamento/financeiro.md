# Modelo financeiro

A planilha [`break-even-3vans.xlsx`](break-even-3vans.xlsx) contém o modelo completo (premissas, resultado e cenários).

## Resumo — transportador com 3 vans (~45 alunos)

| Modelo de cobrança | Receita/mês | Lucro/mês | Margem |
|---|---|---|---|
| R$ 49,90 por van | R$ 149,70 | ~R$ 140 | ~93% |
| R$ 9,90 por aluno | R$ 445,50 | ~R$ 432 | ~97% |

## Custos
- **Entrada (única):** Google Play US$ 25 (~R$ 140). Apple US$ 99/ano (opcional, só ao entrar no iOS).
- **Manutenção/mês:** infraestrutura ~R$ 8 em baixo volume (Cloud Run + banco free tier + FCM gratuito + domínio).
- **Variável:** gateway de pagamento ~1,2% (PIX) sobre o valor cobrado.

## Risco principal
O custo da **API de mapas** é o único que escala mal. Mitigação: tracking por eventos/ETA com cache, não streaming contínuo. Reavaliar plano do Google Maps a partir de ~15–20 vans.

> Todos os valores são editáveis na planilha (células destacadas).
