/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 构建注入的时间戳，仅用于页脚展示。 */
  readonly VITE_BUILD_TIME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue';

  const component: DefineComponent<{}, {}, any>;
  export default component;
}

declare module 'virtual:svg-icons-names' {
  const names: string[];
  export default names;
}
