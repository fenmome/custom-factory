<script setup lang="ts">
import { Check, Close, Refresh, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import ImageThumb from '@/components/custom/image-thumb.vue';
import QaResultTag from '@/components/custom/qa-result-tag.vue';
import { fetchReviewView, submitReview } from '@/service/api/review';
import { REVIEW_REASON_CODES, SLOT_ROLE_DICT, dictValue } from '@/utils/dict';
import { uuidV4 } from '@/utils/uuid';

/** 硬技术失败原因码：永远不可人工放行。 */
const HARD_TECHNICAL_CODES = ['FORMAT_INVALID', 'TRANSPARENCY', 'DIMENSION_MISMATCH', 'FILE_TOO_LARGE'];

defineOptions({ name: 'ReviewDetail' });

const route = useRoute();
const router = useRouter();

const productId = computed(() => route.params.productId as string);

const loading = ref(false);
const submitting = ref(false);
const view = ref<Api.Review.View | null>(null);

/** 每个槽位的人工决策草稿。 */
const drafts = reactive<Record<number, { decision: 'PASS' | 'FAIL' | ''; reasonCode: string; note: string }>>({});

function draftOf(slot: number) {
  if (!drafts[slot]) {
    drafts[slot] = { decision: '', reasonCode: '', note: '' };
  }
  return drafts[slot];
}

function initDrafts() {
  for (const item of view.value?.items ?? []) {
    draftOf(item.slot);
  }
}

async function load() {
  loading.value = true;
  try {
    const result = await fetchReviewView(productId.value);
    if (result.error) {
      ElMessage.error(result.error.msg);
      return;
    }
    view.value = result.data;
    initDrafts();
  } finally {
    loading.value = false;
  }
}

/** 该槽位是否被硬技术失败锁定（禁止人工 PASS）。 */
function isHardBlocked(item: Api.Review.ReviewItem): boolean {
  const code = item.technical?.reason_code;
  return Boolean(item.technical?.result === 'FAIL' && code && HARD_TECHNICAL_CODES.includes(code));
}

function canSubmit(item: Api.Review.ReviewItem): boolean {
  const draft = draftOf(item.slot);
  if (!draft.decision) return false;
  if (draft.decision === 'PASS' && isHardBlocked(item)) return false;
  if (draft.decision === 'FAIL') {
    if (!draft.reasonCode) return false;
    if (draft.reasonCode === 'OTHER' && !draft.note.trim()) return false;
  }
  return Boolean(item.asset_id);
}

const selectedCount = computed(
  () => Object.values(drafts).filter(item => item.decision).length
);

async function submitAll() {
  const decisions = (view.value?.items ?? [])
    .filter(item => draftOf(item.slot).decision)
    .map(item => {
      const draft = draftOf(item.slot);
      return {
        slot: item.slot,
        decision: draft.decision as 'PASS' | 'FAIL',
        reason_code: draft.decision === 'FAIL' ? draft.reasonCode : null,
        note: draft.note || null
      };
    });

  if (!decisions.length) {
    ElMessage.warning('请至少对一个槽位做出判定');
    return;
  }

  submitting.value = true;
  try {
    const result = await submitReview(productId.value, {
      operation_key: uuidV4(),
      decisions,
      snapshot: view.value?.snapshot ?? [],
      complete_set: decisions.length === (view.value?.items.length ?? 0)
    });
    if (result.error) {
      ElMessage.error(`${result.error.msg} ${typeof result.error.detail === 'string' ? result.error.detail : ''}`);
      return;
    }
    const { accepted, rejected } = result.data!;
    ElMessage.success(`提交成功：通过 ${accepted.length} 项` + (rejected.length ? `，被拒 ${rejected.length} 项` : ''));
    if (rejected.length) {
      console.warn('不可人工放行的槽位：', rejected);
    }
    await load();
  } finally {
    submitting.value = false;
  }
}

function backToQueue() {
  router.push({ name: 'review_queue' });
}

onMounted(load);
</script>

<template>
  <div v-loading="loading" class="cf-page">
    <div class="cf-toolbar">
      <div>
        <h2 class="page-title">
          <el-icon><View /></el-icon>
          {{ view?.internal_sku ?? '复审' }}
        </h2>
        <p v-if="view?.title_text" class="cf-muted">{{ view.title_text }}</p>
      </div>
      <el-button-group>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button @click="backToQueue">返回队列</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAll">
          提交复审（已选 {{ selectedCount }}）
        </el-button>
      </el-button-group>
    </div>

    <el-alert
      v-if="view"
      type="info"
      :closable="false"
      show-icon
      title="复审规则"
      description="人工 PASS 可推翻语义自动 FAIL；人工 FAIL 可推翻语义自动 PASS；硬技术失败永远不可人工放行；反转自动结论必须选择原因码（OTHER 需填写说明）。"
      style="margin-bottom: 12px"
    />

    <el-card shadow="never" class="cf-card">
      <div class="review-grid">
        <div v-for="item in view?.items ?? []" :key="item.slot" class="review-card">
          <div class="review-card__thumb">
            <ImageThumb :asset-id="item.asset_id" :slot="item.slot" :size="180" />
            <div class="review-card__slot">槽位 {{ item.slot }}</div>
          </div>

          <div class="review-card__meta">
            <div class="row">
              <strong>{{ SLOT_ROLE_DICT[item.role] ?? item.role }}</strong>
              <el-tag v-if="item.is_required" size="small" type="warning" effect="plain">必需</el-tag>
              <el-tag :type="item.effective === 'PASS' ? 'success' : item.effective === 'FAIL' ? 'danger' : 'info'" size="small">
                {{ dictValue({ PASS: { label: '有效通过', type: 'success' }, FAIL: { label: '有效失败', type: 'danger' }, PENDING: { label: '待判定', type: 'info' } }, item.effective).label }}
              </el-tag>
            </div>

            <div class="row"><span class="label">技术</span><QaResultTag :result="item.technical?.result" :reason-code="item.technical?.reason_code" /></div>
            <div class="row"><span class="label">语义</span><QaResultTag :result="item.semantic?.result" :reason-code="item.semantic?.reason_code" /></div>
            <div class="row"><span class="label">文字</span><QaResultTag :result="item.ocr?.result" :reason-code="item.ocr?.reason_code" /></div>
            <div class="row"><span class="label">人工</span><QaResultTag :result="item.human?.result" :reason-code="item.human?.reason_code" /></div>

            <el-divider style="margin: 8px 0" />

            <el-radio-group v-model="draftOf(item.slot).decision" size="small" :disabled="!item.asset_id">
              <el-radio-button :value="'PASS'" :disabled="isHardBlocked(item)">判定通过</el-radio-button>
              <el-radio-button :value="'FAIL'">标记问题</el-radio-button>
            </el-radio-group>

            <el-alert
              v-if="isHardBlocked(item)"
              type="error"
              :closable="false"
              show-icon
              class="hard-block"
            >
              硬技术失败（{{ item.technical?.reason_code }}），不可人工放行
            </el-alert>

            <template v-if="draftOf(item.slot).decision === 'FAIL'">
              <el-select
                v-model="draftOf(item.slot).reasonCode"
                placeholder="选择原因码"
                size="small"
                style="width: 100%; margin-top: 8px"
              >
                <el-option v-for="opt in REVIEW_REASON_CODES" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
              <el-input
                v-if="draftOf(item.slot).reasonCode === 'OTHER'"
                v-model="draftOf(item.slot).note"
                type="textarea"
                :rows="2"
                size="small"
                placeholder="原因码 OTHER 必须填写说明"
                style="margin-top: 6px"
              />
            </template>

            <p v-if="canSubmit(item)" class="ready-hint">
              <el-icon><Check /></el-icon> 已就绪待提交
            </p>
            <p v-else-if="!item.asset_id" class="muted-hint"><el-icon><Close /></el-icon> 尚无资产</p>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.review-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
}

.review-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: #fff;

  &__thumb {
    position: relative;
    flex-shrink: 0;
  }

  &__slot {
    margin-top: 6px;
    text-align: center;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
}

.row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;

  .label {
    width: 28px;
    color: var(--el-text-color-secondary);
  }
}

.hard-block {
  margin-top: 8px;
}

.ready-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 6px 0 0;
  color: var(--el-color-success);
  font-size: 12px;
}

.muted-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
}
</style>
