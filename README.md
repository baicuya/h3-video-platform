# 锦宿 AI 视频工作台

基于 MiniMax H3、ComfyUI、FastAPI 与 Next.js 的内部视频生成平台。支持文生视频、图生视频，以及已真实验证的单参考图“全能参考”；视频由单 GPU worker 串行执行。系统没有用户注册入口，普通账号只能由管理员在“账号管理”页面开通。

当前临时入口：`http://54.89.116.205`。当前不依赖域名或 HTTPS；正式域名与证书是 2026-08-31 后的可选部署项。

## 架构

```text
浏览器 -> Nginx :80
              ├─ /       -> Next.js 127.0.0.1:3000
              ├─ /api/   -> FastAPI 127.0.0.1:8000
              ├─ /ws/    -> FastAPI WebSocket
              └─ /media/ -> /home/ubuntu/data

FastAPI -> PostgreSQL 127.0.0.1:5432
        -> Redis 127.0.0.1:6379
GPU worker -> ComfyUI 127.0.0.1:8188 -> NVIDIA GPU
```

只有 Nginx 80 和 SSH 22 监听公网。3000、8000、8188、5432、6379 均只监听回环地址。

## 目录

- `backend/`：FastAPI、Alembic、任务 worker、测试
- `frontend/`：Next.js App Router 管理台
- `workflows/`：经过 API 实测的 ComfyUI 工作流
- `deploy/`：systemd 与 Nginx 配置源文件
- `scripts/`：安装、模型下载、启停、健康检查、备份及可选 HTTPS
- `docs/`：部署、API、ComfyUI 和运维文档
- `/home/ubuntu/ComfyUI`：ComfyUI
- `/home/ubuntu/models/minimax-h3`：统一模型目录
- `/home/ubuntu/data`：上传与输出

## 安装

完整顺序和固定版本见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。已有服务器不应重复安装。

新机概要：

```bash
scripts/install_comfyui.sh
cd backend && uv sync
cd ../frontend && npm install && npm run build
scripts/download_models.sh
```

复制 `.env.example` 为 `.env`，生成 `APP_SECRET_KEY`，初始化 PostgreSQL/Alembic，然后安装 `deploy/systemd/*.service` 和 `deploy/nginx/h3-video-platform.conf`。初始管理员只能执行：

```bash
cd backend
.venv/bin/python -m app.cli create-admin
```

CLI 检测到已有管理员时会拒绝继续。没有注册 API 或注册页面。

## 启动与停止

```bash
scripts/start_all.sh
scripts/stop_all.sh
scripts/healthcheck.sh
```

服务开机自启。单独重启使用 `sudo systemctl restart h3-backend` 等命令。

## 更新

更新前先执行 `scripts/backup.sh`。后端变更后运行 Alembic、pytest；前端变更后重新生产构建；工作流或模型变更必须先通过本机 ComfyUI API 真实生成。

```bash
cd backend
uv sync
DATABASE_URL='postgresql+asyncpg:///h3_video_platform?host=/var/run/postgresql' uv run alembic upgrade head
uv run pytest -q

cd ../frontend
npm install
npm run lint
npm run build

sudo systemctl restart h3-backend h3-worker h3-frontend
```

## 日志

```bash
journalctl -u h3-comfyui -f
journalctl -u h3-backend -f
journalctl -u h3-worker -f
journalctl -u h3-frontend -f
journalctl -u nginx -f
```

## 故障排除

先运行 `scripts/healthcheck.sh`，再检查 `systemctl --failed`、worker/ComfyUI 日志、Redis 队列和 `nvidia-smi`。详细步骤见 [docs/OPERATIONS.md](docs/OPERATIONS.md)，模型与工作流说明见 [docs/COMFYUI.md](docs/COMFYUI.md)，接口见 [docs/API.md](docs/API.md)。

