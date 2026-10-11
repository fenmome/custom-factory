export function setupAppVersionNotification() {
  // no-op：版本更新通知由部署层处理
}

export const STORAGE_KEYS = {
  token: '__CF_TOKEN__',
  refreshToken: '__CF_REFRESH_TOKEN__',
  userInfo: '__CF_USER_INFO__'
} as const;
