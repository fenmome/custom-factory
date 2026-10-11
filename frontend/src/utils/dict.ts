type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger';

export interface DictItem {
  label: string;
  type: TagType;
}

/** QA 结果。 */
export const QA_RESULT_DICT: Record<string, DictItem> = {
  PASS: { label: '通过', type: 'success' },
  FAIL: { label: '失败', type: 'danger' },
  PENDING: { label: '待判定', type: 'info' }
};

/** 修订状态。 */
export const REVISION_STATUS_DICT: Record<string, DictItem> = {
  DRAFT: { label: '草稿', type: 'info' },
  DRAFT_LEGACY: { label: '历史草稿', type: 'info' },
  FROZEN: { label: '已冻结', type: 'warning' },
  READY_FOR_PUBLISH: { label: '可发布', type: 'success' }
};

/** 图片任务状态。 */
export const IMAGE_JOB_STATE_DICT: Record<string, DictItem> = {
  PENDING: { label: '待接收', type: 'info' },
  ASSET_RECORD_PENDING: { label: '待记录', type: 'info' },
  ASSET_RECORDED: { label: '已记录', type: 'warning' },
  SETTLED: { label: '已完成', type: 'success' },
  CANCELLED: { label: '已取消', type: 'info' }
};

/** 完整性状态。 */
export const INTEGRITY_DICT: Record<string, DictItem> = {
  UNVERIFIED: { label: '未校验', type: 'info' },
  VERIFIED: { label: '已校验', type: 'success' },
  MISMATCH: { label: '不一致', type: 'danger' }
};

/** 生产保护级别。 */
export const GUARD_LEVEL_DICT: Record<string, DictItem> = {
  GREEN: { label: '正常', type: 'success' },
  YELLOW: { label: '警告', type: 'warning' },
  RED: { label: '暂停', type: 'danger' },
  CRITICAL_STOP: { label: '紧急停止', type: 'danger' }
};

/** 暂停作用域。 */
export const GUARD_SCOPE_DICT: Record<string, string> = {
  PRODUCT_TYPE_SCOPE: '产品类型范围',
  PROVIDER_MODEL_SCOPE: '供应商/模型范围',
  SYSTEM_SCOPE: '系统范围'
};

/** 暂停状态。 */
export const PAUSE_STATE_DICT: Record<string, DictItem> = {
  PAUSED: { label: '已暂停', type: 'danger' },
  TRIAL_RUNNING: { label: '试运行中', type: 'warning' },
  RESOLVED: { label: '已解除', type: 'success' }
};

/** 复审原因码。 */
export const REVIEW_REASON_CODES = [
  { value: 'PRODUCT_MISMATCH', label: '商品不符' },
  { value: 'ROLE_MISMATCH', label: '角色不符' },
  { value: 'CONCEPT_INCONSISTENCY', label: 'Concept 不一致' },
  { value: 'TEXT_ERROR', label: '文字错误' },
  { value: 'VISUAL_DEFECT', label: '视觉缺陷' },
  { value: 'OTHER', label: '其它' }
] as const;

/** QA 类型。 */
export const QA_KIND_DICT: Record<string, string> = {
  TECHNICAL: '技术质检',
  SEMANTIC: '语义质检',
  HUMAN: '人工复审',
  OCR: '文字/品牌校验'
};

/** 8 槽位角色中文名（与图片策略 `slot_roles` 保持一致）。 */
export const SLOT_ROLE_DICT: Record<string, string> = {
  main_image: '主图',
  size_chart: '尺寸图',
  customization_info: '定制信息图',
  scene_1: '场景图 1',
  scene_2: '场景图 2',
  scene_3: '场景图 3',
  usage_instruction: '使用说明图',
  application_surfaces: '适用表面图'
};

/** 必需槽位（来自图片策略）。 */
export const REQUIRED_SLOTS = [1, 2, 3];

export function dictValue(dict: Record<string, DictItem>, key?: string | null, fallback = '-'): DictItem {
  if (!key) return { label: fallback, type: 'info' };
  return dict[key] ?? { label: key, type: 'info' };
}

export function percent(value: number, total: number): number {
  if (!total) return 0;
  return Math.round((value / total) * 100);
}
