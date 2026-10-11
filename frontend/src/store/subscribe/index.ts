import { createPinia } from 'pinia';

export const pinia = createPinia();

/** 订阅 store 变更写回本地存储（当前仅保留骨架）。 */
export function subscribeStore() {
  return pinia;
}
