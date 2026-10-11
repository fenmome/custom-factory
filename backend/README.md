# Custom Factory Backend

FastAPI + SQLAlchemy 2.0 + Alembic + MySQL 8.0

## 目录

```
app/
├── main.py             FastAPI 入口
├── config.py           pydantic-settings 配置
├── deps.py             依赖注入
├── core/               基础设施（DB / 安全 / 存储 / 异常 / 事件 / 资源加载）
├── models/             SQLAlchemy 模型（21 张表）
├── schemas/            Pydantic 请求/响应模型
├── services/           业务逻辑层
├── api/v1/             REST 路由
├── api/runner/         Codex Runner 内部接口
├── providers/          外部服务适配（图片生成 / OCR）
└── resources/          业务规则 JSON（禁止硬编码，SHA-256 固定）
```

## 本地运行

```bash
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000
```

- 健康检查：`GET /api/health`
- Swagger（仅非生产）：`GET /api/docs`
