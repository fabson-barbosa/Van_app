/**
 * Tema claro/escuro do app Motorista (Bloco B8).
 *
 * Três modos: `claro`, `escuro` e `automatico` (segue o Android). O padrão é
 * `automatico` — quem já usa o telefone em escuro permanente não devia precisar
 * configurar nada — e a escolha é persistida no aparelho.
 *
 * **Por que existe um `TemaClaroFixo`.** O escopo aprovado para o B8 é
 * reconstruir só o Motorista; as telas do Responsável e o Login ficam na paleta
 * atual. Elas importam `cores` (estático = claro) direto nos `StyleSheet`, mas os
 * componentes COMPARTILHADOS que vivem dentro delas (`Botao56`, `EstadoBadge`,
 * `PillSync`...) passaram a ler `useTema()`. Com o Android em modo escuro, isso
 * daria botão verde-claro e selos escuros sobre cartão creme — pior que não ter
 * tema nenhum.
 *
 * Então o provider de verdade fica em `App.tsx` (estado único, persistido) e as
 * telas fora do escopo são embrulhadas por `comTemaClaro`, que sobrescreve o
 * contexto com a paleta clara. Quando um bloco futuro redesenhar o Responsável,
 * apagar aquele embrulho é a única mudança necessária.
 *
 * Leitura e escrita da preferência são best-effort: `AsyncStorage` pode falhar
 * (armazenamento cheio, 1º launch). Falhar em ler significa cair no padrão, e
 * nunca travar a renderização — mesma lição do bug de loading infinito achado
 * em aparelho físico no B4.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { StatusBar } from "expo-status-bar";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useColorScheme } from "react-native";

import { type NomeModo, type Paleta, paletaClara, paletas } from "./paleta";

export type ModoTema = "claro" | "escuro" | "automatico";

export const CHAVE_MODO = "vaivem.tema.modo";

const MODOS_VALIDOS: ModoTema[] = ["claro", "escuro", "automatico"];

export function ehModoValido(valor: unknown): valor is ModoTema {
  return typeof valor === "string" && (MODOS_VALIDOS as string[]).includes(valor);
}

/** Resolve o modo efetivo. `automatico` delega ao Android; quando o sistema não
 * informa nada (`null`), assume claro — é o caso do aparelho antigo sem tema
 * escuro no sistema. */
export function resolverPaleta(modo: ModoTema, esquemaSistema: "light" | "dark" | null | undefined): Paleta {
  if (modo === "claro") return paletas.claro;
  if (modo === "escuro") return paletas.escuro;
  return esquemaSistema === "dark" ? paletas.escuro : paletas.claro;
}

interface Tema {
  cores: Paleta;
  /** Modo escolhido (pode ser `automatico`). */
  modo: ModoTema;
  /** Paleta em vigor agora — `claro` ou `escuro`, nunca `automatico`. */
  modoEfetivo: NomeModo;
  definirModo: (modo: ModoTema) => void;
}

const TemaContexto = createContext<Tema>({
  cores: paletaClara,
  modo: "claro",
  modoEfetivo: "claro",
  definirModo: () => undefined,
});

export function TemaProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const esquemaSistema = useColorScheme();
  const [modo, setModo] = useState<ModoTema>("automatico");

  useEffect(() => {
    let ativo = true;
    AsyncStorage.getItem(CHAVE_MODO)
      .then((salvo) => {
        if (ativo && ehModoValido(salvo)) setModo(salvo);
      })
      .catch(() => undefined);
    return () => {
      ativo = false;
    };
  }, []);

  const definirModo = useCallback((novo: ModoTema) => {
    setModo(novo);
    AsyncStorage.setItem(CHAVE_MODO, novo).catch(() => undefined);
  }, []);

  const cores = useMemo(() => resolverPaleta(modo, esquemaSistema), [modo, esquemaSistema]);

  const valor = useMemo<Tema>(
    () => ({ cores, modo, modoEfetivo: cores.nome, definirModo }),
    [cores, modo, definirModo]
  );

  return <TemaContexto.Provider value={valor}>{children}</TemaContexto.Provider>;
}

export function useTema(): Tema {
  return useContext(TemaContexto);
}

const TEMA_CLARO_FIXO: Tema = {
  cores: paletaClara,
  modo: "claro",
  modoEfetivo: "claro",
  definirModo: () => undefined,
};

/**
 * Trava a subárvore na paleta clara, ignorando a preferência do usuário.
 *
 * Para as telas que o B8 não redesenhou (Responsável, Login): elas desenham com
 * `cores` estático e não acompanhariam a troca, então os componentes
 * compartilhados dentro delas também não devem acompanhar.
 *
 * `barraStatus` só deve ser ligado por quem ocupa a tela inteira. `expo-status-bar`
 * resolve pela última instância montada, então um `<StatusBar style="dark">` num
 * componente montado mas invisível (um modal fechado, por exemplo) roubaria a cor
 * da barra do tema em vigor.
 */
export function TemaClaroFixo({
  children,
  barraStatus = false,
}: {
  children: React.ReactNode;
  barraStatus?: boolean;
}): React.JSX.Element {
  return (
    <TemaContexto.Provider value={TEMA_CLARO_FIXO}>
      {barraStatus ? <StatusBar style="dark" /> : null}
      {children}
    </TemaContexto.Provider>
  );
}

/** Versão HOC de `TemaClaroFixo`, para passar direto a `Stack.Screen`. */
export function comTemaClaro<P extends object>(
  Componente: React.ComponentType<P>
): (props: P) => React.JSX.Element {
  function ComTemaClaro(props: P): React.JSX.Element {
    return (
      <TemaClaroFixo barraStatus>
        <Componente {...props} />
      </TemaClaroFixo>
    );
  }
  ComTemaClaro.displayName = `comTemaClaro(${Componente.displayName ?? Componente.name ?? "Componente"})`;
  return ComTemaClaro;
}

/** Barra de status que acompanha a paleta em vigor. Usada no nível do app. */
export function BarraStatusDoTema(): React.JSX.Element {
  const { modoEfetivo } = useTema();
  return <StatusBar style={modoEfetivo === "escuro" ? "light" : "dark"} />;
}
