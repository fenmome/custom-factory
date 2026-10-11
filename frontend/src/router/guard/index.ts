import type { RouteLocationNormalizedLoaded } from 'vue-router';

import NProgress from 'nprogress';
import { ElMessage } from 'element-plus';

import type { Router } from 'vue-router';

import { STORAGE_KEYS } from '@/service/request';
import { routeName } from '@/router/elegant/routes';

export function createRouteGuard(router: Router) {
  router.beforeEach(async (to, _from, next) => {
    NProgress.start();

    const token = localStorage.getItem(STORAGE_KEYS.token);
    const hasToken = Boolean(token && token !== 'null');

    if (to.name === routeName('login')) {
      next();
      return;
    }

    if (!hasToken) {
      ElMessage.warning('请先登录');
      next({ name: routeName('login'), query: { redirect: to.fullPath } });
      return;
    }

    next();
  });

  router.afterEach((to: RouteLocationNormalizedLoaded) => {
    NProgress.done();
    document.title = to.meta?.title ? `${to.meta.title} · Custom Factory` : 'Custom Factory';
  });
}
