<script setup lang="ts">
import { ref } from 'vue';

import { useRoute } from 'vue-router';

import GlobalHeader from '../modules/global-header/index.vue';
import GlobalSider from '../modules/global-sider/index.vue';
import GlobalFooter from '../modules/global-footer/index.vue';

import { useAppStore } from '@/store/modules/app';

defineOptions({ name: 'BaseLayout' });

const app = useAppStore();
const route = useRoute();

const scrollRef = ref<HTMLElement>();
</script>

<template>
  <el-container class="base-layout">
    <el-aside :width="app.siderCollapse ? '64px' : '220px'" class="base-layout__aside">
      <GlobalSider />
    </el-aside>
    <el-container>
      <el-header class="base-layout__header" height="56px">
        <GlobalHeader />
      </el-header>
      <el-main ref="scrollRef" class="base-layout__main">
        <router-view v-slot="{ Component }">
          <transition mode="out-in" name="fade-slide">
            <keep-alive :max="12">
              <component :is="Component" v-if="app.reloadFlag" :key="route.fullPath" />
            </keep-alive>
          </transition>
        </router-view>
      </el-main>
      <GlobalFooter />
    </el-container>
  </el-container>
</template>

<style scoped lang="scss">
.base-layout {
  height: 100vh;

  &__aside {
    overflow: hidden;
    background-color: var(--cf-sider-bg);
    transition: width 0.24s ease;
  }

  &__header {
    display: flex;
    align-items: center;
    padding: 0 16px;
    border-bottom: 1px solid var(--el-border-color-light);
    background-color: #fff;
  }

  &__main {
    padding: 16px;
    background-color: var(--cf-content-bg);
    overflow-y: auto;
  }
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
