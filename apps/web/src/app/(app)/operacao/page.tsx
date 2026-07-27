import { EmScopoPage } from '@/components/layout/em-escopo';
export default function Page() {
  return (
    <EmScopoPage
      resource="operacao"
      title="Operação ao vivo"
      fase="Fase 2"
      itens={['Mapa ao vivo dos veículos', 'Linha do tempo de eventos do dia', 'Registro e tratativa de ocorrências', 'Confirmação de varredura de fim de rota']}
    />
  );
}
