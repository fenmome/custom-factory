<script setup lang="ts">
import { Plus, Refresh, Setting } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';

import { createProductType, fetchNextSkuPreview, fetchProductTypes, updateProductType } from '@/service/api/product-type';

defineOptions({ name: 'ProductTypeList' });

const loading = ref(false);
const submitting = ref(false);
const previewing = ref(false);
const rows = ref<Api.ProductType.Item[]>([]);
const dialogVisible = ref(false);

const form = reactive<Api.ProductType.UpsertParams>({
  product_type_code: '',
  display_name: '',
  prefix: '',
  sequence_width: 6,
  is_enabled: true
});

async function load() {
  loading.value = true;
  try {
    const result = await fetchProductTypes();
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    rows.value = result.data?.items ?? [];
  } finally {
    loading.value = false;
  }
}

async function submitCreate() {
  if (!form.product_type_code || !form.display_name || !form.prefix) {
    ElMessage.warning('产品类型编码、显示名、前缀均为必填');
    return;
  }
  submitting.value = true;
  try {
    const result = await createProductType(form);
    if (result.error) {
      ElMessage.error(`${result.error.msg} ${typeof result.error.detail === 'string' ? result.error.detail : ''}`);
      return;
    }
    ElMessage.success('产品类型已创建');
    dialogVisible.value = false;
    await load();
  } finally {
    submitting.value = false;
  }
}

async function toggleEnabled(row: Api.ProductType.Item) {
  await ElMessageBox.confirm(`确认${row.is_enabled ? '停用' : '启用'}该 SKU 规则？`, '操作确认', {
    type: 'warning'
  }).catch(() => undefined);
  const result = await updateProductType(row.product_type_code, {
    sequence_width: row.sequence_width,
    is_enabled: !row.is_enabled
  });
  if (result.error) {
    ElMessage.error(result.error.msg);
    return;
  }
  ElMessage.success('已更新');
  await load();
}

async function previewNext(row: Api.ProductType.Item) {
  previewing.value = true;
  try {
    const result = await fetchNextSkuPreview(row.product_type_code);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success(`下一个可用 SKU：${result.data?.next_sku}`);
  } finally {
    previewing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">
          <el-icon><Setting /></el-icon>
          产品类型 / SKU 规则
        </h2>
        <p class="cf-muted">SKU 结构 = 用户配置前缀 + 补零流水号（不含日期/随机数）；流水号从 1 开始、永不复用</p>
      </div>
      <el-button-group>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="dialogVisible = true">新建产品类型</el-button>
      </el-button-group>
    </div>

    <el-card v-loading="loading" shadow="never" class="cf-card">
      <el-table :data="rows" size="small" border stripe>
        <el-table-column prop="product_type_code" label="类型编码" width="160" />
        <el-table-column prop="display_name" label="显示名" min-width="180" />
        <el-table-column prop="prefix" label="前缀" width="120">
          <template #default="{ row }"><span class="cf-mono">{{ row.prefix }}</span></template>
        </el-table-column>
        <el-table-column prop="sequence_width" label="流水号位数" width="120" align="right" />
        <el-table-column prop="last_sequence" label="当前最大值" width="120" align="right" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
              {{ row.is_enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="previewNext(row as Api.ProductType.Item)">预览下一个</el-button>
            <el-button
              link
              :type="row.is_enabled ? 'danger' : 'success'"
              size="small"
              @click="toggleEnabled(row as Api.ProductType.Item)"
            >
              {{ row.is_enabled ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新建产品类型" width="480px">
      <el-form label-position="top">
        <el-form-item label="产品类型编码">
          <el-input v-model="form.product_type_code" placeholder="如 UV_DTF" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" placeholder="如 定制水晶标" />
        </el-form-item>
        <el-form-item label="前缀">
          <el-input v-model="form.prefix" placeholder="如 DZUVDTF（字母数字，全局唯一）" />
        </el-form-item>
        <el-form-item label="流水号位数">
          <el-input-number v-model="form.sequence_width" :min="1" :max="12" controls-position="right" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
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
