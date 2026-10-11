<script setup lang="ts">
import { computed } from 'vue';

import { QA_RESULT_DICT, QA_KIND_DICT, dictValue } from '@/utils/dict';

defineOptions({ name: 'QaResultTag' });

const props = withDefaults(
  defineProps<{
    result?: string | null;
    kind?: string | null;
    showKind?: boolean;
    reasonCode?: string | null;
    size?: 'small' | 'default' | 'large';
  }>(),
  { showKind: false, size: 'small' }
);

const item = computed(() => dictValue(QA_RESULT_DICT, props.result, '未质检'));
</script>

<template>
  <span class="qa-result-tag">
    <el-tag :type="item.type" :size="size" effect="light">{{ item.label }}</el-tag>
    <el-tag v-if="showKind && kind" size="small" effect="plain" type="info">
      {{ QA_KIND_DICT[kind] ?? kind }}
    </el-tag>
    <el-tooltip v-if="reasonCode" :content="reasonCode" placement="top">
      <span class="qa-result-tag__reason cf-mono">{{ reasonCode }}</span>
    </el-tooltip>
  </span>
</template>

<style scoped lang="scss">
.qa-result-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  &__reason {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--el-text-color-secondary);
  }
}
</style>
