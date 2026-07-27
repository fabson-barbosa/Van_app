# Fase 0 — o que era preciso, e o que está feito

Checklist do que a fundação exigia, com o estado de cada item e onde ele mora no código.

---

## E1 · Setup e infraestrutura — feito

| Item | Estado | Onde |
|---|---|---|
| Projeto Next.js 15 (App Router) + TypeScript strict | ✅ | `next.config.ts`, `tsconfig.json` |
| Tailwind v4 com tokens em CSS | ✅ | `postcss.config.mjs`, `src/app/globals.css` |
| ESLint 9 flat config + Prettier com ordenação de classes | ✅ | `eslint.config.mjs`, `.prettierrc` |
| Variáveis de ambiente documentadas | ✅ | `.env.example` |
| Cabeçalhos de segurança (frame, sniff, referrer, permissions) | ✅ | `next.config.ts` |
| Geração de tipos a partir do OpenAPI | ✅ script pronto | `npm run api:types` |
| Pipeline de CI | ✅ | `.github/workflows/ci.yml` |

O script `api:types` existe mas ainda não foi exercitado — depende do FastAPI expor `/openapi.json`. É o primeiro item a validar quando o backend subir.

---

## E2 · Design system — feito

**Tokens.** Grafite quente (`#2e2b29`) em vez de preto puro, fundos dessaturados, dourado (`#b8862b`) reservado para sinal. Cinco pares de cor semântica (ok / warn / danger / info / neutral), cada um com fundo suave e texto de contraste suficiente. Duas famílias tipográficas: Sora nos títulos, Plus Jakarta Sans no corpo, auto-hospedadas via `next/font` — sem requisição a terceiros em runtime.

**Componentes.**

| Componente | Resolve |
|---|---|
| `Button` | 5 variantes, 3 tamanhos, estado de carregamento que já desabilita |
| `Input` / `Select` | foco visível, `aria-invalid` |
| `Field` | rótulo + dica + erro com `role="alert"`, associação por `htmlFor` |
| `Badge` | 5 tons semânticos |
| `Card` / `CardHeader` / `CardBody` | contêiner padrão |
| `DataTable` | os quatro estados + paginação, num lugar só |
| `EmptyState` | vazio que diz o que houve e oferece a próxima ação |
| `Modal` / `ConfirmDialog` | `<dialog>` nativo: foco, Esc e backdrop sem biblioteca |
| `Drawer` | detalhe lateral sem perder o contexto da lista |
| `Spinner` / `Skeleton` / `ErrorState` | carregando e falha |

Storybook ficou de fora. A tela de alunos e a matriz de permissões em `/config` já servem de vitrine viva, e Storybook adicionaria uma segunda pipeline de build para manter. Vale reconsiderar quando houver uma segunda pessoa no frontend.

---

## E3 · Autenticação — feito, com um item adiado

| Item | Estado |
|---|---|
| Formulário de login com validação Zod | ✅ |
| Sessão em JWT selado (`jose`, HS256, 8h) | ✅ |
| Cookie `httpOnly` + `SameSite=Lax` + `secure` em produção | ✅ |
| BFF: token nunca chega ao browser | ✅ |
| Logout | ✅ |
| Redirecionamento com `?next=` e retorno ao destino | ✅ |
| Mensagem de erro que não revela se o e-mail existe | ✅ |
| 2FA por TOTP | ⏳ adiado |
| Recuperação de senha | ⏳ depende de envio de e-mail no backend |
| Refresh rotativo | ⏳ sessão de 8h cobre a jornada; entra quando houver mobile web |

Os três adiados dependem de backend real e nenhum bloqueia a Fase 1. Ficam na entrada da Fase 4.

---

## E4 · Layout, navegação e RBAC — feito

**Quatro papéis, uma matriz.** `owner`, `gestor`, `financeiro`, `auditor` sobre 14 recursos e 5 ações. A regra que orientou o desenho: o papel `financeiro` não enxerga dado de criança nem de rota. Um contador não precisa saber onde uma criança de 7 anos mora — e a LGPD concorda.

**Três pontos de checagem, um só lugar de verdade.**

```
src/lib/auth/permissions.ts   ← matriz
  ├── can()                   servidor: página, route handler
  ├── useCan()                cliente: hook
  └── <Can>                   cliente: componente
```

**Aplicado em quatro camadas.** Sidebar filtra itens. Página verifica e devolve 403 explicado. Route handler revalida antes de responder. Backend revalidará de novo — o front é conveniência, não barreira.

**Shell.** Sidebar com grupos, item ativo por rota, `aria-current`, identificação de tenant e papel no rodapé. Topbar com breadcrumb, busca global e sair.

---

## E5 · Camada de dados — feito

Política do TanStack Query definida uma vez em `src/components/providers.tsx`: `staleTime` 30s, sem refetch ao focar a janela, retry que não insiste em 4xx.

`useTableParams` mantém busca, filtros e página na URL. Busca com debounce de 350ms — sem isso, cada tecla vira uma requisição. Troca de página usa `keepPreviousData`, então a tabela não pisca.

A tela `/alunos` existe como referência viva desses padrões: 134 registros mockados, busca, dois filtros, paginação, drawer de detalhe e um estado vazio diferente conforme haja ou não filtro aplicado.

---

## Qualidade — feito

**16 testes unitários passando.**

- RBAC: 6 casos, incluindo o negativo que mais importa (financeiro não lê aluno, auditor não escreve nada)
- Sessão: selagem, abertura, rejeição de token adulterado e de lixo
- Backend mock: autenticação, recusa sem vazamento, paginação, filtros
- Componentes: `EmptyState`, `Button` em loading, `Field` com erro anunciado

**4 cenários Playwright escritos.** Redirecionamento de visitante, login e navegação completos, credencial inválida, e o cenário que fecha o RBAC: papel `financeiro` digitando `/alunos` na barra de endereços recebe 403.

**Verificação executada:** `tsc --noEmit` limpo · ESLint sem erro nem aviso · 16/16 testes · `next build` compilando 16 rotas sem aviso.

---

## O que ficou de fora, e por quê

| Item | Motivo |
|---|---|
| Storybook | Segunda pipeline de build para manter, com uma pessoa no frontend. Reconsiderar quando o time crescer |
| 2FA, recuperação de senha, refresh rotativo | Dependem de backend real; não bloqueiam a Fase 1 |
| Tema escuro | Nenhum gestor pediu. Os tokens já estão em CSS variables, então é uma folha a mais quando pedirem |
| Internacionalização | Produto é Brasil. Adicionar i18n agora é custo sem retorno |
| Observabilidade (Sentry) | O `error.tsx` já tem o ponto de integração marcado. Entra junto com o primeiro deploy de produção |

---

## Primeiros passos da Fase 1

1. `POST /auth/login` no FastAPI e trocar `API_MODE=mock` por `http`. Valida o contrato inteiro de ponta a ponta antes de qualquer tela nova.
2. CRUD de alunos aproveitando `DataTable`, `Drawer` e `Field` — mede se o design system aguenta uma tela real.
3. Importação em massa. É o item que destrava vendas: um operador com 80 alunos não cadastra um por um, e enquanto não existir, todo onboarding depende de você pessoalmente.
