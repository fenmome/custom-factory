<script setup lang="ts">
import { Files, Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { fetchBatchDetail, fetchBatchProgress, prepareBatch } from '@/service/api/batch';
import { REVISION_STATUS_DICT, dictValue, percent } from '@/utils/dict';

defineOptions({ name: 'BatchDetail' });

const route = useRoute();
const router = useRouter();

const batchId = computed(() => route.params.batchId as string);

const loading = ref(false);
const preparing = ref(false);
const detail = ref<Api.Batch.Detail | null>(null);
const progress = ref<Api.Batch.Progress | null>(null);

async function load() {
  loading.value = true;
  try {
    const [d, p] = await Promise.all([fetchBatchDetail(batchId.value), fetchBatchProgress(batchId.value)]);
    if (d.error) ElMessage.error(d.error.msg);
    else detail.value = d.data;
    if (!p.error) progress.value = p.data;
  } finally {
    loading.value = false;
  }
}

async function retryPrepare() {
  preparing.value = true;
  try {
    const result = await prepareBatch(batchId.value);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success('批次生产准备已完成');
    await load();
  } finally {
    preparing.value = false;
  }
}

function openProduct(row: Api.Batch.Item) {
  router.push({ name: 'product_detail', params: { productId: row.product_id } });
}

const imagePercent = computed(() => progress.value?.image_percent ?? 0);

onMounted(load);
</script>

<template>
  <div v-loading="loading" class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">批次详情</h2>
        <p class="cf-muted cf-mono">{{ batchId }}</p>
      </div>
      <el-button-group>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Files" :loading="preparing" @click="retryPrepare">重跑生产准备</el-button>
      </el-button-group>
    </div>

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card shadow="never" class="cf-card">
          <template #header><span>批次信息</span></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="请求键">{{ detail?.batch.request_key ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="请求数量">{{ detail?.batch.requested_quantity ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="已分配 SKU">{{ detail?.items.length ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="控制状态">{{ detail?.batch.control_state ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="图片路线">
              {{ detail?.batch.image_generation_route ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="输入快照哈希">
              <span class="cf-mono">{{ detail?.batch.input_snapshot_hash ?? '-' }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never" class="cf-card">
          <template #header><span>图片进度</span></template>
          <el-progress :percentage="imagePercent" :stroke-width="14" text-inside />
          <p class="cf-muted" style="margin: 10px 0 0">
            已完成 {{ progress?.image_done ?? 0 }} / 计划 {{ progress?.image_total ?? 0 }} 张
          </p>
          <el-descriptions :column="2" border size="small" style="margin-top: 12px">
            <el-descriptions-item v-for="(count, status) in progress?.by_status ?? {}" :key="status" :label="String(status)">
              {{ count }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="cf-card">
      <template #header><span>SKU 明细</span></template>
      <el-table :data="detail?.items ?? []" size="small" border stripe max-height="440">
        <el-table-column prop="internal_sku" label="内部 SKU" width="180">
          <template #default="{ row }"><span class="cf-mono">{{ row.internal_sku }}</span></template>
        </el-table-column>
        <el-table-column label="修订状态" width="140">
          <template #default="{ row }">
            <el-tag :type="dictValue(REVISION_STATUS_DICT, row.revision_status).type" size="small">
              {{ dictValue(REVISION_STATUS_DICT, row.revision_status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="图片进度" min-width="220">
          <template #default="{ row }">
            <el-progress
              :percentage="percent(row.image_progress.asset_recorded, row.image_progress.total)"
              :stroke-width="10"
            />
            <span class="cf-muted">{{ row.image_progress.asset_recorded }}/{{ row.image_progress.total }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openProduct(row as Api.Batch.Item)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.page-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
}
</style>
