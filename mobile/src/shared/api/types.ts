/**
 * Espelho dos schemas Pydantic do backend (`backend/app/schemas/`).
 * Mantido manualmente — sem gerador de cliente nesta rodada (CLAUDE.md não
 * pede, e o contrato é pequeno o bastante para não compensar a dependência).
 */

export type UserRole = "admin" | "motorista" | "motorista_backup" | "responsavel";

export type ViagemStatus = "planejada" | "em_andamento" | "finalizada";

export type TripStudentEstado = "aguardando" | "chegou" | "a_bordo" | "entregue" | "ausente";

export interface LoginRequest {
  email: string;
  senha: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface ViagemOut {
  id: string;
  tenant_id: string;
  rota_id: string;
  veiculo_id: string;
  motorista_id: string;
  data: string; // YYYY-MM-DD
  status: ViagemStatus;
  iniciada_em: string | null;
  finalizada_em: string | null;
  atraso_acumulado_segundos: number;
  varredura_confirmada: boolean;
  created_at: string;
  updated_at: string;
  rota_nome: string;
  rota_turno: string;
  rota_escola: string | null;
  total_alunos: number;
}

export interface TripStudentOut {
  id: string;
  viagem_id: string;
  aluno_id: string;
  parada_id: string | null;
  ordem: number;
  estado: TripStudentEstado;
  chegou_em: string | null;
  checkin_em: string | null;
  checkout_em: string | null;
  ausente_em: string | null;
  aluno_nome: string;
  parada_endereco: string | null;
}

/** Payload comum aos 6 endpoints de evento — CLAUDE.md §4/§8, Bloco B4. */
export interface EventoAlunoRequest {
  event_id: string;
  device_timestamp: string | null;
  device_enviado_em: string | null;
}

export interface ReordenarItem {
  trip_student_id: string;
  ordem: number;
}

export interface ReordenarRequest {
  itens: ReordenarItem[];
}

export interface EstouAtrasadoRequest {
  minutos: number;
}

/** Corpo de erro de domínio (409) devolvido por `_mapear_erro_dominio`. */
export interface ErroDominio {
  detail: string;
}
