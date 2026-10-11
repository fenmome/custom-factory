import type { RouteRecordRaw } from 'vue-router';

import { Layout } from '@/router/constant';

import { routeName, views } from '../elegant/routes';

interface RawRoute {
  name: Route.RouteKey;
  path: string;
  component: keyof typeof views;
  meta: Route.RouteMeta;
}

const rawRoutes: RawRoute[] = [
  {
    name: routeName('home'),
    path: 'home',
    component: 'home',
    meta: { title: '首页', hideInMenu: true, hideInTab: true }
  },
  {
    name: routeName('dashboard_overview'),
    path: 'dashboard/overview',
    component: 'dashboard_overview',
    meta: { title: '生产总览', icon: 'DataLine', order: 1 }
  },
  {
    name: routeName('batch_list'),
    path: 'batch/list',
    component: 'batch_list',
    meta: { title: '批次管理', icon: 'Files', order: 2 }
  },
  {
    name: routeName('batch_detail'),
    path: 'batch/detail/:batchId',
    component: 'batch_detail',
    meta: { title: '批次详情', hideInMenu: true, activeMenu: 'batch_list', multiTab: true }
  },
  {
    name: routeName('product_list'),
    path: 'product/list',
    component: 'product_list',
    meta: { title: 'SKU 管理', icon: 'Goods', order: 3 }
  },
  {
    name: routeName('product_detail'),
    path: 'product/detail/:productId',
    component: 'product_detail',
    meta: { title: 'SKU 详情', hideInMenu: true, activeMenu: 'product_list', multiTab: true }
  },
  {
    name: routeName('review_queue'),
    path: 'review/queue',
    component: 'review_queue',
    meta: { title: '人工复审队列', icon: 'View', order: 4 }
  },
  {
    name: routeName('review_detail'),
    path: 'review/detail/:productId',
    component: 'review_detail',
    meta: { title: 'SKU 复审', hideInMenu: true, activeMenu: 'review_queue', multiTab: true }
  },
  {
    name: routeName('qa_false_positive'),
    path: 'qa/false-positive',
    component: 'qa_false_positive',
    meta: { title: '误判看板', icon: 'Warning', order: 5 }
  },
  {
    name: routeName('qa_calibration'),
    path: 'qa/calibration',
    component: 'qa_calibration',
    meta: { title: 'QA 校准', icon: 'Aim', order: 6 }
  },
  {
    name: routeName('guard_status'),
    path: 'guard/status',
    component: 'guard_status',
    meta: { title: '生产保护', icon: 'Lock', order: 7 }
  },
  {
    name: routeName('product_type_list'),
    path: 'product-type/list',
    component: 'product_type_list',
    meta: { title: '产品类型 / SKU 规则', icon: 'Setting', order: 8 }
  }
];

/** 登录页等常量路由（不包裹 Layout）。 */
export const constantRoutes: RouteRecordRaw[] = [
  {
    name: routeName('login'),
    path: '/login',
    component: views.login as never,
    meta: { title: '登录', constant: true, hideInMenu: true } as never
  },
  {
    name: 'root',
    path: '/',
    redirect: '/dashboard/overview',
    meta: { title: 'root', constant: true, hideInMenu: true } as never
  },
  {
    name: 'not-found',
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard/overview',
    meta: { title: '未找到', constant: true, hideInMenu: true } as never
  }
];

/** 需要登录鉴权的主框架路由。 */
export function getAuthRoutes(): RouteRecordRaw[] {
  return [
    {
      name: 'layout',
      path: '/',
      component: Layout as never,
      redirect: '/dashboard/overview',
      meta: { title: 'Custom Factory', constant: false } as never,
      children: rawRoutes.map(item => ({
        name: item.name,
        path: item.path,
        component: views[item.component] as never,
        meta: item.meta as never
      }))
    }
  ];
}

/** 供菜单渲染使用的扁平路由元数据。 */
export function getMenuRoutes(): Route.Route[] {
  return rawRoutes
    .filter(item => !item.meta.hideInMenu)
    .map(
      item =>
        ({
          name: item.name,
          path: item.path,
          meta: item.meta
        }) as unknown as Route.Route
    )
    .sort((a, b) => (a.meta.order ?? 99) - (b.meta.order ?? 99));
}
