<script setup lang="ts">
import { Aim, Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';

import { fetchCalibration, fetchCalibrationDue } from '@/service/api/qa';
import { fetchProductTypes } from '@/service/api/product-type';

defineOptions({ name: 'QaCalibration' });

const loading = ref(false);
const dueLoading = ref(false);
const report = ref<Api.Qa.Calibration | null>(null);
const dueItems = ref<Array<Record<string, unknown>>>([]);
const productTypes = ref<Api.ProductType.Item[]>([]);
const selectedType = ref('');

const agreement = computed(() => report.value?.agreement_rate ?? 0);

const roleRows = computed(() => report.value?.by_role ?? []);
const reasonRows = computed(() => report.value?.by_reason ?? []);

async function loadTypes() {
  const result = await fetchProductTypes();
  if (!result.error) {
    productTypes.value = result.data?.items ?? [];
    if (!selectedType.value && productTypes.value.length) {
      selectedType.value = productTypes.value[0]!.id;
    }
  }
}

async function loadReport() {
  if (!selectedType.value) return;
  loading.value = true;
  try {
    const result = await fetchCalibration(selectedType.value);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    report.value = result.data;
  } finally {
    loading.value = false;
  }
}

async function loadDue() {
  dueLoading.value = true;
  try {
    const result = await fetchCalibrationDue();
    if (!result.error) dueItems.value = result.data?.items ?? [];
  } finally {
    dueLoading.value = false;
  }
}

watch(selectedType, loadReport);

onMounted(async () => {
  await loadTypes();
  await Promise.all([loadReport(), loadDue()]);
});
</script>

<template>
  <div class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">
          <el-icon><Aim /></el-icon>
          QA 校准
        </h2>
        <p class="cf-muted">校准期 = 每个产品类型前 3 个批次；每批额外抽样最多 20 个自动通过的 SKU 集合</p>
      </div>
      <el-button-group>
        <el-select v-model="selectedType" placeholder="选择产品类型" filterable size="default" style="width: 220px; margin-right: 8px">
          <el-option v-for="item in productTypes" :key="item.id" :label="item.display_name" :value="item.id" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="loadReport">刷新</el-button>
      </el-button-group>
    </div>

    <el-alert
      v-if="dueItems.length"
      type="warning"
      :closable="false"
      show-icon
      title="QA_RULE_REVIEW_DUE"
      :description="`${dueItems.length} 个产品类型已达 ≥3 批次且 ≥100 张人工复审图片，需重新评估质检规则。`"
      style="margin-bottom: 12px"
    />

    <el-row :gutter="12">
      <el-col :span="6">
        <el-card v-loading="loading" shadow="never" class="cf-card">
          <template #header><span>人机一致率</span></template>
          <el-progress type="dashboard" :percentage="Math.min(agreement, 100)" :width="130" />
        </el-card>
      </el-col>
      <el-col :span="18">
        <el-card v-loading="loading" shadow="never" class="cf-card">
          <template #header><span>混淆矩阵</span></template>
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item label="TRUE_PASS">{{ report?.true_pass ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="TRUE_FAIL">{{ report?.true_fail ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="FALSE_PASS">
              <el-tag type="warning" size="small">{{ report?.false_pass ?? 0 }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="FALSE_FAIL">
              <el-tag type="danger" size="small">{{ report?.false_fail ?? 0 }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="校准批次">{{ report?.batch_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="人工复审图片">{{ report?.human_reviewed_images ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="是否到期复核">
              <el-tag :type="report?.review_due ? 'danger' : 'success'" size="small">
                {{ report?.review_due ? '是' : '否' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card v-loading="loading" shadow="never" class="cf-card">
          <template #header><span>按槽位角色统计</span></template>
          <el-table :data="roleRows" size="small" border>
            <el-table-column prop="role" label="角色" />
            <el-table-column prop="agree" label="一致" align="right" />
            <el-table-column prop="disagree" label="不一致" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card v-loading="loading" shadow="never" class="cf-card">
          <template #header><span>按原因码统计</span></template>
          <el-table :data="reasonRows" size="small" border max-height="280">
            <el-table-column prop="reason_code" label="原因码" min-width="150" />
            <el-table-column prop="agree" label="一致" align="right" />
            <el-table-column prop="disagree" label="不一致" align="right" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-loading="dueLoading" shadow="never" class="cf-card">
      <template #header><span>待触发规则复核（QA_RULE_REVIEW_DUE）</span></template>
      <el-table :data="dueItems" size="small" border>
        <el-table-column prop="product_type_id" label="产品类型" min-width="200" />
        <el-table-column prop="batch_count" label="批次数" width="90" align="right" />
        <el-table-column prop="human_reviewed_images" label="人工复审图片" width="130" align="right" />
        <el-table-column prop="agreement_rate" label="一致率(%)" width="110" align="right" />
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
</style>
