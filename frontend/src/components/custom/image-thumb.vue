<script setup lang="ts">
import { Picture } from '@element-plus/icons-vue';
import { computed } from 'vue';

import { localStg } from '@sa/utils';
import { STORAGE_KEYS } from '@/service/request';

defineOptions({ name: 'ImageThumb' });

const props = withDefaults(
  defineProps<{
    assetId?: string | null;
    slot: number;
    size?: number;
    alt?: string;
    preview?: boolean;
  }>(),
  { size: 120, preview: true }
);

const src = computed(() => {
  if (!props.assetId) return '';
  const token = localStg.get<string>(STORAGE_KEYS.token) ?? '';
  return `/api/v1/images/assets/${props.assetId}/raw?token=${encodeURIComponent(token)}`;
});

const previewList = computed(() => (src.value ? [src.value] : []));
</script>

<template>
  <div class="image-thumb" :style="{ width: `${size}px`, height: `${size}px` }">
    <el-image
      v-if="src"
      :src="src"
      :preview-src-list="preview ? previewList : []"
      :initial-index="0"
      fit="contain"
      loading="lazy"
      preview-teleported
    >
      <template #error>
        <div class="image-thumb__error"><el-icon><Picture /></el-icon></div>
      </template>
    </el-image>
    <div v-else class="image-thumb__empty">
      <el-icon><Picture /></el-icon>
      <span>槽位 {{ slot }} 无图</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.image-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  overflow: hidden;
  background-color: #f6f7f9;

  :deep(.el-image) {
    width: 100%;
    height: 100%;
  }

  &__empty,
  &__error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
}
</style>
