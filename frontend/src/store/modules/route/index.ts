import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { getMenuRoutes } from '@/router/routes';

export const useRouteStore = defineStore('route', () => {
  /** 菜单路由 */
  const menus = ref<Route.Route[]>(getMenuRoutes());

  /** 是否初始化过动态路由 */
  const isInitAuthRoute = ref(true);

  /** 去除隐藏项后的干净菜单 */
  const cleanMenus = computed(() => menus.value.filter(item => !item.meta.hideInMenu));

  function resetRouteStore() {
    menus.value = getMenuRoutes();
    isInitAuthRoute.value = true;
  }

  return {
    menus,
    cleanMenus,
    isInitAuthRoute,
    resetRouteStore
  };
});
