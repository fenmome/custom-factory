import { createVitePlugins } from './plugins';

interface ViteOptions {
  sourcemap?: boolean;
}

export function setupVitePlugins(viteEnv: ImportMetaEnv, buildTime: string) {
  return createVitePlugins(viteEnv, buildTime);
}

export { createVitePlugins };
export type { ViteOptions };
