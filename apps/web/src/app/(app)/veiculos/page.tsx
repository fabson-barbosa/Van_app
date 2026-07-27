import { EmScopoPage } from '@/components/layout/em-escopo';
export default function Page() {
  return (
    <EmScopoPage
      resource="veiculos"
      title="Veículos"
      fase="Fase 1"
      itens={['Cadastro da frota e capacidade', 'CRLV, vistoria e seguro com alerta de vencimento', 'Detecção de conflito de horário entre rotas', 'Histórico de manutenção']}
    />
  );
}
