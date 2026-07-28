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

// ---------------------------------------------------------------------------
// App Responsável (Bloco B5) — espelha app/schemas/responsavel.py
// ---------------------------------------------------------------------------

export interface FilhoOut {
  aluno_id: string;
  nome: string;
  parada_endereco: string | null;
}

/** Mapa VIRTUAL (CLAUDE.md §2/§10): progresso por PARADA, nunca coordenada.
 * `faixa_min_*` nunca é minuto exato (CLAUDE.md §5). */
export interface StatusFilhoOut {
  aluno_id: string;
  tem_viagem_hoje: boolean;
  viagem_status: ViagemStatus | null;
  estado: TripStudentEstado | null;
  paradas_totais: number | null;
  paradas_concluidas: number | null;
  paradas_restantes: number | null;
  faixa_min_baixo: number | null;
  faixa_min_alto: number | null;
  chegou_em: string | null;
}

export type TipoEventoHistorico = "cheguei" | "checkin" | "checkout" | "ausente";

export interface EventoHistoricoOut {
  tipo: TipoEventoHistorico;
  ocorrido_em: string;
}

// ---------------------------------------------------------------------------
// Dispositivos / push (Bloco B5) — espelha app/schemas/dispositivos.py
// ---------------------------------------------------------------------------

export type DeviceTokenProvider = "expo" | "fcm";

export interface DeviceTokenRegistrar {
  token: string;
  provider?: DeviceTokenProvider;
}

export interface DeviceTokenRemover {
  token: string;
}

/** `data` de um push da cascata (CLAUDE.md §5) — sempre carrega os ids de
 * roteamento (Bloco B5, `pos_evento._payload_com_rota`), mais o `tipo`. */
export interface PushDataCascata {
  tipo: "chegada" | "iminencia" | "preparo" | "dismiss_chegada";
  viagem_id?: string;
  trip_student_id?: string;
  aluno_id?: string;
  faixa_min_baixo?: number;
  faixa_min_alto?: number;
  /** Só em `tipo: "chegada"` — ancora o texto da notificação persistente
   * (CLAUDE.md §5) sem round-trip extra à API. */
  chegou_em?: string;
}
