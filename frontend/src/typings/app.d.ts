declare namespace App {
  type ThemeColorType = 'default';

  interface GlobalTab {
    /** 多页签 tab 的 key */
    fullPath: string;
    /** 路由名称 */
    label: App.I18n.I18nKey | string;
    meta?: Route.RouteMeta;
    routePath: Route.RoutePath;
    routeName: LastRouteKey;
    fixedIndex?: number | null;
  }

  namespace I18n {
    type I18nKey = 'custom-factory';
  }
}

declare namespace Auth {
  type RoleType = keyof typeof import('@/enum')['userRole'];

  interface Route {
    name: Auth.RouteKey;
    roles: Auth.RoleType[];
    children?: Route[];
  }
}

declare namespace Route {
  type253 = RouteKey;

  type RouteKey = LastRouteKey | AuthRoute.RouteKey;

  type LastRouteKey = (
    | 'home'
    | 'dashboard_overview'
    | 'batch_list'
    | 'batch_detail'
    | 'product_list'
    | 'product_detail'
    | 'review_queue'
    | 'review_detail'
    | 'qa_false_positive'
    | 'qa_calibration'
    | 'guard_status'
    | 'product_type_list'
    | 'login'
  );

  interface RouteMeta {
    title: string;
    i18nKey?: App.I18n.I18nKey | string;
    icon?: string;
    roles?: string[];
    keepAlive?: boolean;
    hideInMenu?: boolean;
    hideInTab?: boolean;
    activeMenu?: Route.LasteRouteKey;
    multiTab?: boolean;
    order?: number | null;
    constant?: boolean;
    query?: Record<string, string>;
  }

  type LasteRouteKey = LastRouteKey;

  type Component = 'basic' | 'blank' | 'multi' | 'self';

  interface Route {
    name: RouteKey;
    path: string;
    redirect?: string;
    component?: Component;
    meta: RouteMeta;
    children?: Route[];
  }
}

declare namespace ImportMetaEnv {
  interface Env {
    VITE_BASE_URL: string;
    VITE_APP_TITLE: string;
    VITE_HTTP_PROXY?: string;
    VITE_SERVICE_BASE?: string;
  }
}

interface ImportMeta {
  readonly env: ImportMetaEnv.Env;
}
