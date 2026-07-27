import { EmScopoPage } from '@/components/layout/em-escopo';
export default function Page() {
  return (
    <EmScopoPage
      resource="rotas"
      title="Rotas"
      fase="Fase 2"
      itens={['Editor de rota com mapa e paradas arrastáveis', 'Cálculo de ETA por parada', 'Alerta de capacidade excedida', 'Sugestão de ordenação (aceita manualmente)', 'Versionamento e vigência']}
    />
  );
}
