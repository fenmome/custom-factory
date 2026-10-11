<script setup lang="ts">
import * as ElementPlusIconsVue from '@element-plus/icons-vue';
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAppStore } from '@/store/modules/app';
import { useRouteStore } from '@/store/modules/route';

defineOptions({ name: 'GlobalSider' });

const app = useAppStore();
const routeStore = useRouteStore();
const router = useRouter();
const route = useRoute();

const menus = computed(() => routeStore.cleanMenus);

const activePath = computed(() => {
  const current = route.name as string;
  const target = menus.value.find(item => item.name === current);
  if (target) return `/${target.path}`;
  const activeMenu = route.meta.activeMenu as string | undefined;
  const parent = menus.value.find(item => item.name === activeMenu);
  return parent ? `/${parent.path}` : route.path;
});

function iconOf(name?: string) {
  if (!name) return null;
  return (ElementPlusIconsVue as Record<string, unknown>)[name] ?? null;
}
</script>

<template>
  <div class="global-sider">
    <div class="global-sider__brand">
      <div class="global-sider__logo">CF</div>
      <span v-show="!app.siderCollapse" class="global-sider__title">定制商品生产系统</span>
    </div>

    <el-menu
      class="global-sider__menu"
      :default-active="activePath"
      :collapse="app.siderCollapse"
      :collapse-transition="false"
      unique-opened
      background-color="transparent"
      text-color="#c7cbd8"
      active-text-color="#ffffff"
    >
      <el-menu-item v-for="item in menus" :key="item.name" :index="`/${item.path}`" @click="router.push({ name: item.name })">
        <el-icon v-if="iconOf(item.meta.icon)"><component :is="iconOf(item.meta.icon)" /></el-icon>
        <template #title>{{ item.meta.title }}</template>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<style scoped lang="scss">
.global-sider {
  display: flex;
  height: 100%;
  flex-direction: column;

  &__brand {
    display: flex;
    height: 56px;
    align-items: center;
    gap: 10px;
    padding: 0 16px;
    color: #fff;
  }

  &__logo {
    display: flex;
    width: 28px;
    height: 28px;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border-radius: 8px;
    background: linear-gradient(135deg, #4f6ef7, #7b5cff);
    font-size: 13px;
    font-weight: 700;
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
  }

  &__menu {
    flex: 1;
    border-right: none;
    overflow-x: hidden;
  }

  :deep(.el-menu-item.is-active) {
    background-color: rgba(79, 110, 247, 0.18) !important;
  }
}
</style>
