import { EmScopoPage } from '@/components/layout/em-escopo';
export default function Page() {
  return (
    <EmScopoPage
      resource="relatorios"
      title="Relatórios"
      fase="Fase 3"
      itens={['Pontualidade por rota e motorista', 'Frequência por aluno', 'Quilometragem por veículo', 'Receita e inadimplência', 'Trilha de auditoria (LGPD)']}
    />
  );
}
