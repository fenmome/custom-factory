<script setup lang="ts">
import { Refresh, Warning } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';

import { fetchFalsePositiveBoard } from '@/service/api/qa';

defineOptions({ name: 'QaFalsePositive' });

const loading = ref(false);
const board = ref<Api.Qa.Board | null>(null);

const falsePassColumns = [
  { prop: 'asset_id', label: '资产 ID', minWidth: 120 },
  { prop: 'human_result', label: '人工判定', width: 100 },
  { prop: 'auto_result', label: '自动结论', width: 100 },
  { prop: 'reason_code', label: '原因码', width: 160 },
  { prop: 'reason_detail', label: '说明', minWidth: 200, showOverflowTooltip: true }
];

async function load() {
  loading.value = true;
  try {
    const result = await fetchFalsePositiveBoard();
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    board.value = result.data;
  } finally {
    loading.value = false;
  }
}

const total = computed(() => (board.value?.false_pass_count ?? 0) + (board.value?.false_fail_count ?? 0));

onMounted(load);
</script>

<template>
  <div class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">
          <el-icon><Warning /></el-icon>
          误判看板
        </h2>
        <p class="cf-muted">
          FALSE_PASS = 人工推翻了自动 FAIL（漏检补回）；FALSE_FAIL = 人工推翻了自动 PASS（自动误杀）。共 {{ total }} 条。
        </p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-card v-loading="loading" shadow="never" class="cf-card">
      <template #header>
        <div class="card-header">
          <span>人工推翻了自动 PASS（自动误杀 FALSE_FAIL）</span>
          <el-tag type="danger" size="small">{{ board?.false_fail_count ?? 0 }}</el-tag>
        </div>
      </template>
      <el-table :data="board?.false_fail ?? []" size="small" border stripe max-height="320">
        <el-table-column type="index" width="50" />
        <el-table-column v-for="col in falsePassColumns" :key="col.prop" v-bind="col">
          <template v-if="col.prop === 'asset_id'" #default="{ row }">
            <span class="cf-mono">{{ row.asset_id?.slice(0, 12) }}…</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-loading="loading" shadow="never" class="cf-card">
      <template #header>
        <div class="card-header">
          <span>人工推翻了自动 FAIL（自动漏检 FALSE_PASS）</span>
          <el-tag type="warning" size="small">{{ board?.false_pass_count ?? 0 }}</el-tag>
        </div>
      </template>
      <el-table :data="board?.false_pass ?? []" size="small" border stripe max-height="320">
        <el-table-column type="index" width="50" />
        <el-table-column v-for="col in falsePassColumns" :key="col.prop" v-bind="col">
          <template v-if="col.prop === 'asset_id'" #default="{ row }">
            <span class="cf-mono">{{ row.asset_id?.slice(0, 12) }}…</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}
</style>
