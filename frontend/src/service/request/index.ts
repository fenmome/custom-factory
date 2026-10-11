import type { AxiosRequestConfig } from 'axios';

import { createFlatRequest } from '@sa/axios';

import { localStg } from '@sa/utils';

export const STORAGE_KEYS = {
  token: '__CF_TOKEN__',
  refreshToken: '__CF_REFRESH_TOKEN__',
  userInfo: '__CF_USER_INFO__'
} as const;

export const VITE_SERVICE_BASE = import.meta.env.VITE_SERVICE_BASE ?? '/api/v1';

/** 扁平化底层实例。 */
export const flatRequest = createFlatRequest({
  baseURL: createServiceBaseUrl(),
  headers: {
    'Content-Type': 'application/json'
  }
});

export interface RequestFailure {
  type: 'fail';
  code: number;
  msg: string;
  detail?: unknown;
}

export type RequestResult<T> = Promise<{ data: T | null; error: RequestFailure | null }>;

/** 统一业务请求入口：始终 resolve，错误通过 `error` 字段返回。 */
export function request<T = any>(config: AxiosRequestConfig & { needToken?: boolean }): RequestResult<T> {
  return flatRequest(config) as RequestResult<T>;
}

export function getAuthorization(): string | null {
  const token = localStg.get<string>(STORAGE_KEYS.token);
  return token ? `Bearer ${token}` : null;
}

export function clearAuthStorage() {
  localStg.remove(STORAGE_KEYS.token);
  localStg.remove(STORAGE_KEYS.refreshToken);
  localStg.remove(STORAGE_KEYS.userInfo);
}

function createServiceBaseUrl(): string {
  const { VITE_SERVICE_BASE = '' } = import.meta.env;
  if (VITE_SERVICE_BASE) return VITE_SERVICE_BASE;
  return '/api/v1';
}
