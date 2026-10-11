import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios';

import { localStg } from '@sa/utils';

export const BACKEND_ERROR_CODE = 400;

export type FlatResponseSuccessData<T> = {
  type: 'success';
  data: T;
};

export type FlatResponseFailData<T> = {
  type: 'fail';
  data: null;
  code: number;
  msg: string;
  detail?: unknown;
};

export type FlatResponseData<T> = FlatResponseSuccessData<T> | FlatResponseFailData<T>;

export interface RequestInstanceState {
  /** 是否正在刷新 token */
  isRefreshingToken: boolean;
  /** 刷新期间被挂起的请求 */
  waitingQueue: Array<(token: string) => void>;
}

export interface CustomAxiosRequestConfig extends AxiosRequestConfig {
  /** 是否需要携带凭证 */
  needToken?: boolean;
}

const STORAGE_KEYS = {
  token: '__CF_TOKEN__'
} as const;

let customOptions: { baseURL: string } = { baseURL: '' };

export function setRequestInstanceOptions(options: { baseURL: string }) {
  customOptions = { ...customOptions, ...options };
}

export class CustomAxiosInstance {
  instance: AxiosInstance;

  backendErrorCode = BACKEND_ERROR_CODE;

  state: RequestInstanceState = {
    isRefreshingToken: false,
    waitingQueue: []
  };

  constructor(config: CustomAxiosRequestConfig) {
    this.instance = axios.create(config);
    this.#setupInterceptors();
  }

  #handleBackendFail(response: AxiosResponse, callback?: (data: FlatResponseFailData<null>) => void) {
    const body = response.data;
    const failData: FlatResponseFailData<null> = {
      type: 'fail',
      data: null,
      code: body?.code ?? this.backendErrorCode,
      msg: body?.message ?? body?.msg ?? '请求失败',
      detail: body?.detail
    };
    callback?.(failData);
    return failData;
  }

  #setupInterceptors() {
    this.instance.interceptors.request.use(
      async config => {
        const { needToken = true } = config as CustomAxiosRequestConfig;
        if (needToken) {
          const token = localStg.get<string>(STORAGE_KEYS.token);
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
          }
        }
        return config;
      },
      (error: AxiosError) => Promise.reject(error)
    );

    // 扁平化拦截器：返回 `{ data, error }` 而非 AxiosResponse
    this.instance.interceptors.response.use(
      (response: AxiosResponse) => this.#flattenSuccess(response) as unknown as AxiosResponse,
      (error: AxiosError) => this.#flattenError(error) as unknown as AxiosError
    );
  }

  #flattenSuccess(response: AxiosResponse): FlatResponse<unknown> {
    const { status } = response;
    if (status !== 200 && status !== 304 && status >= 300) {
      return {
        data: null,
        error: {
          type: 'fail',
          data: null,
          code: status,
          msg: (response.data as { message?: string })?.message ?? '网络异常'
        }
      };
    }

    const body = response.data;
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) {
        return { data: body.data, error: null };
      }
      if (body.code === 40101 && !response.config.url?.includes('/auth/login')) {
        localStg.remove(STORAGE_KEYS.token);
        window.location.href = '/login';
      }
      return { data: null, error: this.#handleBackendFail(response) };
    }
    return { data: body, error: null };
  }

  #flattenError(error: AxiosError): FlatResponse<never> {
    const body = error.response?.data as { code?: number; message?: string; msg?: string; detail?: unknown } | undefined;

    // 后端统一响应体优先：避免把 axios 的 "Request failed with status code 401" 直接抛给用户
    if (body && typeof body === 'object' && 'code' in body) {
      return {
        data: null,
        error: {
          type: 'fail',
          data: null,
          code: body.code ?? (error.response?.status ?? -1),
          msg: body.message ?? body.msg ?? '请求失败',
          detail: body.detail
        }
      };
    }

    return {
      data: null,
      error: {
        type: 'fail',
        data: null,
        code: error.response?.status ?? -1,
        msg: error.message || '请求失败'
      }
    };
  }
}

interface FlatResponse<T> {
  data: T | null;
  error: FlatResponseFailData<T> | null;
}

export function createFlatRequest(customConfig: CustomAxiosRequestConfig) {
  const wrapper = new CustomAxiosInstance({
    baseURL: customOptions.baseURL || customConfig.baseURL,
    timeout: 60_000,
    ...customConfig
  });

  // 响应拦截器已统一成 `{ data, error }` 结构，此处直接返回 Axios 实例（本身可调用）
  return wrapper.instance as unknown as FlatRequestInstance;
}

export interface FlatRequestInstance {
  <T = any>(config: CustomAxiosRequestConfig): Promise<{ data: T | null; error: RequestFailure | null }>;
  get<T = any>(url: string, config?: CustomAxiosRequestConfig): Promise<{ data: T | null; error: RequestFailure | null }>;
  post<T = any>(url: string, data?: unknown, config?: CustomAxiosRequestConfig): Promise<{ data: T | null; error: RequestFailure | null }>;
  defaults: { baseURL?: string };
}

export interface RequestFailure {
  type: 'fail';
  data: null;
  code: number;
  msg: string;
  detail?: unknown;
}

export type { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse };
export { BACKEND_ERROR_CODE as REQUEST_BACKEND_ERROR_CODE };
