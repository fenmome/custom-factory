<script setup lang="ts">
defineOptions({ name: 'GlobalFooter' });

const year = new Date().getFullYear();
const buildTime = import.meta.env.VITE_BUILD_TIME ?? '';
</script>

<template>
  <el-footer class="global-footer" height="36px">
    <span>Custom Factory · 定制商品生产系统 © {{ year }}</span>
    <span v-if="buildTime" class="global-footer__build">构建时间：{{ buildTime }}</span>
  </el-footer>
</template>

<style scoped lang="scss">
.global-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--el-border-color-light);
  background-color: #fff;
  color: var(--el-text-color-secondary);
  font-size: 12px;

  &__build {
    opacity: 0.75;
  }
}
</style>
