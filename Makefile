.PHONY: help dev dev-build up down build logs ps test migrate revision seed lint fmt seed-resources clean

DC = docker compose
DEV_FILES = -f docker-compose.yml -f docker-compose.dev.yml

help:  ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

dev:  ## 启动开发环境（前台带日志需用 make dev-logs）
	$(DC) $(DEV_FILES) up -d --build

dev-logs:  ## 查看开发环境日志
	$(DC) $(DEV_FILES) logs -f

up:  ## 启动生产环境
	$(DC) up -d --build

down:  ## 停止所有服务
	$(DC) $(DEV_FILES) down

ps:  ## 查看服务状态
	$(DC) $(DEV_FILES) ps

build:  ## 构建镜像
	$(DC) build

logs:  ## 查看日志
	$(DC) logs -f

test:  ## 运行后端测试
	$(DC) exec backend pytest -q

migrate:  ## 运行数据库迁移
	$(DC) exec backend alembic upgrade head

revision:  ## 生成迁移脚本（用法: make revision m="说明"）
	$(DC) exec backend alembic revision --autogenerate -m "$(m)"

seed:  ## 导入开发种子数据
	$(DC) exec backend python -m scripts.seed

seed-resources:  ## 校验业务资源 JSON 的 SHA-256 指纹
	$(DC) exec backend python -m scripts.verify_resources

lint:  ## 代码检查
	cd backend && ruff check . && ruff format --check .
	cd frontend && pnpm lint

fmt:  ## 代码格式化
	cd backend && ruff format . && ruff check --fix .

clean:  ## 清理本地持久化数据（危险）
	rm -rf data/mysql data/redis data/images/* data/plans/*
