import { request } from '../request';

/** 认证相关接口。 */
export function fetchLogin(params: Api.Auth.LoginParams) {
  return request<Api.Auth.LoginToken>({
    url: '/auth/login',
    method: 'post',
    data: params,
    needToken: false
  });
}

export function fetchLogout() {
  return request<{ logged_out: boolean }>({
    url: '/auth/logout',
    method: 'post'
  });
}

export function fetchMe() {
  return request<{ user: Api.Auth.UserInfo; workspace: Api.Auth.WorkspaceBrief | null }>({
    url: '/auth/me',
    method: 'get'
  });
}
