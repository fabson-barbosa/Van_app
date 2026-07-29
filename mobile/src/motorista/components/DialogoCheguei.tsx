/**
 * Diálogo do "Cheguei" (CLAUDE.md §6). Conteúdo taxativo: nome do aluno em
 * destaque, endereço abaixo (peso leve, cor secundária, ~13sp), dois botões —
 * Confirmar/Cancelar, nada mais.
 *
 * O §6 é explícito sobre POR QUE o nome vem em destaque e um "Confirmar?"
 * genérico não serve: o erro que importa é Cheguei na parada errada, e só o
 * nome do aluno permite pegar esse erro antes do push sair.
 *
 * Desde o B7 é uma casca fina sobre `DialogoConfirmacao` — a anatomia é a
 * mesma dos demais diálogos, e mantê-las no mesmo componente impede que as
 * duas linguagens visuais divirjam com o tempo. O que este arquivo preserva é
 * o CONTRATO do §6 (o que entra em cada campo), não o desenho.
 */
import React from "react";

import { DialogoConfirmacao } from "../../shared/components/DialogoConfirmacao";

interface Props {
  visivel: boolean;
  nomeAluno: string;
  endereco: string | null;
  onConfirmar: () => void;
  onCancelar: () => void;
}

export function DialogoCheguei({
  visivel,
  nomeAluno,
  endereco,
  onConfirmar,
  onCancelar,
}: Props): React.JSX.Element {
  return (
    <DialogoConfirmacao
      visivel={visivel}
      titulo={nomeAluno}
      subtitulo={endereco}
      rotuloConfirmar="Confirmar"
      // Chegar numa parada não é destrutivo — o verde da marca está certo aqui.
      // O push sai imediatamente depois (§6), mas `chegou` ainda tem volta pelo
      // "Desfazer chegada" (§4), diferente de `ausente`/`entregue`.
      varianteConfirmar="primario"
      onConfirmar={onConfirmar}
      onCancelar={onCancelar}
    />
  );
}
