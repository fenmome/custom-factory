# syntax=docker/dockerfile:1
# 构建上下文为仓库根目录（docker-compose.yml 中已指定 context: .）

# ---------- 阶段一：构建前端产物 ----------
FROM node:20-alpine AS build
WORKDIR /app
RUN npm install -g pnpm@9
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/index.html frontend/vite.config.ts frontend/tsconfig.json ./
COPY frontend/build ./build
COPY frontend/packages ./packages
COPY frontend/src ./src
COPY frontend/.env* ./
RUN pnpm build

# ---------- 阶段二：生产运行时（nginx 托管 dist 并反代 /api） ----------
FROM nginx:alpine AS runtime
COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

# ---------- 阶段三：本地开发（vite dev server，配合 docker-compose.dev.yml） ----------
FROM node:20-alpine AS dev
WORKDIR /app
RUN npm install -g pnpm@9
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
