/**
 * Elegant routes（静态声明版）：所有页面懒加载，组件变量即为路由 name。
 *
 * 说明：本处保留 soybean-admin 的 **elegant routes 分层思路**（通过 `views` 目录同名
 * 组件变量自动建立映射），但去掉了 `elegant-router` 生成器的运行时依赖，
 * 以保证 `pnpm dev` 在离线环境下也能直接启动。
 */

import type { RouteComponent } from 'vue-router';

type RouteView = string | RouteComponent;

export const views: Record<string, RouteView> = {
  home: () => import('@/views/home/index.vue'),
  dashboard_overview: () => import('@/views/dashboard/overview/index.vue'),
  batch_list: () => import('@/views/batch/index/index.vue'),
  batch_detail: () => import('@/views/batch/detail/index.vue'),
  product_list: () => import('@/views/product/list/index.vue'),
  product_detail: () => import('@/views/product/detail/index.vue'),
  review_queue: () => import('@/views/review/queue/index.vue'),
  review_detail: () => import('@/views/review/detail/index.vue'),
  qa_false_positive: () => import('@/views/qa/false-positive/index.vue'),
  qa_calibration: () => import('@/views/qa/calibration/index.vue'),
  guard_status: () => import('@/views/guard/index/index.vue'),
  product_type_list: () => import('@/views/product-type/index.vue'),
  login: () => import('@/views/login/index.vue')
};

export const routeName = (key: keyof typeof views) => key as Route.RouteKey;

export const ROUTE_HOME = 'home';
