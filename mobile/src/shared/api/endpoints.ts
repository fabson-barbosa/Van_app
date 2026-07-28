import { api } from "./client";
import type {
  DeviceTokenRegistrar,
  EstouAtrasadoRequest,
  EventoAlunoRequest,
  EventoHistoricoOut,
  FilhoOut,
  LoginRequest,
  ReordenarRequest,
  StatusFilhoOut,
  TokenResponse,
  TripStudentOut,
  ViagemOut,
} from "./types";

export const endpoints = {
  login: (payload: LoginRequest) => api.post<TokenResponse>("/api/auth/login", payload),

  listarViagens: () => api.get<ViagemOut[]>("/api/viagens"),
  obterViagem: (viagemId: string) => api.get<ViagemOut>(`/api/viagens/${viagemId}`),
  iniciarViagem: (viagemId: string) => api.post<ViagemOut>(`/api/viagens/${viagemId}/iniciar`),
  finalizarViagem: (viagemId: string) => api.post<ViagemOut>(`/api/viagens/${viagemId}/finalizar`),
  estouAtrasado: (viagemId: string, payload: EstouAtrasadoRequest) =>
    api.post<ViagemOut>(`/api/viagens/${viagemId}/estou-atrasado`, payload),

  listarTripStudents: (viagemId: string) => api.get<TripStudentOut[]>(`/api/viagens/${viagemId}/trip-students`),
  reordenarTripStudents: (viagemId: string, payload: ReordenarRequest) =>
    api.patch<TripStudentOut[]>(`/api/viagens/${viagemId}/trip-students/reordenar`, payload),

  cheguei: (viagemId: string, tripStudentId: string, payload: EventoAlunoRequest) =>
    api.post<TripStudentOut>(`/api/viagens/${viagemId}/trip-students/${tripStudentId}/cheguei`, payload),
  checkin: (viagemId: string, tripStudentId: string, payload: EventoAlunoRequest) =>
    api.post<TripStudentOut>(`/api/viagens/${viagemId}/trip-students/${tripStudentId}/checkin`, payload),
  checkout: (viagemId: string, tripStudentId: string, payload: EventoAlunoRequest) =>
    api.post<TripStudentOut>(`/api/viagens/${viagemId}/trip-students/${tripStudentId}/checkout`, payload),
  ausente: (viagemId: string, tripStudentId: string, payload: EventoAlunoRequest) =>
    api.post<TripStudentOut>(`/api/viagens/${viagemId}/trip-students/${tripStudentId}/ausente`, payload),
  desfazerChegada: (viagemId: string, tripStudentId: string, payload: EventoAlunoRequest) =>
    api.post<TripStudentOut>(`/api/viagens/${viagemId}/trip-students/${tripStudentId}/desfazer-chegada`, payload),
  desfazerCheckin: (viagemId: string, tripStudentId: string, payload: EventoAlunoRequest) =>
    api.post<TripStudentOut>(`/api/viagens/${viagemId}/trip-students/${tripStudentId}/desfazer-checkin`, payload),

  // App Responsável (Bloco B5)
  listarFilhos: () => api.get<FilhoOut[]>("/api/responsavel/filhos"),
  statusFilho: (alunoId: string) => api.get<StatusFilhoOut>(`/api/responsavel/filhos/${alunoId}/status`),
  historicoFilho: (alunoId: string, data?: string) =>
    api.get<EventoHistoricoOut[]>(`/api/responsavel/filhos/${alunoId}/historico${data ? `?data=${data}` : ""}`),

  // Registro de push (Bloco B5)
  registrarTokenPush: (payload: DeviceTokenRegistrar) => api.post<void>("/api/dispositivos/token", payload),
  removerTokenPush: (token: string) => api.delete<void>("/api/dispositivos/token", { token }),
};

/** As 6 ações de evento do aluno que passam pela fila offline — CLAUDE.md §4. */
export type AcaoEvento = "cheguei" | "checkin" | "checkout" | "ausente" | "desfazer_chegada" | "desfazer_checkin";

export function chamarAcaoEvento(
  acao: AcaoEvento,
  viagemId: string,
  tripStudentId: string,
  payload: EventoAlunoRequest
): Promise<TripStudentOut> {
  const chamadas: Record<AcaoEvento, typeof endpoints.cheguei> = {
    cheguei: endpoints.cheguei,
    checkin: endpoints.checkin,
    checkout: endpoints.checkout,
    ausente: endpoints.ausente,
    desfazer_chegada: endpoints.desfazerChegada,
    desfazer_checkin: endpoints.desfazerCheckin,
  };
  return chamadas[acao](viagemId, tripStudentId, payload);
}
