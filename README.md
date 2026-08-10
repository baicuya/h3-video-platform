# 锦宿 AI 视频工作台

基于 MiniMax H3、ComfyUI、FastAPI 与 Next.js 的内部视频生成平台。支持文生视频、首尾帧视频，以及图片/视频/音频混合的“全能参考”；视频由单 GPU worker 串行执行。系统没有用户注册入口，普通账号只能由管理员在“账号管理”页面开通。

## 访问入口（先看这里）

当前公网入口：**[http://54.89.116.205](http://54.89.116.205)**

打开首页会自动跳转到登录页。当前使用临时公网 IP 和 HTTP，不依赖域名或 HTTPS；正式域名与证书是 2026-08-31 后的可选部署项。

| 页面 | 公网地址 | 说明 |
| --- | --- | --- |
| 登录 | [http://54.89.116.205/login](http://54.89.116.205/login) | 所有用户从这里登录 |
| 创建视频 | [http://54.89.116.205/create](http://54.89.116.205/create) | 文生视频、图生视频、全能参考 |
| 任务历史 | [http://54.89.116.205/history](http://54.89.116.205/history) | 查看任务状态和生成结果 |
| 素材库 | [http://54.89.116.205/assets](http://54.89.116.205/assets) | 查看和管理上传素材 |
| 管理后台 | [http://54.89.116.205/admin](http://54.89.116.205/admin) | 仅管理员可访问 |
| 账号管理 | [http://54.89.116.205/admin/users](http://54.89.116.205/admin/users) | 管理员开通、停用或重置普通账号 |

系统不提供自助注册。管理员账号已在服务器初始化，登录凭据不写入 Git 或 README；请向系统管理员获取。普通用户由管理员登录后在“账号管理”中开通，首次登录后按页面提示修改密码。

### 内部服务地址

以下地址只监听服务器的 `127.0.0.1`，不能从公网直接打开：

| 服务 | 本机地址 | 用途 |
| --- | --- | --- |
| Next.js | `http://127.0.0.1:3000` | 前端应用 |
| FastAPI | `http://127.0.0.1:8000` | 后端 API |
| 后端健康检查 | `http://127.0.0.1:8000/api/v1/health` | 正常时返回 HTTP 200 |
| ComfyUI | `http://127.0.0.1:8188` | 视频生成引擎，仅供内部调用 |
| PostgreSQL | `127.0.0.1:5432` | 数据库 |
| Redis | `127.0.0.1:6379` | 队列与状态 |

如果公网入口打不开，先登录服务器运行：

```bash
cd /home/ubuntu/workspace/h3-video-platform
scripts/healthcheck.sh
sudo systemctl status h3-comfyui h3-backend h3-worker h3-frontend nginx --no-pager
```

## 模型精度

所有生成模式统一使用 MiniMax H3 INT8 模型，以降低显存占用并保持单 GPU 服务稳定。创建页可切换三种服务端固定档位：默认 Turbo 8 步、极速 6 步和原始高质量 20 步；前两档加载 MiniMax H3 Turbo LoRA，高质量档保持原工作流。

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
