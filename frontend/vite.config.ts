import { fileURLToPath, URL } from 'node:url';

import dayjs from 'dayjs';
import { defineConfig, loadEnv } from 'vite';

import { setupVitePlugins } from './build/plugins';

export default defineConfig(configEnv => {
  const viteEnv = loadEnv(configEnv.mode, process.cwd()) as unknown as ImportMetaEnv;

  // 后端代理目标：容器内通过 VITE_PROXY_TARGET 指向 backend 服务，本地默认 8000 端口
  const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000';

  const buildTime = dayjs().format('YYYY-MM-DD HH:mm:ss');

  return {
    base: viteEnv.VITE_BASE_URL,
    resolve: {
      alias: {
        '~': fileURLToPath(new URL('./', import.meta.url)),
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        'vue': fileURLToPath(new URL('./node_modules/vue/dist/vue.esm-browser.prod.js', import.meta.url)),
        '@sa/utils': fileURLToPath(new URL('./packages/utils/src', import.meta.url)),
        '@sa/hooks': fileURLToPath(new URL('./packages/hooks/src', import.meta.url)),
        '@sa/axios': fileURLToPath(new URL('./packages/axios/src', import.meta.url)),
        '@sa/materials': fileURLToPath(new URL('./packages/materials/src', import.meta.url))
      }
    },
    plugins: setupVitePlugins(viteEnv, buildTime),
    define: {
      BUILD_TIME: JSON.stringify(buildTime)
    },
    css: {
      preprocessorOptions: {
        scss: {
          api: 'modern-compiler',
          additionalData: `@use "@/styles/scss/global.scss" as *;`
        }
      }
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      open: false,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true
        },
        '/internal': {
          target: proxyTarget,
          changeOrigin: true
        }
      },
      warmup: {
        clientFiles: ['./index.html', './src/{layouts,views,router,store}/*']
      }
    },
    preview: {
      port: 9725
    },
    build: {
      reportCompressedSize: false,
      sourcemap: viteEnv.VITE_SOURCE_MAP === 'Y',
      commonjsOptions: {
        ignoreTryCatch: true
      },
      chunkSizeWarningLimit: 1500,
      rollupOptions: {
        output: {
          chunkFileNames: 'js/[name]-[hash].js',
          entryFileNames: 'js/[name]-[hash].js',
          assetFileNames: '[ext]/[name]-[hash].[ext]'
        }
      }
    }
  };
});
