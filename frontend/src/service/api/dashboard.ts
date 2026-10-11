import { request } from '../request';

export function fetchOverview() {
  return request<Api.Dashboard.Overview>({
    url: '/dashboard/overview',
    method: 'get'
  });
}

export function fetchClaimsPanel() {
  return request<{ items: Array<Record<string, unknown>> }>({
    url: '/dashboard/claims',
    method: 'get'
  });
}
