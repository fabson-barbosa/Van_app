import { EmScopoPage } from '@/components/layout/em-escopo';
export default function Page() {
  return (
    <EmScopoPage
      resource="comunicacao"
      title="Comunicação"
      fase="Fase 3"
      itens={['Avisos por rota, escola ou geral', 'Modelos salvos reutilizáveis', 'Envio por app, WhatsApp e e-mail', 'Histórico com confirmação de leitura']}
    />
  );
}
