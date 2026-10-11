import { request } from '../request';

export function fetchWorkspaceList() {
  return request<{ items: Api.Workspace.Item[]; current: string }>({
    url: '/workspaces',
    method: 'get'
  });
}
