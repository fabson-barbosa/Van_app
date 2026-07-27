# VaiVem — Painel Web do Gestor

Fase 0 do roadmap: a fundação sobre a qual as telas de negócio das fases 1 a 3 vão ser construídas.

Não há tela de negócio pronta aqui, e isso é proposital. O que está pronto é tudo aquilo que, se ficasse para depois, seria reimplementado de forma diferente em cada tela — e viraria dívida técnica por volta da sexta.

---

## Rodar

```bash
npm install
cp .env.example .env.local        # já vem com API_MODE=mock
npm run dev                       # http://localhost:3000
```

Contas de demonstração (senha `vaivem123` em todas):

| E-mail | Papel | O que enxerga |
|---|---|---|
| `owner@aurora.com.br` | Proprietário | Tudo |
| `gestor@aurora.com.br` | Gestor | Operação + financeiro, sem billing nem usuários |
| `financeiro@aurora.com.br` | Financeiro | Só o módulo financeiro — nem menu de alunos aparece |
| `auditor@aurora.com.br` | Auditor | Tudo em leitura, nada em escrita |

Entre com dois papéis diferentes e compare a barra lateral. É o teste mais rápido de que o RBAC está de pé.

---

## O que a Fase 0 entrega

**Autenticação ponta a ponta.** Login com validação Zod, sessão em JWT selado, cookie `httpOnly` + `SameSite=Lax`, logout. O token nunca chega ao JavaScript da página: quem autentica é um Route Handler agindo como BFF. Um XSS na página não consegue ler nem exfiltrar credencial.

**Guarda de rota na borda.** O `middleware.ts` verifica a sessão antes de a página renderizar, o que elimina o flash de tela protegida. Rota protegida acessada sem sessão redireciona para `/login?next=...` e volta ao destino depois de entrar.

**RBAC declarativo.** Permissões são pares `(recurso, ação)` — nunca "quem pode ver a tela X". Quatro papéis, uma matriz em `src/lib/auth/permissions.ts`, três formas de consumir:

```tsx
const podeEditar = useCan('alunos', 'update');            // hook, em client component
<Can resource="alunos" action="create">…</Can>            // componente
if (!can(user.role, 'financeiro')) return forbidden();     // server component / route handler
```

O front esconde o que o papel não permite. O backend revalida toda escrita. Esconder botão é UX, não controle de acesso — e os dois estão no lugar.

**Design system.** Tokens em `globals.css` (grafite quente, fundos dessaturados, dourado só como sinal — o esquema que sobreviveu às duas iterações do app Gestor). Onze componentes base: `Button`, `Input`, `Select`, `Field`, `Badge`, `Card`, `DataTable`, `EmptyState`, `Modal`, `ConfirmDialog`, `Drawer`, mais `Spinner`, `Skeleton` e `ErrorState`. As telas viram composição, não CSS novo.

**Camada de dados.** TanStack Query com política padrão definida uma vez: `staleTime` de 30s, sem refetch ao focar a janela, e retry que não insiste em 4xx (repetir um 403 não o transforma em 200).

**Padrão de tabela.** `DataTable` trata os quatro estados — carregando, erro, vazio, dados — num lugar só. Filtros, busca e paginação vivem na URL via `useTableParams`, então o link é compartilhável, o botão voltar funciona e um F5 não joga o gestor de volta à página 1 no meio de uma conferência.

**Troca mock ↔ API real por variável de ambiente.** `src/lib/api/index.ts` escolhe o adapter conforme `API_MODE`. Mock e cliente HTTP implementam a mesma interface `Backend`, então nenhuma tela muda quando o FastAPI ficar pronto.

**CI e testes.** GitHub Actions rodando typecheck, lint, testes unitários, build e E2E. 16 testes unitários (RBAC, sessão, backend mock, componentes) e 4 cenários Playwright, incluindo o que importa: um usuário `financeiro` que digita `/alunos` direto na barra de endereços leva 403, não a lista.

---

## Estrutura

```
src/
├── app/
│   ├── (auth)/login/          formulário de entrada
│   ├── (app)/                 tudo que exige sessão
│   │   ├── page.tsx           dashboard
│   │   ├── alunos/            tela de referência: busca, filtros, drawer, paginação
│   │   └── …                  demais rotas, protegidas, com escopo à vista
│   ├── api/                   route handlers (BFF)
│   ├── globals.css            tokens do design system
│   ├── error.tsx              boundary de erro
│   └── not-found.tsx
├── components/
│   ├── ui/                    componentes base
│   ├── layout/                sidebar, topbar
│   └── auth/                  <Can>, contexto de sessão
├── hooks/                     useCan, useTableParams
├── lib/
│   ├── api/                   contrato Backend + cliente HTTP
│   ├── auth/                  JWT, sessão, permissões, schemas
│   ├── mock/                  dados e adapter de demonstração
│   └── nav.ts                 navegação como dado, filtrada por permissão
└── middleware.ts              guarda de rota na borda
```

---

## Comandos

```bash
npm run dev          servidor de desenvolvimento
npm run verify       typecheck + lint + testes + build (o que a CI roda)
npm run test         testes unitários
npm run e2e          Playwright
npm run api:types    gera tipos TS a partir do OpenAPI do FastAPI
```

---

## Ligar no FastAPI

1. Suba o backend com os endpoints `POST /auth/login`, `GET /alunos`, `GET /dashboard/resumo`.
2. `npm run api:types` — os tipos passam a vir do OpenAPI. Divergência entre back e front vira erro de build, não bug em produção.
3. No `.env.local`: `API_MODE=http` e `API_BASE_URL=http://localhost:8000`.
4. Ajuste `src/lib/api/http-backend.ts` se os nomes de campo diferirem.

Nenhuma tela precisa mudar.

---

## Decisões que valem explicação

**Por que Next.js e não SPA pura.** Telas densas de dados carregam mais rápido com SSR em conexão ruim — realidade dos clientes-alvo. E o middleware na borda dá guarda de rota sem flash de conteúdo protegido.

**Por que JWT em cookie `httpOnly` e não em `localStorage`.** `localStorage` é legível por qualquer script na página. Cookie `httpOnly` não é. Custa um Route Handler a mais e remove uma classe inteira de ataque.

**Por que a navegação é dado e não JSX.** `src/lib/nav.ts` declara cada item com o par `(recurso, ação)` que o habilita. A sidebar filtra sozinha. Sem isso, cada novo papel espalharia mais um `if` pelo componente.

**Por que filtros na URL.** Estado local perde tudo num F5 e não dá para mandar o link para um colega. Custa um hook e resolve os dois.

**Por que os módulos futuros são rotas reais e não 404.** Um gestor que clica em "Financeiro" e vê o escopo previsto entende que o módulo existe e está por vir. Um 404 parece defeito.

---

## Estado da verificação

Rodado neste projeto: `tsc --noEmit` limpo, ESLint sem erro nem aviso, 16 testes unitários passando, `next build` compilando 16 rotas sem aviso. Os testes Playwright estão escritos e configurados; rodá-los exige o browser instalado (`npx playwright install chromium`), o que a CI faz.
