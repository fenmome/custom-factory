declare global {
  const BUILD_TIME: string;

  interface Window {
    /** 全局加载提示的显隐控制 */
    $loadingBar?: {
      start: () => void;
      finish: () => void;
      error: () => void;
    };
  }

  namespace App {
    namespace Service {
      interface Response<T = any> {
        code: number;
        message: string;
        data: T;
        detail?: unknown;
      }

      type Flat<T = any> = { data: T; error: null } | { data: null; error: { type: 'fail'; code: number; msg: string; detail?: unknown } };

      type RequestResult<T = any> = Promise<Flat<T>>;
    }
  }
}

export {};
