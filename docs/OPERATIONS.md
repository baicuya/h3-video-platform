# 运维手册

## 启动与停止全部服务

```bash
/home/ubuntu/workspace/h3-video-platform/scripts/start_all.sh
/home/ubuntu/workspace/h3-video-platform/scripts/stop_all.sh
```

基础依赖是 `postgresql`、`redis-server`；应用服务是 `h3-comfyui`、`h3-backend`、`h3-worker`、`h3-frontend`、`nginx`。均已配置开机自启。

## 健康与端口

```bash
scripts/healthcheck.sh
systemctl --failed
ss -lntp
curl -fsS http://127.0.0.1:8000/api/v1/health | jq
```

期望只有 80（以及运维 SSH 22）对公网监听；3000、8000、8188、5432、6379 必须显示为 `127.0.0.1` 或 `::1`。

## 检查 GPU

```bash
nvidia-smi
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits
```

CUDA OOM 时先停止继续入队，检查是否有外部 GPU 进程和 ComfyUI 日志；取消当前任务后重启 ComfyUI/worker。不要直接提高并发：

```bash
curl -b /path/to/admin-cookie -X POST http://127.0.0.1:8000/api/v1/admin/queue/pause
sudo systemctl restart h3-comfyui h3-worker
```

必要时降低分辨率/时长。确认服务稳定后恢复队列。

## 检查 ComfyUI

```bash
curl -fsS http://127.0.0.1:8188/system_stats | jq
curl -fsS http://127.0.0.1:8188/queue | jq
journalctl -u h3-comfyui -n 200 --no-pager
```

8188 永远不应改为 `0.0.0.0`。

## 检查队列

```bash
redis-cli LLEN h3:video_jobs
redis-cli LRANGE h3:video_jobs 0 -1
redis-cli GET h3:queue:paused
systemctl status h3-worker
journalctl -u h3-worker -n 200 --no-pager
```

管理后台可暂停/恢复“取出新任务”；正在执行的任务不会被粗暴删除。

## 日志

```bash
journalctl -u h3-comfyui -f
journalctl -u h3-backend -f
journalctl -u h3-worker -f
journalctl -u h3-frontend -f
journalctl -u nginx -f
```

避免把 `.env`、Cookie、JWT 或初始密码粘贴到工单。

## 清理失败任务

先备份数据库并确认目标数量：

```bash
psql h3_video_platform -c "SELECT count(*) FROM video_jobs WHERE status='failed';"
/home/ubuntu/workspace/h3-video-platform/scripts/backup.sh
psql h3_video_platform -c "DELETE FROM video_jobs WHERE status='failed';"
```

上述操作只清数据库记录；若还需清理对应输出，应先从查询结果取得明确文件路径逐个处理，不要对存储根目录递归删除。

## 备份与恢复

```bash
scripts/backup.sh
```

备份写入 `/home/ubuntu/backups/h3-video-platform/<UTC时间>`，包含 PostgreSQL custom dump、排除依赖/构建物的项目配置包及媒体包。恢复前停止 worker/backend，并在隔离环境验证：

```bash
pg_restore --clean --if-exists --dbname=h3_video_platform /path/to/database.dump
```

生产上还应把备份同步到独立存储并定期做恢复演练。

## 磁盘不足

```bash
df -h /home/ubuntu
du -sh /home/ubuntu/data/* /home/ubuntu/ComfyUI/output /home/ubuntu/backups/*
```

先暂停队列，归档旧备份和已确认可删除的历史输出。模型目录是统一唯一副本，不要误删模型或创建重复副本。任何清理前先依据数据库记录和完整路径复核。

## 数据库迁移与测试

```bash
cd /home/ubuntu/workspace/h3-video-platform/backend
DATABASE_URL='postgresql+asyncpg:///h3_video_platform?host=/var/run/postgresql' uv run alembic upgrade head
uv run pytest -q
```

## 临时公网与后续 HTTPS

当前统一入口为 AWS 公网 IPv4 的 HTTP 80，不依赖固定域名。2026-08-31 后若续费或迁移：

1. 将正式域名 A 记录指向届时服务器公网 IPv4并等待解析生效。
2. 用 `scripts/enable_https.sh <domain> [email]` 校验 DNS、修改 server_name 并调用 Certbot。
3. 把 `.env` 的 `PUBLIC_ORIGIN` 改为 `https://<domain>`、`COOKIE_SECURE=true`，并将 `TRUSTED_HOSTS` 限定为正式域名。
4. 重启 backend 和 Nginx，验证 HTTP 跳转、HTTPS 登录、WebSocket 与证书续期。

