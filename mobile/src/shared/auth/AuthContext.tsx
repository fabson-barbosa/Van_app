/**
 * Sessão do motorista — token JWT em SecureStore (backend expira em 60min,
 * `access_token_expire_minutes`, sem endpoint de refresh).
 *
 * Proposta de resolução para "token expira no meio de uma viagem offline"
 * (aprovada antes da implementação, ver PROGRESSO.md Bloco B4): a fila
 * offline (`shared/offline/sync.ts`) já para de drenar sozinha em qualquer
 * 401 (`pausadoPorAuth`) SEM descartar itens. Este contexto só observa esse
 * sinal (`sessaoExpirada`) e expõe `login()` de novo — o app renderiza um
 * prompt de reautenticação por cima da tela atual (RootNavigator), sem
 * navegar pra longe e sem perder o estado da viagem em andamento. Depois de
 * logar de novo, `retomarAposRelogin()` destrava a drenagem e os eventos
 * pendentes saem sozinhos.
 *
 * `tokenRef` (em vez de `configurarApi` reagir a `token` via `useEffect`):
 * achado testando em aparelho físico real — logo após um login bem-sucedido,
 * a tela autenticada (RotaDoDiaScreen) monta e já busca dados reagindo à
 * mudança de `token`. React roda o efeito do FILHO recém-montado antes do
 * efeito do ANCESTRAL (`AuthProvider`) na mesma leva de renderização — então
 * a primeira requisição podia sair ANTES do efeito que atualizaria
 * `config.getToken` rodar, sem Authorization nenhum, voltando 401 ("sessão
 * expirada") na hora, mesmo o login tendo funcionado. `tokenRef` é atualizado
 * SINCRONAMENTE dentro de `definirToken`, antes de qualquer `setState` —
 * `configurarApi` é chamado uma única vez, e `getToken` sempre lê o valor
 * atual do ref, nunca uma closure de render desatualizada.
 */
import * as SecureStore from "expo-secure-store";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { configurarApi } from "../api/client";
import { endpoints } from "../api/endpoints";
import type { UserRole } from "../api/types";
import { registrarPushToken, removerPushTokenAtual } from "../notifications";
import { retomarAposRelogin } from "../offline/sync";
import { decodeJwtPayload } from "./jwt";

const CHAVE_TOKEN = "vaivem:token";

/** `role` só decide QUAL STACK a UI mostra (RootNavigator) — nunca
 * autorização de verdade, que continua sendo o backend em cada request. */
function extrairRole(token: string | null): UserRole | null {
  if (!token) return null;
  const payload = decodeJwtPayload(token);
  const role = payload?.role;
  return typeof role === "string" ? (role as UserRole) : null;
}

interface AuthContextValue {
  token: string | null;
  role: UserRole | null;
  carregando: boolean;
  sessaoExpirada: boolean;
  login: (email: string, senha: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const [token, setToken] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [sessaoExpirada, setSessaoExpirada] = useState(false);
  const tokenRef = useRef<string | null>(null);

  const definirToken = useCallback((novo: string | null) => {
    tokenRef.current = novo;
    setToken(novo);
  }, []);

  // Configurado UMA VEZ — `getToken` lê `tokenRef.current` a cada chamada,
  // nunca uma closure presa ao valor de `token` no momento em que este
  // efeito rodou (ver docstring do módulo).
  useEffect(() => {
    configurarApi({
      getToken: async () => tokenRef.current,
      onUnauthorized: () => setSessaoExpirada(true),
    });
  }, []);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      // Sem o catch, qualquer rejeição aqui (SecureStore falhar por qualquer
      // motivo no primeiro launch) travava `carregando=true` pra sempre —
      // a tela de loading nunca soltava, sem erro visível nenhum. Achado
      // testando em aparelho físico real (não reproduzia no bundling nem no
      // typecheck). Tratar erro como "sem sessão salva" é o fallback seguro:
      // pior caso o motorista precisa logar de novo, nunca fica travado.
      let salvo: string | null = null;
      try {
        salvo = await SecureStore.getItemAsync(CHAVE_TOKEN);
      } catch (erro) {
        console.warn("Falha ao ler token do SecureStore — seguindo sem sessão salva.", erro);
      }
      if (!cancelado) {
        definirToken(salvo);
        setCarregando(false);
      }
    })();
    return () => {
      cancelado = true;
    };
  }, [definirToken]);

  const login = useCallback(
    async (email: string, senha: string) => {
      // `endpoints.login` lança ApiError/NetworkError se a autenticação em si
      // falhar — deixa propagar, é o único caso que deve virar "e-mail ou
      // senha inválidos" na tela.
      const resposta = await endpoints.login({ email, senha });

      // Daqui pra baixo a autenticação JÁ teve sucesso (o servidor validou a
      // senha). Uma falha de SecureStore aqui NÃO pode virar "credenciais
      // inválidas" — achado testando em aparelho físico real: o app mostrava
      // esse erro mesmo com o backend respondendo 200, porque o catch do
      // LoginScreen era genérico demais e o SecureStore falhava silenciosamente
      // (`expo-secure-store` tem falhas de escrita esporádicas documentadas em
      // alguns Android/Expo Go). Se persistir falhar, a sessão ainda funciona
      // pro resto deste uso do app — só não sobrevive a fechar/reabrir.
      try {
        await SecureStore.setItemAsync(CHAVE_TOKEN, resposta.access_token);
      } catch (erro) {
        console.warn("Falha ao salvar token no SecureStore — sessão válida só até fechar o app.", erro);
      }

      definirToken(resposta.access_token);
      setSessaoExpirada(false);
      retomarAposRelogin();

      // Best-effort (Bloco B5) — sem permissão/EAS projectId configurado, o
      // app segue funcionando normalmente, só sem push. Nunca bloqueia login.
      void registrarPushToken();
    },
    [definirToken]
  );

  const logout = useCallback(async () => {
    await removerPushTokenAtual();
    await SecureStore.deleteItemAsync(CHAVE_TOKEN);
    definirToken(null);
    setSessaoExpirada(false);
  }, [definirToken]);

  const role = useMemo(() => extrairRole(token), [token]);

  const value = useMemo<AuthContextValue>(
    () => ({ token, role, carregando, sessaoExpirada, login, logout }),
    [token, role, carregando, sessaoExpirada, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}
