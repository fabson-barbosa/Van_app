import React, { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AuthProvider } from "./src/shared/auth/AuthContext";
import { carregarPreferenciaSom } from "./src/shared/feedback";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { BarraStatusDoTema, TemaProvider } from "./src/shared/theme";

export default function App(): React.JSX.Element {
  // Preferência de som (Bloco B8). Best-effort e sem bloquear a renderização: se
  // a leitura falhar, o padrão (ligado) vale. Fica aqui, e não dentro do módulo
  // de som, para o `AsyncStorage` ser tocado uma vez no start e não no primeiro
  // toque do motorista.
  useEffect(() => {
    void carregarPreferenciaSom();
  }, []);

  return (
    <SafeAreaProvider>
      {/* O tema envolve o app inteiro porque a preferência é uma só; as telas que
          o B8 não redesenhou são travadas em claro por `comTemaClaro`, em
          `RootNavigator`. Ver `shared/theme/TemaContext.tsx`. */}
      <TemaProvider>
        <AuthProvider>
          <BarraStatusDoTema />
          <RootNavigator />
        </AuthProvider>
      </TemaProvider>
    </SafeAreaProvider>
  );
}
