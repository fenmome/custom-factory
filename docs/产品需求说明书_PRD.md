# Custom Factory 定制工厂 — 产品需求说明书（PRD）

> **版本**: V1.0
> **日期**: 2026-10-09
> **状态**: 基于 `codex/phase-3-schema-dev` 分支全量分析
> **用途**: 项目重构参考

---

## 一、产品概述

### 1.1 产品名称

**Custom Factory（定制工厂）**，代号 CF。

### 1.2 产品定位

独立、可迁移、可扩展的**定制商品生产系统**。核心业务是将买家上传的定制图案（artwork）批量转化为可用于电商平台（如 TEMU）的商品列表内容（标题 + 多张产品图片 + 属性数据），完成从"一个想法"到"可发布商品"的全自动化流水线。

### 1.3 首发产品线

**Custom UV DTF（定制水晶标 / UV 转印贴纸）**

- 卖的是：买家上传的图案被印成 UV 转印贴纸
- 不卖的是：贴纸所贴的载体（盒子、瓶子等，仅作展示）
- 使用场景：小商家包装（small_business_packaging）

### 1.4 核心业务流程

```
Batch（批次创建）
  → Product Profile（产品档案）
    → Listing Concept（商品概念冻结）
      → Title（标题分配）
        → Image Prompt（图片提示词生成）
          → Image Generation（图片生成，API 或 Codex 两条路线）
            → Image QA（技术 + 语义 + 人工 + OCR 文字质检）
              → Production Guard（生产保护监控）
                → Product Data（商品属性数据）
                  → READY_FOR_PUBLISH（内容生产完成）
                    → Channel Import（渠道导入，TEMU/店小秘，下游系统）
```

### 1.5 项目阶段状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 0-1 业务流程冻结 | ✅ PASS | 业务决策已冻结（ADR 0001） |
| Phase 2 技术选型研究 | ✅ 完成 | 10 份研究报告 + 34 份证据 |
| Phase 3 数据模型设计 | ✅ 已冻结 | 17 实体 ER 模型 + Schema 实现计划 |
| Phase 3 Schema 实现 | ✅ 已实现 | 5 个 Alembic 迁移 |
| Phase 3 核心服务 | ✅ 部分实现 | 批次/标题/图片/QA/READY 等 30+ 服务 |
| Phase 4 图片工厂 | ✅ 部分实现 | UV DTF 8 槽位 Prompt + 对象解析 |
| Phase 4 前端 MVP | ✅ DEV 阶段 | FastAPI + Jinja2，仅限本机 |
| Phase 4 TEMU 模板 | ✅ 部分实现 | Excel 导入 + 12 变体预览 |
| 生产部署 | ❌ 未实现 | 无 Dockerfile、CI/CD |
| Channel Import | ❌ 未实现 | TEMU 发布 API 待研究 |

---

## 二、目标用户与角色

### 2.1 用户角色

| 角色 | 职责 | 系统权限 |
|------|------|----------|
| **运营操作员（Operator）** | 创建批次、触发生产准备、人工复审图片 | 读写批次/复审/READY |
| **质检审核员（Reviewer）** | 人工复审自动生成的图片、OCR 文字复核 | 复审图片、确认/推翻自动 QA |
| **维护管理员（Admin）** | 配置产品类型/SKU 前缀、管理生产保护、QA 校准 | 配置 + 试运行恢复 |
| **系统执行器（Codex）** | 领取 SKU 生图任务、上传生成结果 | 受限 Runner API，仅执行生图 |

### 2.2 Workspace 模型

- 系统支持多工作空间（Workspace），数据完全隔离
- 用户通过 WorkspaceMembership 关联到 Workspace，角色为 OWNER / MEMBER / REVIEWER
- 当前为单机 DEV 模式，生产登录/部署延后

---

## 三、功能需求

### FR-01 批次创建（Batch Creation）

**描述**：运营人员选择产品类型、使用场景、数量、生成路线（CODEX/API）、视觉偏好，创建一个生产批次。

**详细规则**：
- 产品类型由系统管理（名称 + SKU 前缀 + 流水号位数）
- 创建 N 个商品时，**同一事务内原子分配 N 个 SKU**
- SKU 格式：`前缀 + 定宽流水号`，如 `DZUVDTF000001`
  - 前缀：大写字母 + 数字，非空，全局唯一
  - 流水号：从 1 开始递增，不回绕，不同产品类型独立计数
  - 已分配的 SKU 永久保留，不可回收
- 生成路线：当前仅支持 `CODEX`（API 路线已定义但未启用）
- 视觉偏好：风格（style）+ 配色（palette），默认"系统自动"
- 每次创建生成不可变的请求快照文件（`<hash>.json`）

**输入**：产品类型 ID、数量、路线、使用场景、风格、配色
**输出**：Batch ID + N 个 Product + N 个 SKU

---

### FR-02 产品类型与 SKU 管理

**描述**：管理产品类型的名称、SKU 前缀、流水号位数、启用状态。

**详细规则**：
- 前缀一旦被使用，永久归属该产品类型，即使后来换前缀
- 修改位数不能缩短到装不下当前/历史最大值
- `000000` 无效，流水号从 1 开始
- 启用/停用不影响已分配的 SKU

---

### FR-03 标题分配（Title Allocation）

**描述**：为每个商品从预审批的标题池中分配一个标题。

**详细规则**：
- 标题池来自 Title Factory 离线预生成（当前 Small Business 池有 **84,658** 个标题）
- 分配流程：`AVAILABLE → RESERVED → USED`
- 标题绑定基于 Concept 的语义指纹（core_hash）
- 标题是全局资源，由 TitleUsage 记录消耗
- READY 首次成功时消费 1 个 TitleUsage；后续修订不再消耗
- 标题文本变更仅在同一产品内允许，且核心语义不能变

---

### FR-04 图片工厂 — UV DTF 八槽位

**描述**：为每个 SKU 生成一套 8 张产品图，每张有固定的业务角色。

**八槽位定义**：

| 槽位 | 角色 | 必需 | 职责 |
|------|------|------|------|
| 01 | main_image（主图） | ✅ | 成品 UV DTF 贴纸在载体上的效果图；建立标准图案参考 |
| 02 | size_chart（尺寸图） | ✅ | 展示 1.5/2/3/4/5 英寸对应厘米数 |
| 03 | customization_info（定制说明） | ✅ | 买家上传说明：推荐透明 PNG，接受 JPG/PNG |
| 04 | scene_1（应用场景） | ❌ | 自然使用场景 |
| 05 | scene_2（质感特写） | ❌ | 微距展示 UV 墨水边缘、微浮雕、局部光泽 |
| 06 | scene_3（定制流程） | ❌ | 上传 → UV 转印 → 贴到光滑表面 |
| 07 | usage_instruction（使用步骤） | ❌ | 清洁 → 定位 → 按压 → 撕除 |
| 08 | application_surfaces（适用材质） | ❌ | 适合/不适合的表面教育 |

**关键规则**：
- `planned_count = 8`，`min_ready_count = 5`
- 必需角色（main_image, size_chart, customization_info）任何一张失败，整套不可 READY
- 最终输出：原始 PNG，正方形，宽高各 ≥1200px
- **禁止**：缩放、裁剪、格式转换、重新压缩

---

### FR-05 对象解析（Object Resolution）

**描述**：从买家查询（Query）中解析出贴纸所贴的"载体对象"。

**解析顺序**：
1. Primary Query 有明确 ACTIVE 对象 → 用它
2. Primary 非 ACTIVE → **HOLD**（不允许替换）
3. Primary 无对象 → 从 Secondary Query 取第一个 ACTIVE
4. 全部无对象 → 按固定字母序：GIFT_BOX → MAILER_BOX → PACKAGING_BOX → PRODUCT_BOX

**对象状态**：
| 状态 | 对象 |
|------|------|
| ACTIVE | GIFT_BOX, MAILER_BOX, PACKAGING_BOX, PRODUCT_BOX |
| HOLD | SHIPPING_BOX, RETAIL_BOX, RIGID_BOX, COATED_BOX, JEWELRY_PACKAGING, TIN_CONTAINER |
| CROSS_USAGE_ONLY | BOTTLE, JAR, CANDLE_JAR, COSMETIC_CONTAINER, CUP_TUMBLER |

**表面要求**：所有对象需 clean, dry, smooth, hard, non_porous, external_surface
**MAILER_BOX 额外要求**：coated 或 laminated 涂层

---

### FR-06 提示词生成（Prompt Rendering）

**描述**：基于冻结的 Concept 语义 + 解析出的对象 + 品牌/视觉计划，渲染 8 个完整的图片生成提示词。

**输入白名单**：
- PrimaryVisualSemantic（仅 Primary Query 的结构化语义）
- 解析后的冻结对象
- 卖出实体（sold_entity）
- 表面条件
- 冻结的艺术品事实（品牌、logo 描述、配色、风格）

**禁止输入**：Secondary Query 文本、完整标题、买家联系方式等

---

### FR-07 图片生成（Image Generation）

**描述**：通过两条路线执行实际的图片生成。

**路线 A：API（OpenAI 兼容）**
- 配置：Provider 名称、base_url、API Key、模型
- 协议：`POST /v1/images/generations`
- 安全：API Key 不入库、不提交 Git
- 当前状态：代码已实现，但 UI 中标记"暂未启用"

**路线 B：Codex（当前主路线）**
- 以 SKU 集合为执行单元
- 同一 SKU 由同一执行器、同一会话完成
- 通过本地 Runner HTTP 协议（127.0.0.1）通信
- 支持跨批次公平领取
- Slot01 先生成，后续槽位以 Slot01 PNG 为参考图
- 上传的原始 PNG 需 SHA-256 校验一致后才注册为正式资产

---

### FR-08 图片质检（Image QA）

**四层质检体系**：

#### 8.1 技术质检（Technical QA）— 自动
- 文件完整性（SHA-256 + 字节数）
- PNG 解码有效性
- 尺寸检查（正方形，≥1200×1200）
- 透明像素检测（正常图不应有透明像素）
- 存储配置验证

#### 8.2 语义质检（Semantic QA）— 自动 + 人工兜底
- 检查原因码：PRODUCT_MISMATCH, ROLE_MISMATCH, CONCEPT_INCONSISTENCY, TEXT_ERROR, VISUAL_DEFECT, REVIEW_REQUIRED_UNCERTAIN
- `REVIEW_REQUIRED_UNCERTAIN` 存为 FAIL，必须人工复审

#### 8.3 人工复审（Human Review）
- 按 SKU 集合审核（一次看 8 张图）
- 可逐图标记问题/通过
- 人工 FAIL 可推翻语义自动 PASS
- 人工 PASS 可推翻语义自动 FAIL
- **但硬技术失败（文件损坏/尺寸错/透明等）永远不可人工放行**
- 复审是追加式的（ImageQA.kind=HUMAN），不修改原始自动记录

#### 8.4 OCR 文字质检（OCR Text QA）
- 使用本地 PaddleOCR 运行时
- 检测图片中不应出现的文字（如 Water Resistant, UV Resistant 等虚假宣传）
- 检测结果需要人工确认
- 假阳性率需要校准

**校准机制**：
- 每个产品类型的前 3 个批次为校准期
- 自动失败的 SKU 集合必须人工复审
- 每批次稳定采样最多 20 个自动通过的 SKU 集合
- 统计 TRUE_PASS / FALSE_PASS / TRUE_FAIL / FALSE_FAIL
- ≥3 批次 + ≥100 张人工复审图片后触发 `QA_RULE_REVIEW_DUE`

---

### FR-09 生产保护（Production Guard）

**描述**：监控生产质量，在异常时自动暂停生产，人工确认后试运行恢复。

**三色状态**：

| 状态 | 含义 | 行为 |
|------|------|------|
| 🟢 GREEN | 正常 | 继续生产 |
| 🟡 YELLOW | 警告 | 显示警告，不降速不停止 |
| 🔴 RED | 暂停 | 停止新任务领取，已开始的可安全结束 |
| ⛔ CRITICAL_STOP | 紧急停止 | 立即停止（认证失败/配额耗尽/存储故障等） |

**YELLOW 规则**：
| ID | 触发条件 |
|----|----------|
| YELLOW-01 | 最近 50 个 QA 完成 SKU 失败率 ≥10% 且 <20% |
| YELLOW-02 | 最近 100 张图片 QA 失败率 ≥20% |
| YELLOW-03 | 同一必需角色连续 2 个 SKU 失败 |

**RED 规则**：
| ID | 触发条件 |
|----|----------|
| RED-01 | 连续 5 个 SKU 未通过 READY |
| RED-02 | 最近 20 个 SKU 中 ≥6 个失败（≥30%） |
| RED-03 | 最近 50 个 SKU 中 ≥10 个失败（≥20%） |
| RED-04 | 同一必需角色连续 3 个 SKU 失败 |
| RED-05 | 同一非致命系统异常连续 3 次 |

**启动观察期**（模型/Prompt/策略变更后）：前 10 个 SKU，0-1 失败继续，2 个黄色，≥3 个红色暂停

**恢复流程**：自动暂停 → 人工确认 → 试运行（最多 3 个 SKU）→ 3/3 全过恢复，任一失败继续暂停

**暂停范围**：PRODUCT_TYPE_SCOPE / PROVIDER_MODEL_SCOPE / SYSTEM_SCOPE，取最小影响范围

---

### FR-10 内容生产完成（READY）

**描述**：当一个 SKU 的所有必要内容（标题 + 图片 + 属性数据）都就绪时，标记为 READY_FOR_PUBLISH。

**READY 必要条件**：
1. ✅ 创建批次时已分配永久 SKU
2. ✅ ListingConcept 完整冻结 + 标题身份确认
3. ✅ ProductData 属性数据已生成
4. ✅ 图片满足 Image Policy（≥5 张通过 + 所有必需角色通过）
5. ✅ 图片实际字节完整性 VERIFIED
6. ✅ 当前 ImageQA + RevisionQA 均为 PASS
7. ✅ 原子完成首次 TitleUsage / TitleReservation / Revision 状态 / 审计事件

**READY 含义**：CustomFactory 内容生产完成，**不等于**平台发布

---

### FR-11 商品属性数据（Product Data）

**描述**：基于 Small Business 属性 Schema 生成结构化的商品数据。

**当前 Schema**：
- `cf:uv-dtf-small-business-attributes:v1`
- 必填字段：`surface_gate`（表面条件数组）
- 绑定 Product Profile `uv_dtf_crystal` v1.0
- 属性值固定为：`["clean", "dry", "smooth", "hard", "non_porous", "external_surface"]`

---

### FR-12 TEMU / 店小秘类目模板

**描述**：导入操作员编辑好的 TEMU Excel 模板，生成 12 变体的发布预览。

**功能**：
- Excel 导入（37 列，4 尺寸 × 3 数量 = 12 变体）
- 不可变版本快照存储（按内容哈希去重）
- 发布配置文件（Profile）绑定店铺 + 账号标签
- 只读预览：读取 READY 的 Revision 冻结内容 → 展开 12 行

**列分类**：
| 分类 | 数量 | 示例 |
|------|------|------|
| DYNAMIC_PRODUCT | 4 | 产品标题、产品货号、轮播图、素材图 |
| TEMPLATE_PRODUCT | 17 | 外包装、定制品类型、分类 id、产地等 |
| TEMPLATE_VARIANT | 13 | 变种名称、尺寸、重量、SKU 货号等 |
| OFFER | 2 | 申报价格、建议零售价 |
| ROUTING | 1 | 所属店铺 |

**当前状态**：`publish_ready = false`（价格未配置 + 图片上传未实现 + 发布 API 未实现）

---

### FR-13 Web 前端（DEV UI）

**描述**：FastAPI + Jinja2 服务端渲染的管理界面，仅限本机访问。

**页面清单**：
| 路径 | 页面 | 功能 |
|------|------|------|
| `/dev` | 工作空间选择 | 选择用户/工作空间 |
| `/` | 生产总览 | 批次列表、指标面板、执行会话 |
| `/batches/new` | 创建批次 | 表单：类型/数量/路线/视觉偏好 |
| `/batches/{id}` | 批次详情 | SKU 进度、生产准备状态 |
| `/skus/{id}` | SKU 详情 | 图片网格、QA 状态、READY 按钮 |
| `/reviews` | 人工复审列表 | 待审 SKU + 随机抽查 |
| `/reviews/skus/{id}` | 操作员复审 | 8 图审核 + OCR 复核 + 逐图标记 |
| `/calibration` | QA 校准报告 | 漏检/误杀统计、按角色/原因分析 |
| `/guard` | 生产保护 | 暂停状态、试运行恢复、规则展示 |
| `/types` | 产品类型 | SKU 前缀/位数/启用配置 |
| `/assets/{id}` | 图片查看 | 原始 PNG 服务（含完整性校验） |

**安全措施**：
- 仅允许 127.0.0.1/localhost 访问
- CSRF token 校验
- Origin / sec-fetch-site 检查
- CSP / X-Frame-Options 等安全头
- 表单长度限制 32KB

---

## 四、非功能需求

### 4.1 技术架构

| 维度 | 选型 |
|------|------|
| 架构风格 | 模块化单体（Modular Monolith） |
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI + Uvicorn |
| 模板引擎 | Jinja2 |
| 前端 | 原生 JavaScript（无框架） |
| ORM | SQLAlchemy 2.1 |
| 数据库迁移 | Alembic |
| 数据库 | SQLite（开发）→ PostgreSQL（生产） |
| 图片生成 | OpenAI 兼容 API / Codex 双路线 |
| OCR | PaddleOCR 本地运行时 |
| 存储 | 文件系统（开发）→ 对象存储（生产） |

### 4.2 数据安全

- 所有配置资源通过 SHA-256 哈希固定（content-addressed）
- 图片存储使用 `storage_profile + storage_key`，不存绝对路径
- API Key 不入库、不提交 Git
- 请求快照、冻结计划均使用规范 JSON（CF-CJSON-V1）
- 幂等键防止重复操作

### 4.3 图片格式约束

- 正式格式：**仅 PNG**
- 不做任何格式转换、缩放、裁剪、重新压缩
- 非 PNG 输入返回 `UNSUPPORTED_IMAGE_FORMAT` 拒绝
- 目标尺寸：正方形，≥1200×1200（1254×1254 等更大尺寸也可）

### 4.4 文件系统治理

- 所有项目文件必须在项目根目录内
- 临时文件 → `tmp/`，缓存 → `cache/`，日志 → `logs/`，产物 → `artifacts/`
- 外部存储需明确审批（当前 `EXTERNAL_STORAGE_PATHS=NONE_APPROVED`）
- 本地图片根目录默认 `/Volumes/ZHITAI/Images/CustomFactory`（可配置）

---

## 五、待决策事项

| # | 事项 | 状态 |
|---|------|------|
| 1 | 是否需要 PNG → JPG 转换（当文件体积成为问题时） | 待定 |
| 2 | 真实图片 QA 验证 + 语义 QA 提供者选型 | PENDING |
| 3 | UV DTF 之外的产品类型角色集合 | 待定 |
| 4 | QA 失败图片的保留期限/删除策略 | PENDING |
| 5 | SERVER/OBJECT STORAGE 实现选型 | 待定 |
| 6 | Codex Runner 生产部署验证 | 待定 |
| 7 | TEMU 发布 API 研究与对接 | 未开始 |
| 8 | 前端框架选型（当前原生 JS） | 待定 |
| 9 | 生产环境部署方案（Docker/CI-CD） | 未开始 |

---

## 六、关键技术决策摘要（ADR 索引）

| ADR | 标题 | 状态 |
|-----|------|------|
| 0001 | Phase 0-1 冻结业务决策 | FROZEN |
| 0002 | 项目文件系统治理 | ACCEPTED |
| 0003 | Phase 2 最终技术架构 | ACCEPTED |
| 0004 | Phase 3 核心数据模型 V1 | ACCEPTED |
| 0005 | Phase 3 Schema 实现计划 | ACCEPTED |
| 0006 | 项目根目录迁移 | ACCEPTED |
| 0007 | SKU 分配与核心模型修订 | ACCEPTED |
| 0008 | Phase 3 生产业务规则 V1 | ACCEPTED |
| 0009 | 模块化单体与过度设计治理 | ACCEPTED |
