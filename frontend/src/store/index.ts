import type { App } from 'vue';

import { createPinia } from 'pinia';

import { pinia } from './subscribe';

export function setupStore(app: App) {
  app.use(createPinia());
  void pinia;
}

export * from './modules';
