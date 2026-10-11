export type QaResult = 'PASS' | 'FAIL' | 'PENDING';
export type GuardLevel = 'GREEN' | 'YELLOW' | 'RED' | 'CRITICAL_STOP';
export type ExecutorKind = 'API' | 'CODEX';
export type RevisionStatus = 'DRAFT' | 'FROZEN' | 'READY_FOR_PUBLISH' | 'DRAFT_LEGACY';

export const FINALIZED_STATUSES = ['ACTIVE', 'FROZEN', 'READY_FOR_PUBLISH', 'SETTLED'] as const;

export const BLOCKED_TRANSITIONS: Array<{ from: string; to: string }> = [
  { from: 'FROZEN', to: 'DRAFT' },
  { from: 'READY_FOR_PUBLISH', to: 'DRAFT' },
  { from: 'READY_FOR_PUBLISH', to: 'FROZEN' },
  { from: 'SETTLED', to: 'PENDING' },
  { from: 'CANCELED', to: 'QUEUED' }
];

export function isBlocked(from: string, to: string): boolean {
  return BLOCKED_TRANSITIONS.some(item => item.from === from && item.to === to);
}

export function isFinalized(state: string): boolean {
  return (FINALIZED_STATUSES as readonly string[]).includes(state);
}
