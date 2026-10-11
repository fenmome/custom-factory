import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { clearAuthStorage, STORAGE_KEYS } from '@/service/request';
import { fetchLogin, fetchMe } from '@/service/api/auth';
import { localStg } from '@sa/utils';

export const useAuthStore = defineStore('auth', () => {
  /** token */
  const token = ref(localStg.get<string>(STORAGE_KEYS.token) ?? '');

  const userInfo = ref<Api.Auth.UserInfo>({
    id: '',
    email: '',
    display_name: '',
    state: 'ACTIVE',
    is_superuser: false
  });

  const workspace = ref<Api.Auth.WorkspaceBrief | null>(null);

  const isLogin = computed(() => Boolean(token.value));

  const role = computed(() => workspace.value?.role ?? '');

  function setToken(next: string) {
    token.value = next;
    localStg.set(STORAGE_KEYS.token, next);
  }

  async function login(params: Api.Auth.LoginParams) {
    const result = await fetchLogin(params);

    if (!result.error) {
      setToken(result.data!.token);
      userInfo.value = result.data!.user;
      workspace.value = result.data!.workspace;
      return { success: true as const };
    }

    return { success: false as const, error: result.error.msg };
  }

  async function loadMe() {
    const result = await fetchMe();
    if (!result.error && result.data) {
      userInfo.value = result.data.user;
      workspace.value = result.data.workspace;
    }
    return result;
  }

  function reset() {
    token.value = '';
    userInfo.value = { id: '', email: '', display_name: '', state: 'ACTIVE', is_superuser: false };
    workspace.value = null;
    clearAuthStorage();
  }

  return {
    token,
    userInfo,
    workspace,
    isLogin,
    role,
    setToken,
    login,
    loadMe,
    reset
  };
});
