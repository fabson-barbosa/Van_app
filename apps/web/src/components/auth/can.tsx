'use client';
import * as React from 'react';
import { useCan } from '@/hooks/use-can';
import type { Action, Resource } from '@/lib/auth/permissions';

/** Renderiza os filhos só quando o papel do usuário permite a ação. */
export function Can({
  resource,
  action = 'read',
  fallback = null,
  children,
}: {
  resource: Resource;
  action?: Action;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}) {
  return useCan(resource, action) ? <>{children}</> : <>{fallback}</>;
}
