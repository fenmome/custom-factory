# AGENTS.md — Custom Factory 重构项目

> AI 编码助手必读。本文件定义项目约束和关键规则，详细文档在 `docs/` 目录。

---

## 1. 项目简介

**Custom Factory（定制工厂）**：定制商品生产系统。核心流程：

```
创建批次 → 分配SKU → 分配标题 → 冻结概念 → 渲染提示词 → 生成图片
→ 质检(技术/语义/人工/OCR) → 生产保护监控 → 商品数据 → READY_FOR_PUBLISH
```

首发产品线：**Custom UV DTF（定制水晶标）**——买家上传图案 → 生成 8 张电商产品图。

---

## 2. 技术栈（硬性约束，不可更改）

| 层 | 选型 |
|----|------|
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Element Plus |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy 2.0 + Alembic |
| 数据库 | MySQL 8.0（Docker） |
| 部署 | Docker Compose（开发 + 生产） |
| 架构 | 前后端分离，RESTful API |

**禁止引入**：React、Django、Celery、Kafka、微服务架构、GraphQL。

---

## 3. 项目结构

```
custom-factory/
├── docker-compose.yml          # 生产编排
├── docker-compose.dev.yml      # 开发覆盖
├── .env.example
├── Makefile
├── docs/                       # 产品和技术文档
│   ├── 产品需求说明书_PRD.md
│   ├── 产品功能说明书.md
│   ├── 资源摘录_提示词与规则.md
│   └── 技术架构设计文档.md
├── backend/                    # FastAPI 后端
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py             # 入口
│   │   ├── config.py           # 配置
│   │   ├── api/v1/             # 路由
│   │   ├── models/             # SQLAlchemy 模型
│   │   ├── schemas/            # Pydantic 模型
│   │   ├── services/           # 业务逻辑
│   │   ├── core/               # 基础设施
│   │   ├── providers/          # 外部服务适配
│   │   └── resources/          # 业务规则 JSON
│   └── tests/
├── frontend/                   # Vue 3 前端
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── api/                # 请求封装
│       ├── stores/             # Pinia
│       ├── router/
│       ├── views/              # 页面
│       ├── components/         # 组件
│       └── composables/
├── data/                       # 持久化（Docker 卷）
└── scripts/
```

---

## 4. 关键业务规则（必须严格遵守）

### 4.1 SKU 分配
- 格式：`前缀 + 定宽流水号`，如 `DZUVDTF000001`
- 创建批次时在**同一数据库事务**内原子分配 N 个 SKU
- 前缀：大写字母+数字，全局唯一，一旦使用永久归属该产品类型
- 流水号从 1 开始，不回绕，不同产品类型独立计数
- `000000` 无效，已分配 SKU 不可回收

### 4.2 图片规格（不可违反）
- 仅 PNG 格式，**禁止**格式转换/缩放/裁剪/重新压缩
- 正方形，宽高各 ≥1200px（1254×1254 等更大尺寸也接受）
- 不允许透明像素（`TRANSPARENCY_EXPECTED=NO`）
- 8 槽位：3 必需（main_image/size_chart/customization_info）+ 5 可选
- `planned_count=8`，`min_ready_count=5`
- 任何必需角色失败 → 整套不可 READY

### 4.3 QA 规则
- QA 记录是**追加式**的（INSERT，不 UPDATE）
- 人工 PASS 可推翻语义自动 FAIL
- 人工 FAIL 可推翻语义自动 PASS
- **硬技术失败**（文件损坏/校验不匹配/尺寸错/透明/解码失败）**永远不可人工放行**
- 校准期：每产品类型前 3 个批次，自动失败必须人工复审
- 随机采样：每批次最多 20 套自动通过的 SKU 集合

### 4.4 生产保护（Guard）
- GREEN 正常 / YELLOW 警告（不停不减速）/ RED 暂停 / CRITICAL_STOP 紧急停止
- YELLOW：50 SKU 失败率 ≥10%、100 图失败率 ≥20%、必需角色连续 2 失败
- RED：连续 5 SKU 未 READY、20 中 ≥6 失败、50 中 ≥10 失败、角色连续 3 失败、异常连续 3 次
- RED 暂停 → 人工确认 → 试运行 3 SKU → 3/3 通过恢复，任一失败重新暂停
- 暂停取最小范围：产品类型 / 供应商+模型 / 全系统

### 4.5 READY 判定（全部满足才可通过）
1. 已分配永久 SKU
2. ListingConcept 状态 FROZEN + 标题身份确认
3. ProductData 存在且 QA 指纹匹配
4. 图片 ≥5 张通过 + 所有必需角色通过
5. 每张选中图片字节完整性 VERIFIED + 当前 QA = PASS
6. 原子完成 TitleUsage + Revision 状态 + 审计事件

### 4.6 对象解析
- 优先 Primary Query 的 ACTIVE 对象；非 ACTIVE 一律 HOLD
- Primary 无对象 → Secondary 第一个 ACTIVE
- 全部无 → 固定字母序：GIFT_BOX → MAILER_BOX → PACKAGING_BOX → PRODUCT_BOX
- ACTIVE 仅 4 个：GIFT_BOX, MAILER_BOX, PACKAGING_BOX, PRODUCT_BOX
- 所有对象需表面条件：clean, dry, smooth, hard, non_porous, external_surface

### 4.7 禁止文字（图片中不可出现）
```
Water Resistant, UV Resistant, Scratch Resistant, Durable,
Long Lasting, Waterproof, Dishwasher Safe
```
以及任何未经批准的性能声明、品牌 slogan、调试文字。

---

## 5. 业务资源文件

以下 JSON 文件包含核心业务配置，**不可在代码中硬编码**，必须从文件加载并通过 SHA-256 校验：

```
app/resources/
├── prompt_rules/UV_DTF_PROMPT_RULE_V1_4.json     # 8槽位提示词
├── image_policy/uv_dtf_image_policy_v1_2.json     # 图片策略
├── visual_prep/visual_preparation_v1.json          # 品牌/配色/风格
├── visual_prep/allowed_objects_v1.json             # 允许对象
├── guard_rules/production_guard_rules_v1.json      # 生产保护阈值
├── profiles/product_profile_v1.json                # 产品档案
└── schemas/small_business_attribute_schema_v1.json # 属性Schema
```

完整内容见 `docs/资源摘录_提示词与规则.md`。

---

## 6. API 设计规范

**Base URL**：`/api/v1`

**统一响应**：
```json
{ "code": 0, "message": "success", "data": {} }
```

**错误**：
```json
{ "code": 40001, "message": "Validation failed", "detail": "..." }
```

**认证**：JWT Bearer Token，Header: `Authorization: Bearer <token>`

**幂等**：创建类操作需携带 `operation_key`（UUID），服务端校验去重

---

## 7. 数据库约定

- 主键：`CHAR(36)` UUID v4
- 时间戳：`TIMESTAMP(6)`，UTC
- JSON 字段：业务约束和快照用 `JSON` 类型
- 软删除：`state` 字段（ACTIVE/CANCELLED/ARCHIVED），不物理删除
- 迁移：Alembic，只前进不回滚生产

---

## 8. 代码规范

**Python**：
- `ruff` lint + format
- 类型注解必须
- 服务层函数签名：`def do_thing(*, workspace_id: str, ...) -> Result`
- 业务异常用 `app/core/exceptions.py` 定义，不用裸 `Exception`

**TypeScript**：
- strict 模式
- API 调用统一走 `src/api/client.ts`
- 组合式函数放 `composables/`，不写 mixin

**Git**：
- 提交规范：`feat:` / `fix:` / `docs:` / `refactor:`
- 分支：`feature/xxx`、`fix/xxx`

---

## 9. 参考文档索引

| 需要了解 | 阅读 |
|----------|------|
| 业务需求全貌 | `docs/产品需求说明书_PRD.md` |
| 功能细节/流程 | `docs/产品功能说明书.md` |
| 提示词/规则/配置 | `docs/资源摘录_提示词与规则.md` |
| 技术架构/DDL/API | `docs/技术架构设计文档.md` |
| 现有系统源码 | 原仓库 `codex/phase-3-schema-dev` 分支 |

---

## 10. 禁止事项

- ❌ 不要把 API Key 写入代码或提交 Git
- ❌ 不要在图片上做任何格式转换/缩放/裁剪
- ❌ 不要用 UPDATE 修改已有的 QA 记录（只能 INSERT）
- ❌ 不要让人工复审放行硬技术失败
- ❌ 不要在生产环境开启 Swagger 文档
- ❌ 不要引入微服务/消息队列（除非明确要求）
- ❌ 不要硬编码业务规则（必须从资源 JSON 加载）
- ❌ 不要创建项目根目录以外的文件
