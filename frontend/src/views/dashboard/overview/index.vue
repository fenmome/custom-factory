<script setup lang="ts">
import { Aim, Box, Files, Goods, Lock, Refresh, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';

import StatCard from '@/components/custom/stat-card.vue';
import { usePolling } from '@sa/hooks';
import { fetchOverview } from '@/service/api/dashboard';
import { evaluateGuard } from '@/service/api/guard';
import { useGuardStore } from '@/store/modules/guard';
import { GUARD_LEVEL_DICT, dictValue, percent } from '@/utils/dict';

defineOptions({ name: 'DashboardOverview' });

const loading = ref(false);
const data = ref<Api.Dashboard.Overview | null>(null);
const guardStore = useGuardStore();

const guard = computed(() => data.value?.guard);
const levelItem = computed(() => dictValue(GUARD_LEVEL_DICT, guard.value?.level, '未知'));

const readyCount = computed(() => data.value?.counts.revisions.READY_FOR_PUBLISH ?? 0);
const productCount = computed(() => data.value?.counts.products ?? 0);
const readyPercent = computed(() => percent(readyCount.value, productCount.value));

const imageTotal = computed(() => Object.values(data.value?.counts.image_jobs ?? {}).reduce((a, b) => a + b, 0));
const imageDone = computed(
  () => (data.value?.counts.image_jobs.ASSET_RECORDED ?? 0) + (data.value?.counts.image_jobs.SETTLED ?? 0)
);

async function load() {
  loading.value = true;
  try {
    const result = await fetchOverview();
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    data.value = result.data;
  } finally {
    loading.value = false;
  }
}

async function runEvaluate() {
  const result = await evaluateGuard();
  if (result.error) {
    ElMessage.error(result.error.msg);
    return;
  }
  ElMessage.success(`评估完成：${result.data?.level ?? ''}`);
  await load();
}

/** 保护阈值项（中文标签 → 资源文件字段）。 */
const RULE_LABELS: Record<string, string> = {
  window: '统计窗口',
  sku_window: 'SKU 滑动窗口',
  startup_skus: '启动期 SKU 数',
  image_window: '图片滑动窗口',
  sku_yellow_min_percent: 'SKU 黄灯阈值下限(%)',
  sku_yellow_max_percent: 'SKU 黄灯阈值上限(%)',
  image_yellow_min_percent: '图片黄灯阈值(%)',
  yellow_required_role_streak: '必需角色黄灯连续数',
  red_required_role_streak: '必需角色红灯连续数',
  red_consecutive_skus: '红灯连续未通过 SKU',
  red_short_window: '红灯短窗口',
  red_short_failures: '红灯短窗口失败数',
  red_long_failures: '红灯长窗口失败数',
  trial_sku_limit: '试运行 SKU 上限',
  trial_idle_minutes: '领取空闲回收(分钟)',
  max_consecutive_executor: '同一执行器连续上限',
  max_open_generations_per_sku: '单 SKU 最大并发'
};

const ruleRows = computed(() => {
  const rules = (guardStore.rules ?? {}) as Record<string, unknown>;
  return Object.entries(rules).map(([key, value]) => ({
    name: RULE_LABELS[key] ?? key,
    value: String(value)
  }));
});

const { tick, running } = usePolling(load, 15_000);

onMounted(() => {
  void tick();
  void guardStore.reload();
});
</script>

<template>
  <div v-loading="loading" class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">生产总览</h2>
        <p class="cf-muted">实时掌握批次进度、图片流水、质检结果与生产保护状态</p>
      </div>
      <el-button-group>
        <el-button :loading="loading" :icon="Refresh" @click="tick">刷新</el-button>
        <el-button type="primary" :loading="running" :icon="Aim" @click="runEvaluate">评估生产保护</el-button>
      </el-button-group>
    </div>

    <el-row :gutter="12">
      <el-col :span="6">
        <StatCard label="批次总数" :value="data?.counts.batches ?? 0" :icon="Files" />
      </el-col>
      <el-col :span="6">
        <StatCard label="SKU 总数" :value="productCount" :icon="Goods" />
      </el-col>
      <el-col :span="6">
        <StatCard
          label="可发布 READY"
          :value="readyCount"
          :icon="View"
          type="success"
          :trend="`占全部 SKU ${readyPercent}%`"
        />
      </el-col>
      <el-col :span="6">
        <StatCard
          label="图片槽位完成"
          :value="`${imageDone}/${imageTotal}`"
          :icon="Box"
          :trend="`完成率 ${percent(imageDone, imageTotal)}%`"
        />
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :span="14">
        <el-card class="cf-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>生产保护</span>
              <el-tag :type="levelItem.type" effect="dark" size="small" round>{{ levelItem.label }}</el-tag>
            </div>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="当前级别">
              {{ guard?.evaluation.level ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="触发规则">
              {{ guard?.evaluation.rule_id ?? '无' }}
            </el-descriptions-item>
            <el-descriptions-item label="说明" :span="2">
              {{ guard?.evaluation.reason ?? '生产正常' }}
            </el-descriptions-item>
            <el-descriptions-item label="活跃领取">
              {{ data?.active_claims ?? 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="暂停数量">
              {{ guard?.pauses.length ?? 0 }}
            </el-descriptions-item>
          </el-descriptions>

          <el-empty v-if="!(guard?.pauses.length ?? 0)" description="当前无暂停" :image-size="60" />
          <el-table v-else :data="guard?.pauses ?? []" size="small" style="margin-top: 12px">
            <el-table-column prop="scope_kind" label="作用域" width="180" />
            <el-table-column prop="state" label="状态" width="120" />
            <el-table-column prop="trigger_rule_id" label="规则" width="100" />
            <el-table-column prop="reason" label="原因" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card class="cf-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Lock /></el-icon> 保护阈值（来自资源文件）</span>
            </div>
          </template>
          <el-table :data="ruleRows" size="small" max-height="300">
            <el-table-column prop="name" label="阈值项" />
            <el-table-column prop="value" label="取值" width="100" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.page-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}
</style>
