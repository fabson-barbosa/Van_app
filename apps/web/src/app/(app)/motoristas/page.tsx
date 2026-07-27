import { EmScopoPage } from '@/components/layout/em-escopo';
export default function Page() {
  return (
    <EmScopoPage
      resource="motoristas"
      title="Motoristas"
      fase="Fase 1"
      itens={['Cadastro e vínculo com veículo e rota', 'Documentos com data de validade (CNH, curso escolar)', 'Alertas de vencimento em D-30, D-15 e D-1', 'Indicadores de pontualidade']}
    />
  );
}
