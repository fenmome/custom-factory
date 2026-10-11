<script setup lang="ts">
import { Check, DataBoard, Refresh, View } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import ImageThumb from '@/components/custom/image-thumb.vue';
import QaResultTag from '@/components/custom/qa-result-tag.vue';
import { buildProductData, fetchProductDetail, markReady, summariseQa } from '@/service/api/product';
import {
  INTEGRITY_DICT,
  IMAGE_JOB_STATE_DICT,
  REVISION_STATUS_DICT,
  SLOT_ROLE_DICT,
  dictValue
} from '@/utils/dict';
import { uuidV4 } from '@/utils/uuid';

defineOptions({ name: 'ProductDetail' });

const route = useRoute();
const router = useRouter();

const productId = computed(() => route.params.productId as string);

const loading = ref(false);
const acting = ref(false);
const detail = ref<Api.Product.Detail | null>(null);

async function load() {
  loading.value = true;
  try {
    const result = await fetchProductDetail(productId.value);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    detail.value = result.data;
  } finally {
    loading.value = false;
  }
}

async function onSummarise() {
  acting.value = true;
  try {
    const result = await summariseQa(productId.value);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success(`修订级 QA：${result.data?.result}`);
    await load();
  } finally {
    acting.value = false;
  }
}

async function onBuildData() {
  acting.value = true;
  try {
    const result = await buildProductData(productId.value);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    ElMessage.success('商品属性数据已生成');
  } finally {
    acting.value = false;
  }
}

async function onMarkReady() {
  const gate = detail.value?.ready_gate;
  if (!gate?.ready) {
    ElMessage.warning(`READY 门禁未通过：${gate?.blockers.join('、') ?? ''}`);
    return;
  }
  await ElMessageBox.confirm('确认将该 SKU 标记为 READY_FOR_PUBLISH？该操作不可回退。', 'READY 判定', {
    type: 'warning'
  }).catch(() => undefined);

  acting.value = true;
  try {
    const result = await markReady(productId.value, uuidV4());
    if (result.error) {
      ElMessage.error(`${result.error.msg} ${typeof result.error.detail === 'string' ? result.error.detail : ''}`);
      return;
    }
    ElMessage.success('已标记为 READY_FOR_PUBLISH');
    await load();
  } finally {
    acting.value = false;
  }
}

function goReview() {
  router.push({ name: 'review_detail', params: { productId: productId.value } });
}

const gate = computed(() => detail.value?.ready_gate);

onMounted(load);
</script>

<template>
  <div v-loading="loading" class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">
          <el-icon><DataBoard /></el-icon>
          {{ detail?.internal_sku ?? 'SKU 详情' }}
        </h2>
        <p v-if="detail?.title_text" class="cf-muted">{{ detail.title_text }}</p>
      </div>
      <el-button-group>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button :icon="View" @click="goReview">去复审</el-button>
        <el-button :loading="acting" @click="onSummarise">汇总 QA</el-button>
        <el-button :loading="acting" @click="onBuildData">生成商品属性</el-button>
        <el-button type="success" :icon="Check" :loading="acting" @click="onMarkReady">标记 READY</el-button>
      </el-button-group>
    </div>

    <el-row :gutter="12">
      <el-col :span="14">
        <el-card shadow="never" class="cf-card">
          <template #header><span>八槽位图片</span></template>
          <div class="cf-image-grid">
            <div v-for="item in detail?.images ?? []" :key="item.slot" class="cf-image-card">
              <div class="cf-image-card__thumb">
                <ImageThumb :asset-id="item.asset_id" :slot="item.slot" :size="150" />
              </div>
              <div class="cf-image-card__body">
                <div class="card-row">
                  <span class="slot-badge">{{ item.slot }}</span>
                  <span>{{ SLOT_ROLE_DICT[item.role] ?? item.role }}</span>
                  <el-tag v-if="item.is_required" size="small" type="warning" effect="plain">必需</el-tag>
                </div>
                <div class="card-row">
                  <el-tag :type="dictValue(IMAGE_JOB_STATE_DICT, item.job_state).type" size="small">
                    {{ dictValue(IMAGE_JOB_STATE_DICT, item.job_state).label }}
                  </el-tag>
                  <el-tag :type="dictValue(INTEGRITY_DICT, item.integrity_state).type" size="small" effect="plain">
                    字节{{ dictValue(INTEGRITY_DICT, item.integrity_state).label }}
                  </el-tag>
                </div>
                <div class="card-row">
                  <span class="cf-muted">技术</span>
                  <QaResultTag :result="item.technical?.result" :reason-code="item.technical?.reason_code" />
                </div>
                <div class="card-row">
                  <span class="cf-muted">语义</span>
                  <QaResultTag :result="item.semantic?.result" :reason-code="item.semantic?.reason_code" />
                </div>
                <div class="card-row">
                  <span class="cf-muted">人工</span>
                  <QaResultTag :result="item.human?.result" :reason-code="item.human?.reason_code" />
                </div>
                <div v-if="item.width" class="card-row cf-muted">{{ item.width }} × {{ item.height }}</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card shadow="never" class="cf-card">
          <template #header>
            <div class="card-header">
              <span>READY 门禁</span>
              <el-tag :type="gate?.ready ? 'success' : 'danger'" size="small">
                {{ gate?.ready ? '可通过' : '未通过' }}
              </el-tag>
            </div>
          </template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="修订状态">
              <el-tag :type="dictValue(REVISION_STATUS_DICT, detail?.revision_status).type" size="small">
                {{ dictValue(REVISION_STATUS_DICT, detail?.revision_status).label }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="通过数量">{{ gate?.passed_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="标题">{{ detail?.title_text ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="品牌">{{ detail?.brand_name ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="对象">{{ detail?.object ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Core Hash">
              <span class="cf-mono">{{ detail?.core_hash ?? '-' }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="gate && !gate.ready" class="blockers">
            <p class="cf-muted">阻塞项：</p>
            <el-tag v-for="item in gate.blockers" :key="item" type="danger" size="small" effect="plain" class="blocker">
              {{ item }}
            </el-tag>
          </div>

          <div v-if="gate" class="roles">
            <p class="cf-muted">必需角色状态：</p>
            <el-tag
              v-for="(state, role) in gate.required_status"
              :key="role"
              :type="state === 'PASS' ? 'success' : state === 'FAIL' ? 'danger' : 'info'"
              size="small"
              effect="plain"
            >
              {{ SLOT_ROLE_DICT[role as string] ?? role }}：{{ state }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>
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

.card-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.slot-badge {
  display: inline-flex;
  width: 18px;
  height: 18px;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background-color: var(--el-color-primary-light-3);
  color: #fff;
  font-size: 11px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.blockers,
.roles {
  margin-top: 12px;

  p {
    margin: 0 0 6px;
  }

  .el-tag {
    margin: 0 6px 6px 0;
  }
}
</style>
