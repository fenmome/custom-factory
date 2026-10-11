import { request } from '../request';

export function fetchGuardStatus() {
  return request<Api.Guard.Status>({
    url: '/guard/status',
    method: 'get'
  });
}

export function evaluateGuard() {
  return request<Record<string, unknown>>({
    url: '/guard/evaluate',
    method: 'post'
  });
}

export function fetchPauses() {
  return request<{ items: Api.Guard.PauseBrief[] }>({
    url: '/guard/pauses',
    method: 'get'
  });
}

export function startTrial(controlId: string) {
  return request<Api.Guard.PauseBrief>({
    url: `/guard/pauses/${controlId}/trial`,
    method: 'post',
    data: {}
  });
}

export function reportTrialResult(controlId: string, result: 'PASS' | 'FAIL') {
  return request<Api.Guard.PauseBrief>({
    url: `/guard/pauses/${controlId}/trial/result`,
    method: 'post',
    params: { result }
  });
}

export function criticalStop(reason: string) {
  return request<Api.Guard.PauseBrief>({
    url: '/guard/critical-stop',
    method: 'post',
    params: { reason }
  });
}

export function dismissPause(controlId: string) {
  return request<{ id: string; state: string }>({
    url: `/guard/pauses/${controlId}`,
    method: 'delete'
  });
}

export function fetchActiveClaims() {
  return request<{ items: Array<Record<string, unknown>>; total: number }>({
    url: '/guard/claims',
    method: 'get'
  });
}
