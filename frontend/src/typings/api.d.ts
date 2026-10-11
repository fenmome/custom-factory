/** 后端统一响应格式 `{ code, message, data, detail }`。 */

declare namespace Api {
  interface Response<T> {
    code: number;
    message: string;
    data: T;
    detail?: unknown;
  }

  interface Page<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
  }

  // ---------------- 认证 ----------------
  namespace Auth {
    interface LoginParams {
      email: string;
      password: string;
    }

    interface LoginToken {
      token: string;
      token_type: string;
      expires_hours: number;
      user: UserInfo;
      workspace: WorkspaceBrief | null;
    }

    interface UserInfo {
      id: string;
      email: string;
      display_name: string;
      state: string;
      is_superuser: boolean;
    }

    interface WorkspaceBrief {
      id: string;
      display_name: string;
      state: string;
      role: string;
    }
  }

  // ---------------- 工作空间 ----------------
  namespace Workspace {
    interface Item {
      id: string;
      display_name: string;
      state: string;
      role: string;
    }
  }

  // ---------------- 产品类型 ----------------
  namespace ProductType {
    interface Item {
      id: string;
      product_type_code: string;
      display_name: string;
      prefix: string;
      sequence_width: number;
      last_sequence: number;
      is_enabled: boolean;
      created_at: string;
    }

    interface UpsertParams {
      product_type_code: string;
      display_name: string;
      prefix: string;
      sequence_width?: number;
      is_enabled?: boolean;
    }
  }

  // ---------------- 批次 ----------------
  namespace Batch {
    interface CreateParams {
      operation_key: string;
      request_key: string;
      product_type_code?: string;
      usage_code?: string;
      quantity: number;
      image_generation_route?: 'API' | 'CODEX';
      style_code?: string | null;
      palette_code?: string | null;
    }

    interface Summary {
      id: string;
      product_type_id: string;
      requested_quantity: number;
      image_generation_route: string;
      control_state: string;
      request_key: string;
      input_snapshot_hash: string;
      usage_code: string;
      style_code: string | null;
      palette_code: string | null;
      prepared_at: string | null;
      created_at: string;
    }

    interface Item {
      id: string;
      product_id: string;
      internal_sku: string;
      revision_id: string;
      revision_status: string;
      image_progress: { total: number; settled: number; asset_recorded: number };
    }

    interface Detail {
      batch: Summary;
      items: Item[];
      counts: Record<string, number>;
    }

    interface Progress {
      batch_id: string;
      requested_quantity: number;
      allocated_count: number;
      by_status: Record<string, number>;
      image_total: number;
      image_done: number;
      image_percent: number;
      prepared_at: string | null;
    }
  }

  // ---------------- 商品 / SKU ----------------
  namespace Product {
    interface QaBrief {
      result: string;
      reason_code: string | null;
      reason_detail: string | null;
      evaluated_at: string | null;
    }

    interface ImageBrief {
      slot: number;
      role: string;
      is_required: boolean;
      job_state: string;
      asset_id: string | null;
      width: number | null;
      height: number | null;
      integrity_state: string | null;
      effective_result: string | null;
      technical: QaBrief | null;
      semantic: QaBrief | null;
      human: QaBrief | null;
      ocr: QaBrief | null;
    }

    interface ReadyGate {
      ready: boolean;
      blockers: string[];
      passed_count: number;
      required_status: Record<string, string>;
    }

    interface Detail {
      product_id: string;
      internal_sku: string;
      batch_id: string;
      revision_id: string;
      revision_status: string;
      title_text: string | null;
      brand_name: string | null;
      object: string | null;
      core_hash: string | null;
      images: ImageBrief[];
      ready_gate: ReadyGate;
      created_at: string | null;
    }

    interface ListItem {
      product_id: string;
      internal_sku: string;
      batch_id: string;
      revision_status: string | null;
      state: string;
    }

    interface ReadyResult {
      product_id: string;
      revision_id: string;
      status: string;
      ready_gate_id: string;
      selected_assets: string[];
      passed_count: number;
      title_usage_created: boolean;
    }
  }

  // ---------------- 复审 ----------------
  namespace Review {
    interface SnapshotItem {
      asset_id: string;
      checksum: string;
    }

    interface DecisionIn {
      slot: number;
      decision: 'PASS' | 'FAIL';
      reason_code?: string | null;
      note?: string | null;
    }

    interface SubmitParams {
      operation_key: string;
      decisions: DecisionIn[];
      snapshot: SnapshotItem[];
      complete_set?: boolean;
    }

    interface ReviewItem {
      slot: number;
      role: string;
      is_required: boolean;
      asset_id: string | null;
      checksum: string | null;
      width: number | null;
      height: number | null;
      byte_size: number | null;
      integrity_state: string | null;
      technical: QaBriefShape | null;
      semantic: QaBriefShape | null;
      human: QaBriefShape | null;
      ocr: QaBriefShape | null;
      effective: string;
      history: Array<Record<string, unknown>>;
    }

    interface QaBriefShape {
      result: string;
      reason_code: string | null;
      reason_detail: string | null;
      evaluated_at: string | null;
    }

    interface View {
      product_id: string;
      internal_sku: string;
      revision_id: string;
      revision_status: string;
      brand_name: string | null;
      object: string | null;
      title_text: string | null;
      items: ReviewItem[];
      snapshot: SnapshotItem[];
    }

    interface SubmitResult {
      product_id: string;
      accepted: Array<{ slot: number; qa_id: string; result: string }>;
      rejected: Array<{ slot: number; error: string; detail?: string }>;
      reviewed_count: number;
    }

    interface PendingItem {
      product_id: string;
      internal_sku: string;
      revision_id: string;
      revision_status: string;
      batch_id: string;
      request_key: string;
    }
  }

  // ---------------- 质检 / 校准 ----------------
  namespace Qa {
    interface HistoryItem {
      kind: string;
      result: string;
      reason_code: string | null;
      reason_detail: string | null;
      rule_id: string;
      rule_version: string;
      rule_hash: string;
      asset_checksum: string;
      evaluated_by: string | null;
      evaluated_at: string | null;
    }

    interface Board {
      false_pass: Array<Record<string, unknown>>;
      false_fail: Array<Record<string, unknown>>;
      false_pass_count: number;
      false_fail_count: number;
    }

    interface Calibration {
      product_type_id: string;
      batch_count: number;
      human_reviewed_images: number;
      agreement_rate: number;
      false_pass: number;
      false_fail: number;
      true_pass: number;
      true_fail: number;
      by_role: Array<{ role: string; agree: number; disagree: number }>;
      by_reason: Array<{ reason_code: string; agree: number; disagree: number }>;
      review_due: boolean;
    }
  }

  // ---------------- 生产保护 ----------------
  namespace Guard {
    interface PauseBrief {
      id: string;
      scope_kind: string;
      target: Record<string, unknown>;
      state: string;
      trigger_rule_id: string;
      rule_text: string;
      reason: string;
      paused_at: string | null;
      updated_at: string | null;
      trial_sku_limit: number;
      trial_claim_count: number;
      trial_completed_count: number;
      trial_pass_count: number;
      trial_fail_count: number;
    }

    interface Evaluation {
      level: string;
      rule_id: string | null;
      reason: string | null;
      metrics: Record<string, unknown>;
    }

    interface Status {
      level: string;
      evaluation: Evaluation;
      pauses: PauseBrief[];
      rules: Record<string, unknown>;
    }
  }

  // ---------------- 仪表盘 ----------------
  namespace Dashboard {
    interface Overview {
      counts: {
        batches: number;
        products: number;
        revisions: Record<string, number>;
        image_jobs: Record<string, number>;
        image_qa: Record<string, number>;
        revision_qa: Record<string, number>;
      };
      guard: {
        level: string;
        pauses: Api.Guard.PauseBrief[];
        evaluation: Api.Guard.Evaluation;
      };
      active_claims: number;
    }
  }

  // ---------------- 图片 ----------------
  namespace Image {
    interface Policy {
      policy_id: string;
      version: string;
      content_hash: string;
      policy: Record<string, unknown>;
    }

    interface JobItem {
      slot: number;
      role: string;
      is_required: boolean;
      state: string;
      asset_id: string | null;
      checksum: string | null;
    }
  }
}
