import './assets/css/reset.css';
import './styles/css/global.css';

import { createApp } from 'vue';

import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import zhCn from 'element-plus/es/locale/lang/zh-cn';

import App from './App.vue';

import { setupStore } from './store';
import { router, setupRouter } from './router';

import { setupDirectives } from './directives';
import { useGuardStore } from './store/modules/guard';

async function setupApp() {
  const app = createApp(App);

  setupStore(app);
  await setupRouter(app);

  app.use(ElementPlus, { locale: zhCn });
  setupDirectives(app);

  await router.isReady();

  app.mount('#app');

  // 登录后加载生产保护状态（失败静默）
  const guard = useGuardStore();
  void guard.reload().catch(() => undefined);
}

setupApp();
