<script setup lang="ts">
import { ElConfigProvider } from 'element-plus';
import zhCn from 'element-plus/es/locale/lang/zh-cn';

defineOptions({ name: 'App' });
</script>

<template>
  <ElConfigProvider :locale="zhCn" size="default">
    <router-view />
  </ElConfigProvider>
</template>
