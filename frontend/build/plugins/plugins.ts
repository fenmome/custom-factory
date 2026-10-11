import type { PluginOption } from 'vite';
import vue from '@vitejs/plugin-vue';

export function createVitePlugins(_viteEnv: ImportMetaEnv, buildTime: string): PluginOption[] {
  const plugins: PluginOption[] = [
    vue({
      script: {
        defineModel: true,
        propsDestructure: true
      }
    })
  ];

  // 生产环境可选 gzip 压缩（依赖缺失时自动跳过）
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const compression = require('vite-plugin-compression');
    const plugin = compression.default ? compression.default({ verbose: false, disable: false, threshold: 10240, algorithm: 'gzip', ext: '.gz' }) : compression({ verbose: false });
    plugins.push(plugin);
  } catch {
    // ignore
  }

  plugins.push({
    name: 'html-inject-build-time',
    transformIndexHtml(html) {
      return html.replace('__BUILD_TIME__', buildTime);
    }
  });

  return plugins;
}
