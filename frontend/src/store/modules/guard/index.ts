import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { fetchGuardStatus } from '@/service/api/guard';

const LEVEL_META: Record<string, { label: string; tag: 'success' | 'warning' | 'danger' | 'info' }> = {
  GREEN: { label: '正常 GREEN', tag: 'success' },
  YELLOW: { label: '警告 YELLOW', tag: 'warning' },
  RED: { label: '暂停 RED', tag: 'danger' },
  CRITICAL_STOP: { label: '紧急停止', tag: 'danger' }
};

/** 生产保护状态：全局共享（页头展示 + 页面复用）。 */
export const useGuardStore = defineStore('guard', () => {
  const status = ref<Api.Guard.Status | null>(null);
  const loading = ref(false);

  const level = computed(() => status.value?.level ?? 'GREEN');

  const levelLabel = computed(() => LEVEL_META[level.value]?.label ?? level.value);

  const levelTagType = computed(() => LEVEL_META[level.value]?.tag ?? 'info');

  const pauses = computed(() => status.value?.pauses ?? []);

  const rules = computed(() => status.value?.rules ?? {});

  async function reload() {
    loading.value = true;
    try {
      const result = await fetchGuardStatus();
      if (!result.error && result.data) {
        status.value = result.data;
      }
    } finally {
      loading.value = false;
    }
    return status.value;
  }

  return { status, loading, level, levelLabel, levelTagType, pauses, rules, reload };
});
