<script setup lang="ts">
import { Aim, Lock, Refresh, VideoPause } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, ref } from 'vue';

import { criticalStop, dismissPause, evaluateGuard, fetchGuardStatus, reportTrialResult, startTrial } from '@/service/api/guard';
import { GUARD_LEVEL_DICT, GUARD_SCOPE_DICT, PAUSE_STATE_DICT, dictValue } from '@/utils/dict';

defineOptions({ name: 'GuardStatus' });

const loading = ref(false);
const evaluating = ref(false);
const acting = ref(false);
const status = ref<Api.Guard.Status | null>(null);

const levelItem = computed(() => dictValue(GUARD_LEVEL_DICT, status.value?.level, '未知'));
const pauses = computed(() => status.value?.pauses ?? []);

async function load() {
  loading.value = true;
  try {
    const result = await fetchGuardStatus();
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    status.value = result.data;
  } finally {
    loading.value = false;
  }
}

async function onEvaluate() {
  evaluating.value = true;
  try {
    const result = await evaluateGuard();
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success(`评估完成：${result.data?.level ?? ''}`);
    await load();
  } finally {
    evaluating.value = false;
  }
}

async function onCriticalStop() {
  await ElMessageBox.confirm('紧急停止将立即暂停整个工作空间的新领取，确认继续？', 'CRITICAL_STOP', {
    type: 'error'
  }).catch(() => undefined);
  acting.value = true;
  try {
    const result = await criticalStop('手动紧急停止');
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success('已触发紧急停止');
    await load();
  } finally {
    acting.value = false;
  }
}

async function onStartTrial(row: Api.Guard.PauseBrief) {
  acting.value = true;
  try {
    const result = await startTrial(row.id);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success(`已开启试运行，允许 ${row.trial_sku_limit} 个 SKU`);
    await load();
  } finally {
    acting.value = false;
  }
}

async function onTrialResult(row: Api.Guard.PauseBrief, pass: boolean) {
  acting.value = true;
  try {
    const result = await reportTrialResult(row.id, pass ? 'PASS' : 'FAIL');
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success(`上报完成，当前状态 ${result.data?.state}`);
    await load();
  } finally {
    acting.value = false;
  }
}

async function onDismiss(row: Api.Guard.PauseBrief) {
  await ElMessageBox.confirm('确认撤销该暂停？请确认根因已消除。', '撤销暂停', { type: 'warning' }).catch(
    () => undefined
  );
  acting.value = true;
  try {
    const result = await dismissPause(row.id);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success('暂停已撤销');
    await load();
  } finally {
    acting.value = false;
  }
}

function trialPercent(row: Api.Guard.PauseBrief): number {
  if (!row.trial_sku_limit) return 0;
  return Math.round((row.trial_completed_count / row.trial_sku_limit) * 100);
}

function pauseStateItem(state: string) {
  return dictValue(PAUSE_STATE_DICT, state, state);
}

onMounted(load);
</script>

<template>
  <div class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">
          <el-icon><Lock /></el-icon>
          生产保护
        </h2>
        <p class="cf-muted">三色状态：GREEN 正常 / YELLOW 警告不降速 / RED 暂停 / CRITICAL_STOP 紧急停止</p>
      </div>
      <el-button-group>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button :icon="Aim" :loading="evaluating" @click="onEvaluate">立即评估</el-button>
        <el-button type="danger" :icon="VideoPause" :loading="acting" @click="onCriticalStop">紧急停止</el-button>
      </el-button-group>
    </div>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-card v-loading="loading" shadow="never" class="cf-card">
          <template #header><span>当前状态</span></template>
          <div class="level">
            <el-tag :type="levelItem.type" effect="dark" size="large" round>{{ levelItem.label }}</el-tag>
          </div>
          <el-descriptions :column="1" border size="small" style="margin-top: 12px">
            <el-descriptions-item label="触发规则">{{ status?.evaluation.rule_id ?? '无' }}</el-descriptions-item>
            <el-descriptions-item label="说明">{{ status?.evaluation.reason ?? '生产正常' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card v-loading="loading" shadow="never" class="cf-card">
          <template #header><span>评估指标</span></template>
          <el-table
            :data="Object.entries(status?.evaluation.metrics ?? {}).map(([key, value]) => ({ key, value }))"
            size="small"
            border
            max-height="260"
          >
            <el-table-column prop="key" label="指标" min-width="200" />
            <el-table-column prop="value" label="取值" min-width="200">
              <template #default="{ row }">{{ JSON.stringify(row.value) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-loading="loading" shadow="never" class="cf-card">
      <template #header><span>暂停控制</span></template>
      <el-table :data="pauses" size="small" border stripe>
        <el-empty slot="empty" description="当前无暂停" />
        <el-table-column label="作用域" width="180">
          <template #default="{ row }">{{ GUARD_SCOPE_DICT[row.scope_kind] ?? row.scope_kind }}</template>
        </el-table-column>
        <el-table-column label="目标" min-width="160">
          <template #default="{ row }"><span class="cf-mono">{{ JSON.stringify(row.target) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="pauseStateItem(row.state).type" size="small">{{ pauseStateItem(row.state).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trigger_rule_id" label="规则" width="90" />
        <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
        <el-table-column label="试运行" width="180">
          <template #default="{ row }">
            <el-progress
              v-if="row.state === 'TRIAL_RUNNING'"
              :percentage="trialPercent(row as Api.Guard.PauseBrief)"
              :stroke-width="10"
              :format="() => `${(row as Api.Guard.PauseBrief).trial_completed_count}/${(row as Api.Guard.PauseBrief).trial_sku_limit}`"
            />
            <span v-else class="cf-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.state === 'PAUSED'" link type="warning" size="small" @click="onStartTrial(row as Api.Guard.PauseBrief)">
              开始试运行
            </el-button>
            <template v-else-if="row.state === 'TRIAL_RUNNING'">
              <el-button link type="success" size="small" @click="onTrialResult(row as Api.Guard.PauseBrief, true)">通过</el-button>
              <el-button link type="danger" size="small" @click="onTrialResult(row as Api.Guard.PauseBrief, false)">失败</el-button>
            </template>
            <el-button link type="primary" size="small" @click="onDismiss(row as Api.Guard.PauseBrief)">撤销</el-button>
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

.level {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px 0;
}
</style>
