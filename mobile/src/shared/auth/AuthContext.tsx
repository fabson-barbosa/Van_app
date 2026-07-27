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
 */
import * as SecureStore from "expo-secure-store";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { configurarApi } from "../api/client";
import { endpoints } from "../api/endpoints";
import { retomarAposRelogin } from "../offline/sync";

const CHAVE_TOKEN = "vaivem:token";

interface AuthContextValue {
  token: string | null;
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

  useEffect(() => {
    configurarApi({
      getToken: async () => token,
      onUnauthorized: () => setSessaoExpirada(true),
    });
  }, [token]);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const salvo = await SecureStore.getItemAsync(CHAVE_TOKEN);
      if (!cancelado) {
        setToken(salvo);
        setCarregando(false);
      }
    })();
    return () => {
      cancelado = true;
    };
  }, []);

  const login = useCallback(async (email: string, senha: string) => {
    const resposta = await endpoints.login({ email, senha });
    await SecureStore.setItemAsync(CHAVE_TOKEN, resposta.access_token);
    setToken(resposta.access_token);
    setSessaoExpirada(false);
    retomarAposRelogin();
  }, []);

  const logout = useCallback(async () => {
    await SecureStore.deleteItemAsync(CHAVE_TOKEN);
    setToken(null);
    setSessaoExpirada(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ token, carregando, sessaoExpirada, login, logout }),
    [token, carregando, sessaoExpirada, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}
