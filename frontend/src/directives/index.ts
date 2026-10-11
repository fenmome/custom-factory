import type { App } from 'vue';

/** 注册自定义指令。 */
export function setupDirectives(app: App) {
  app.directive('loading-auto', {
    mounted(el) {
      el.setAttribute('element-loading-background', 'rgba(255, 255, 255, 0.7)');
    }
  });
}
