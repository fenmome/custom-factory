import type { App } from 'vue';

import type { RouteRecordRaw } from 'vue-router';

import NProgress from 'nprogress';
import { createRouter, createWebHistory } from 'vue-router';

import { createRouteGuard } from './guard';

import { constantRoutes, getAuthRoutes } from './routes';

import { localStg } from '@sa/utils';
import { STORAGE_KEYS } from '@/service/request';

NProgress.configure({ showSpinner: false, trickleSpeed: 200 });

export const router = createRouter({
  history: createWebHistory(import.meta.env.VITE_BASE_URL || '/'),
  routes: [...constantRoutes, ...getAuthRoutes()] as RouteRecordRaw[]
});

createRouteGuard(router);

export async function setupRouter(app: App) {
  app.use(router);
  await router.isReady();
}

export function getToken(): string | null {
  return localStg.get<string>(STORAGE_KEYS.token);
}

export function isWhiteList(name: unknown): boolean {
  return name === 'login';
}

export const ROUTE_HOME = '/dashboard/overview';
