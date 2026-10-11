# Custom Factory · 定制商品生产系统

面向定制商品（UV DTF 贴纸等）生产的全流程管控系统：从批次创建、SKU 分配、八槽位图片流水线、自动/人工质检，到复审放行、READY 门禁与三色生产保护，覆盖"接单 → 出图 → 质检 → 复审 → 可发布"的完整链路。

> 详细的产品需求与设计背景见 `docs/` 目录：
> - `产品需求说明书_PRD.md` —— 功能需求与验收标准
> - `产品功能说明书.md` —— 功能操作说明
> - `技术架构设计文档.md` —— 架构与数据模型设计
> - `资源摘录_提示词与规则.md` —— 业务规则 JSON 的来源摘录

---

## 目录

- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [方式一：Docker 一键启动（推荐）](#方式一docker-一键启动推荐)
- [方式二：本地裸机启动（无 Docker）](#方式二本地裸机启动无-docker)
- [默认账号](#默认账号)
- [环境变量说明](#环境变量说明)
- [测试与代码质量](#测试与代码质量)
- [生产部署](#生产部署)
- [常用 Make 命令](#常用-make-命令)
- [业务资源与指纹校验](#业务资源与指纹校验)
- [Codex Runner 内部接口](#codex-runner-内部接口)
- [常见问题 FAQ](#常见问题-faq)

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 |
| 数据库 | MySQL 8.0（本地开发可用 SQLite 免装） · Redis 7（预留，运行时非必需） |
| 前端 | Vue 3 · TypeScript · Vite 5 · Pinia · Vue Router · Element Plus · ECharts · Axios |
| 部署 | Docker Compose · Nginx（托管前端产物 + 反代 `/api`） |
| 质量工具 | pytest · ruff · vue-tsc · ESLint · Prettier |

核心后端分层：

```
backend/app/
├── main.py             FastAPI 入口（/api/v1 业务路由，/internal/runner 内部路由）
├── config.py           pydantic-settings 配置（读根目录或 backend 目录的 .env）
├── deps.py             认证 / 角色 / Runner 依赖注入
├── core/               数据库、安全（JWT/密码）、统一响应、异常体系、
│                       幂等键、哈希、存储、事件流水、资源加载
├── models/             21 张表的 SQLAlchemy 模型
├── schemas/            Pydantic 请求/响应模型
├── services/           业务逻辑（批次/SKU/标题/图片/质检/复审/READY/生产保护）
├── api/v1/             REST 路由（auth, workspaces, dashboard, batches, products,
│                       images, reviews, qa, guard, product-types）
├── api/runner/         Codex Runner 内部接口（仅本机回环 + 静态 Token）
└── resources/          业务规则 JSON（禁止硬编码，SHA-256 指纹锁定）
```

前端为 Soybean 风格分层：

```
frontend/
├── src/                页面、布局、路由、store、service、类型声明
├── packages/           内部共享包（@sa/axios 扁平化请求、@sa/hooks、@sa/utils、@sa/materials）
└── build/              Vite 插件装配
```

---

## 项目结构

```
factory/
├── backend/                # FastAPI 后端
│   ├── app/                # 应用代码
│   ├── alembic/            # 数据库迁移
│   ├── scripts/            # seed.py 种子数据 · verify_resources.py 资源指纹
│   ├── tests/              # pytest（含端到端冒烟测试）
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/               # Vue3 前端
│   ├── src/  packages/  build/
│   ├── vite.config.ts
│   ├── package.json        # 包管理器：pnpm
│   └── Dockerfile          # 三阶段：build / runtime(nginx) / dev
├── docs/                   # 产品与架构文档
├── nginx/conf.d/           # Nginx 反代配置
├── scripts/init-db.sh      # MySQL 容器初始化脚本
├── docker-compose.yml      # 生产编排（web + backend + mysql + redis）
├── docker-compose.dev.yml  # 开发编排（vite dev + uvicorn --reload）
├── Makefile                # 常用命令封装
└── .env.example            # 环境变量模板
```

---

## 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Docker + Docker Compose | Compose v2 | 方式一需要 |
| Node.js | >= 20.19 | 前端构建 / 本地开发 |
| pnpm | >= 9.5 | 前端包管理器（`npm i -g pnpm`） |
| Python | >= 3.11 | 方式二 / 跑测试需要 |
| MySQL 8.0 | 可选 | 本地开发可用 SQLite 代替 |

---

## 方式一：Docker 一键启动（推荐）

```bash
# 1. 准备环境变量
cp .env.example .env
# 编辑 .env：修改 SECRET_KEY / RUNNER_TOKEN / MYSQL_ROOT_PASSWORD / DB_PASSWORD

# 2. 构建并启动（backend + mysql + redis + web/nginx）
docker compose up -d --build

# 3. 初始化数据库 + 种子数据（seed 会自动建表并创建管理员）
docker compose exec backend python -m scripts.seed

# 4. 验证
curl http://localhost:38080/api/health    # {"code":0,...,"data":{"status":"ok"}}
```

打开 <http://localhost:38080> 即可使用（开发编排则是 <http://localhost:35173>）。

**开发模式**（前端热更新 + 后端 --reload）：

```bash
make dev        # 或: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
make dev-logs   # 跟踪日志
make down       # 停止
```

> 数据库迁移：首次由 seed 完成建表；后续模型变更时执行
> `docker compose exec backend alembic revision --autogenerate -m "说明"` 生成迁移，
> `docker compose exec backend alembic upgrade head` 应用。

---

## 方式二：本地裸机启动（无 Docker）

适合没有 Docker / MySQL 的环境，数据库用 SQLite。

### 1. 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

在**仓库根目录**创建 `.env`（backend 会自动读取根目录或 backend 目录下的 `.env`）：

```ini
ENVIRONMENT=development
DATABASE_URL=sqlite:///./data/cf_dev.db   # 无 MySQL 时用 SQLite；有 MySQL 则填 mysql+pymysql://...
STORAGE_ROOT=./data/images
PLAN_STORE_ROOT=./data/plans
CORS_ORIGINS=["http://localhost:35173","http://127.0.0.1:35173"]
```

启动并初始化：

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.seed    # 建表 + 种子数据（含管理员账号）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 38000
```

- 健康检查：<http://127.0.0.1:38000/api/health>
- Swagger：<http://127.0.0.1:38000/api/docs>（仅非生产环境开放）

### 2. 前端

```powershell
cd frontend
pnpm install
pnpm dev            # http://localhost:35173
```

Vite 开发服务器会把 `/api` 代理到 `http://127.0.0.1:38000`（可用 `VITE_PROXY_TARGET` 环境变量覆盖），
因此浏览器侧无跨域问题。

---

## 默认账号

种子脚本创建的管理员：

| 项 | 值 |
|---|---|
| 邮箱 | `admin@custom-factory.com` |
| 密码 | `Admin@123456` |
| 角色 | OWNER（Default Workspace） |

> 注意：旧版本的种子邮箱 `admin@custom-factory.local` 因 `.local` 是保留域名，
> 会被后端邮箱校验拒绝（422），已废弃，请使用 `.com` 邮箱。
> 生产环境务必更换 `SECRET_KEY` 并通过员工管理创建真实账号，不要使用种子账号。

---

## 环境变量说明

完整模板见 `.env.example`。后端通过 pydantic-settings 读取，敏感信息一律走环境变量，禁止入库入 Git。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `test` / `production`，生产下关闭 Swagger |
| `DATABASE_URL` | MySQL 连接串 | SQLAlchemy 连接串，本地开发可换成 `sqlite:///./data/cf_dev.db` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 10 / 20 | 连接池 |
| `REDIS_URL` | `redis://localhost:6379/0` | 预留，当前运行时非必需 |
| `SECRET_KEY` | 开发默认值 | JWT 签名密钥，**生产必须更换**（≥32 字符随机串） |
| `ACCESS_TOKEN_EXPIRE_HOURS` | 8 | 登录态有效期 |
| `RUNNER_TOKEN` | 开发默认值 | Codex Runner 内部接口静态 Token，**生产必须更换** |
| `STORAGE_ROOT` | `./data/images` | 图片资产存储根目录（强制位于项目根目录内） |
| `PLAN_STORE_ROOT` | `./data/plans` | 冻结计划（概念包）存储根目录 |
| `CORS_ORIGINS` | `["http://localhost:35173"]` | 允许的前端来源（JSON 数组或逗号分隔） |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | 空 | 图片生成 API 路线（可选） |
| `OCR_ENABLED` | `false` | 本地 OCR 运行时开关 |
| `TITLE_POOL_VERSION` | `1.3.0` | 标题池版本号 |
| `MYSQL_ROOT_PASSWORD` / `DB_PASSWORD` | — | 仅 Docker Compose 插值使用 |

Docker Compose 会自动读取仓库根目录 `.env` 做 `${...}` 插值；后端容器内的
`DATABASE_URL`/`STORAGE_ROOT` 等由 compose 显式注入，优先级高于 `.env` 文件。

---

## 测试与代码质量

```powershell
# 后端（47 个用例：单元 + 端到端链路 + API 冒烟，SQLite 运行，无需 MySQL）
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# 代码检查
cd backend; ruff check .; ruff format --check .
cd frontend; pnpm lint

# 前端类型检查 + 构建
cd frontend
pnpm typecheck
pnpm build
```

端到端测试覆盖：批次创建（幂等三层语义）→ SKU 连续分配 → 概念冻结 → 冻结计划 →
八槽位图片任务 → 上传/技术质检/OCR → 人工复审 → 修订级汇总 → 商品属性 → READY 门禁 → 事件流水。

---

## 生产部署

### 1. 标准部署（单机 Docker Compose）

```bash
cp .env.example .env
# 必改：SECRET_KEY、RUNNER_TOKEN、MYSQL_ROOT_PASSWORD、DB_PASSWORD（随机长字符串）
docker compose up -d --build
docker compose exec backend python -m scripts.seed     # 仅首次
```

架构：`web`（nginx 容器：前端静态资源 + `/api` 反代）→ `backend`（uvicorn:38000）→ `mysql` / `redis`。

- 前端产物在 `frontend/Dockerfile` 的 build 阶段内完成，部署机无需安装 Node。
- Nginx 配置见 `nginx/conf.d/default.conf`：SPA fallback、`/assets/` 长缓存、
  生产环境屏蔽 `/api/docs` 与 `/internal/`。
- Swagger 仅在 `ENVIRONMENT != production` 时由后端注册，与 Nginx 屏蔽形成双保险。

### 2. HTTPS

将证书放到 `nginx/ssl/`，并在 `nginx/conf.d/default.conf` 增加 443 server 块后
`docker compose restart web`（compose 已把该目录只读挂载进容器）。

### 3. 数据持久化与备份

| 路径 | 内容 |
|---|---|
| `data/mysql/` | MySQL 数据文件 |
| `data/redis/` | Redis 持久化 |
| `data/images/` | 图片资产（按 SKU/槽位落盘，含校验和） |
| `data/plans/` | 冻结计划包（概念快照 + SHA-256 信封） |

备份 = 备份以上目录 + 定期 `mysqldump`；升级前 `docker compose down`
（数据卷在宿主机目录，不会丢失）。

### 4. 升级流程

```bash
git pull
docker compose up -d --build          # 重建镜像
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.verify_resources   # 校验业务资源指纹
```

### 5. 健康检查与日志

```bash
curl http://localhost:38080/api/health
docker compose ps
docker compose logs -f backend
```

backend 容器自带 HEALTHCHECK（`/api/health`），web 容器检查 nginx 首页。

---

## 常用 Make 命令

| 命令 | 说明 |
|---|---|
| `make dev` / `make dev-logs` / `make down` | 启动 / 跟踪日志 / 停止开发环境 |
| `make up` / `make ps` / `make logs` | 生产环境启停与状态 |
| `make migrate` | 应用数据库迁移 |
| `make revision m="说明"` | 生成迁移脚本 |
| `make seed` | 导入种子数据 |
| `make seed-resources` | 重新生成业务资源 SHA-256 清单 |
| `make test` | 跑后端测试 |
| `make lint` / `make fmt` | 代码检查 / 格式化 |
| `make clean` | 清理本地持久化数据（**危险**） |

---

## 业务资源与指纹校验

业务规则（槽位角色、质检原因码、READY 条件、生产保护阈值等）全部以 JSON 形式存放在
`backend/app/resources/`，代码中禁止硬编码。启动/校验时按 `MANIFEST.json` 中的 SHA-256
逐个核对，防止规则被静默篡改：

```bash
python -m scripts.verify_resources    # 修改资源 JSON 后重新生成清单
```

---

## Codex Runner 内部接口

`/internal/runner/*` 供 Codex Runner（自动化出图执行器）调用，与业务 API 隔离：

- 仅接受本机回环（127.0.0.1 / ::1）请求，Nginx 层同时屏蔽外部访问；
- 认证方式：`X-Runner-Token`（与 `.env` 中 `RUNNER_TOKEN` 比对）+ `X-Workspace-Id`；
- 用于领取 SKU、提交图片产物、上报执行状态等机器侧动作。

---

## 常见问题 FAQ

**Q1：登录报 401？**
401 = 邮箱不存在或密码错误（见 `backend/app/api/v1/auth.py`）。请使用种子账号
`admin@custom-factory.com` / `Admin@123456`。旧邮箱 `admin@custom-factory.local`
是保留域名，会返回 422，永远无法登录。

**Q2：没有 Docker / MySQL 能跑吗？**
能。按[方式二](#方式二本地裸机启动无-docker)操作，`DATABASE_URL` 用 SQLite 即可；
Alembic 迁移与全部测试在 SQLite 下均可运行。

**Q3：前端请求全部 404 / 502？**
检查代理配置：本地开发由 Vite 把 `/api` 代理到后端（`vite.config.ts`，
默认 `http://127.0.0.1:38000`）；生产由 Nginx 反代（`nginx/conf.d/default.conf`）。
接口基址为 `/api/v1`（`VITE_SERVICE_BASE`）。

**Q4：`pnpm install` 报 engine 不兼容？**
项目要求 Node ≥ 20.19、pnpm ≥ 9.5（见 `frontend/package.json` 的 engines 字段）。

**Q5：端口被占用？**
后端 38000、前端 35173、Nginx 38080/38443、MySQL 33306、Redis 36379
（宿主机映射；容器内部分别是 38000 / 5173 / 80,443 / 3306 / 6379）。
可在 `docker-compose*.yml` 的 ports 段或 uvicorn/vite 启动参数中调整。

**Q6：图片和计划数据存在哪？**
`STORAGE_ROOT`（默认 `./data/images`）按 SKU/槽位目录落盘，每个资产带 SHA-256 校验和；
`PLAN_STORE_ROOT` 存概念冻结计划包。两目录均被强制限制在项目根目录内。

**Q7：如何重置开发环境？**
`make clean` 清空 MySQL/Redis/图片/计划数据；本地 SQLite 方式直接删除
`backend/data/cf_dev.db` 后重新执行 `python -m scripts.seed`。
