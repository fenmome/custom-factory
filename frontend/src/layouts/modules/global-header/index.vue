<script setup lang="ts">
import { Expand, Fold, Lock, Refresh, SwitchButton } from '@element-plus/icons-vue';
import { ElMessageBox } from 'element-plus';

import { useRouter } from 'vue-router';

import { useAppStore } from '@/store/modules/app';
import { useAuthStore } from '@/store/modules/auth';
import { useGuardStore } from '@/store/modules/guard';

defineOptions({ name: 'GlobalHeader' });

const app = useAppStore();
const auth = useAuthStore();
const guard = useGuardStore();
const router = useRouter();

async function logout() {
  await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' });
  auth.reset();
  router.push({ name: 'login' });
}
</script>

<template>
  <div class="global-header">
    <el-icon class="global-header__fold" :size="20" @click="app.toggleSiderCollapse()">
      <Fold v-if="!app.siderCollapse" />
      <Expand v-else />
    </el-icon>

    <el-breadcrumb separator="/" class="global-header__crumb">
      <el-breadcrumb-item :to="{ path: '/dashboard/overview' }">首页</el-breadcrumb-item>
      <el-breadcrumb-item>{{ (($route.meta.title as string) ?? '') }}</el-breadcrumb-item>
    </el-breadcrumb>

    <div class="global-header__right">
      <el-tag :type="guard.levelTagType" effect="dark" size="small" round>
        <el-icon><Lock /></el-icon>
        生产保护：{{ guard.levelLabel }}
      </el-tag>

      <el-tooltip content="刷新" placement="bottom">
        <el-icon :size="18" @click="app.reloadPage()"><Refresh /></el-icon>
      </el-tooltip>

      <el-dropdown trigger="click">
        <span class="global-header__user">
          <el-avatar :size="26">{{ auth.userInfo.display_name?.slice(0, 1) || 'U' }}</el-avatar>
          <span class="global-header__name">{{ auth.userInfo.display_name }}</span>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>
              {{ auth.userInfo.email }}
            </el-dropdown-item>
            <el-dropdown-item divided @click="logout">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style scoped lang="scss">
.global-header {
  display: flex;
  width: 100%;
  align-items: center;

  &__fold {
    margin-right: 14px;
    cursor: pointer;
    color: var(--el-text-color-regular);
  }

  &__crumb {
    flex: 1;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  &__user {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    outline: none;
  }

  &__name {
    font-size: 13px;
    color: var(--el-text-color-primary);
  }
}
</style>
