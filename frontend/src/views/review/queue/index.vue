<script setup lang="ts">
import { Refresh, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { fetchPendingQueue } from '@/service/api/review';
import { REVISION_STATUS_DICT, dictValue } from '@/utils/dict';

defineOptions({ name: 'ReviewQueue' });

const router = useRouter();

const loading = ref(false);
const rows = ref<Api.Review.PendingItem[]>([]);
const total = ref(0);

const query = reactive({ page: 1, pageSize: 20 });

async function load() {
  loading.value = true;
  try {
    const result = await fetchPendingQueue({ page: query.page, pageSize: query.pageSize });
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    rows.value = result.data?.items ?? [];
    total.value = result.data?.total ?? rows.value.length;
  } finally {
    loading.value = false;
  }
}

function openReview(row: Api.Review.PendingItem) {
  router.push({ name: 'review_detail', params: { productId: row.product_id } });
}

onMounted(load);
</script>

<template>
  <div class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">人工复审队列</h2>
        <p class="cf-muted">按 SKU 集合粒度复审（一次 8 张图）；硬技术失败不可人工放行</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-card v-loading="loading" shadow="never" class="cf-card">
      <el-table :data="rows" size="small" border stripe max-height="540">
        <el-table-column label="内部 SKU" min-width="190">
          <template #default="{ row }"><span class="cf-mono">{{ row.internal_sku }}</span></template>
        </el-table-column>
        <el-table-column label="批次请求键" min-width="220">
          <template #default="{ row }"><span class="cf-mono">{{ row.request_key }}</span></template>
        </el-table-column>
        <el-table-column label="修订状态" width="140">
          <template #default="{ row }">
            <el-tag :type="dictValue(REVISION_STATUS_DICT, row.revision_status).type" size="small">
              {{ dictValue(REVISION_STATUS_DICT, row.revision_status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" :icon="View" @click="openReview(row as Api.Review.PendingItem)">开始复审</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next"
        class="table-pagination"
        @current-change="load"
        @size-change="load"
      />
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.page-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
}

.table-pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
