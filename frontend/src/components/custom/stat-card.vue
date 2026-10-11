<script setup lang="ts">
defineOptions({ name: 'StatCard' });

import type { Component } from 'vue';

withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    icon?: string | Component;
    trend?: string;
    type?: 'default' | 'success' | 'warning' | 'danger';
  }>(),
  { type: 'default' }
);
</script>

<template>
  <el-card class="stat-card" shadow="never">
    <div class="stat-card__inner">
      <div class="stat-card__meta">
        <span class="stat-card__label">{{ label }}</span>
        <strong class="stat-card__value" :class="`is-${type}`">{{ value }}</strong>
        <span v-if="trend" class="stat-card__trend cf-muted">{{ trend }}</span>
      </div>
      <div class="stat-card__icon">
        <slot name="icon">
          <el-icon><component :is="icon" /></el-icon>
        </slot>
      </div>
    </div>
  </el-card>
</template>

<style scoped lang="scss">
.stat-card {
  border-radius: var(--cf-card-radius);

  &__inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  &__label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__value {
    font-size: 24px;
    font-weight: 600;
    line-height: 1.2;

    &.is-success {
      color: var(--el-color-success);
    }
    &.is-warning {
      color: var(--el-color-warning);
    }
    &.is-danger {
      color: var(--el-color-danger);
    }
  }

  &__icon {
    display: flex;
    width: 40px;
    height: 40px;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    background-color: var(--el-fill-color-light);
    color: var(--el-color-primary);
    font-size: 20px;
  }
}
</style>
