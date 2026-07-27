'use client';
import { useSessionUser } from '@/components/auth/session-context';
import { can, type Action, type Resource } from '@/lib/auth/permissions';

/**
 * Verificação de permissão nas telas.
 *
 *   const podeEditar = useCan('alunos', 'update');
 *
 * Serve para esconder ou desabilitar controles. Não é segurança —
 * a segurança está no backend, que revalida toda escrita.
 */
export function useCan(resource: Resource, action: Action = 'read') {
  const user = useSessionUser();
  return can(user.role, resource, action);
}
