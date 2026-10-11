<script setup lang="ts">
import { Files, Plus, Refresh } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { createBatch, fetchBatchList } from '@/service/api/batch';
import { requestKey, uuidV4 } from '@/utils/uuid';

defineOptions({ name: 'BatchList' });

const router = useRouter();

const loading = ref(false);
const submitting = ref(false);
const rows = ref<Api.Batch.Summary[]>([]);
const total = ref(0);

const query = reactive({ page: 1, pageSize: 20 });
const dialogVisible = ref(false);

const form = reactive({
  quantity: 10,
  style_code: '',
  image_generation_route: 'CODEX' as 'API' | 'CODEX'
});

const MAX_QUANTITY = 500;

const buttonDisabled = computed(() => submitting.value);

async function load() {
  loading.value = true;
  try {
    const result = await fetchBatchList({ page: query.page, pageSize: query.pageSize });
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

async function submitCreate() {
  if (form.quantity < 1 || form.quantity > MAX_QUANTITY) {
    ElMessage.error(`数量必须在 1 ~ ${MAX_QUANTITY} 之间`);
    return;
  }

  await ElMessageBox.confirm(`确认创建 ${form.quantity} 个 SKU 的批次并立即原子分配？`, '创建批次', {
    type: 'warning'
  }).catch(() => undefined);

  submitting.value = true;
  try {
    const result = await createBatch({
      operation_key: uuidV4(),
      request_key: requestKey('batch'),
      quantity: form.quantity,
      image_generation_route: form.image_generation_route,
      style_code: form.style_code || null
    });
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success('批次已创建并完成 SKU 分配');
    dialogVisible.value = false;
    await load();
  } finally {
    submitting.value = false;
  }
}

function openDetail(row: Api.Batch.Summary) {
  router.push({ name: 'batch_detail', params: { batchId: row.id } });
}

onMounted(load);
</script>

<template>
  <div class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">批次管理</h2>
        <p class="cf-muted">一个 SKU = 一个商品；批次创建时原子分配永久流水号</p>
      </div>
      <el-button-group>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="dialogVisible = true">创建批次</el-button>
      </el-button-group>
    </div>

    <el-card v-loading="loading" shadow="never" class="cf-card">
      <el-table :data="rows" size="small" border stripe>
        <el-empty slot="empty" description="暂无批次" />
        <el-table-column label="批次 ID" min-width="150">
          <template #default="{ row }">
            <span class="cf-mono">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="requested_quantity" label="数量" width="80" align="right" />
        <el-table-column prop="image_generation_route" label="图片路线" width="100" />
        <el-table-column prop="control_state" label="控制状态" width="100" />
        <el-table-column prop="usage_code" label="用途" width="150" />
        <el-table-column label="输入快照" min-width="130">
          <template #default="{ row }">
            <el-tooltip :content="row.input_snapshot_hash" placement="top">
              <span class="cf-mono">{{ row.input_snapshot_hash.slice(0, 12) }}…</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="准备状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.prepared_at ? 'success' : 'info'" size="small">
              {{ row.prepared_at ? '已准备' : '未准备' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row as Api.Batch.Summary)">详情</el-button>
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

    <el-dialog v-model="dialogVisible" title="创建批次" width="460px">
      <el-form label-position="top">
        <el-form-item label="生产数量">
          <el-input-number v-model="form.quantity" :min="1" :max="MAX_QUANTITY" controls-position="right" />
          <span class="cf-muted" style="margin-left: 8px">单批次上限 {{ MAX_QUANTITY }}</span>
        </el-form-item>
        <el-form-item label="图片路线">
          <el-radio-group v-model="form.image_generation_route">
            <el-radio value="CODEX">Codex 手工产出</el-radio>
            <el-radio value="API">API 自动产出</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="风格编码（可选）">
          <el-input v-model="form.style_code" placeholder="留空则使用默认" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="buttonDisabled" :loading="submitting" @click="submitCreate">
          确认创建
        </el-button>
      </template>
    </el-dialog>
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
