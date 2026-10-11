<script setup lang="ts">
import { Goods, Refresh, Search } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { fetchBatchList } from '@/service/api/batch';
import { fetchProductList } from '@/service/api/product';
import { REVISION_STATUS_DICT, dictValue } from '@/utils/dict';

defineOptions({ name: 'ProductList' });

const router = useRouter();

const loading = ref(false);
const rows = ref<Api.Product.ListItem[]>([]);
const total = ref(0);
const batchOptions = ref<Array<{ id: string; label: string }>>([]);

const query = reactive({ page: 1, pageSize: 20, batchId: '', keyword: '' });

const filtered = ref<Api.Product.ListItem[]>([]);

async function load() {
  loading.value = true;
  try {
    const result = await fetchProductList({
      batchId: query.batchId || undefined,
      page: query.page,
      pageSize: query.pageSize
    });
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    rows.value = result.data?.items ?? [];
    total.value = result.data?.total ?? rows.value.length;
    applyFilter();
  } finally {
    loading.value = false;
  }
}

async function loadBatches() {
  const result = await fetchBatchList({ page: 1, pageSize: 100 });
  if (!result.error) {
    batchOptions.value = (result.data?.items ?? []).map(item => ({ id: item.id, label: item.id.slice(0, 8) }));
  }
}

function applyFilter() {
  const kw = query.keyword.trim().toLowerCase();
  filtered.value = kw
    ? rows.value.filter(row => row.internal_sku.toLowerCase().includes(kw))
    : rows.value;
}

function openDetail(row: Api.Product.ListItem) {
  router.push({ name: 'product_detail', params: { productId: row.product_id } });
}

onMounted(() => {
  void loadBatches();
  void load();
});
</script>

<template>
  <div class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">SKU 管理</h2>
        <p class="cf-muted">内部流水号（含前缀）即 TCRP MMK SKU，永久保留不可修改</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-card shadow="never" class="cf-card">
      <el-form :inline="true" size="small" class="filter-form">
        <el-form-item label="批次">
          <el-select v-model="query.batchId" clearable placeholder="全部批次" filterable style="width: 220px">
            <el-option v-for="item in batchOptions" :key="item.id" :label="item.label" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="SKU">
          <el-input v-model="query.keyword" :prefix-icon="Search" placeholder="按流水号搜索" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="filtered" size="small" border stripe max-height="520">
        <el-table-column label="内部 SKU" min-width="180">
          <template #default="{ row }"><span class="cf-mono">{{ row.internal_sku }}</span></template>
        </el-table-column>
        <el-table-column label="批次" min-width="120">
          <template #default="{ row }"><span class="cf-mono">{{ row.batch_id.slice(0, 8) }}…</span></template>
        </el-table-column>
        <el-table-column label="修订状态" width="140">
          <template #default="{ row }">
            <el-tag :type="dictValue(REVISION_STATUS_DICT, row.revision_status).type" size="small">
              {{ dictValue(REVISION_STATUS_DICT, row.revision_status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="state" label="商品状态" width="100" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row as Api.Product.ListItem)">详情</el-button>
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

.filter-form {
  margin-bottom: 6px;
}

.table-pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
