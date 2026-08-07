# 锦宿 AI 视频工作台部署记录

执行日期：2026-08-07（UTC）。最终依据：`/home/ubuntu/md/minimax_h3_comfyui_web_codex_spec_v2.md`。各 Phase 按顺序执行，只有真实验收通过后才进入下一阶段。

## Phase 0：环境审计 — 通过

- Ubuntu 24.04.4 LTS，内核 7.0.0-1010-aws
- Python 3.12.3、uv 0.12.2、Git 2.43.0
- NVIDIA RTX PRO 6000 Blackwell Server Edition，驱动 595.71.05，显存 97887 MiB
- RAM 62GiB、Swap 63GiB；根卷 495GiB，审计时可用 425GiB
- 初始未发现 ComfyUI、H3 模型或工作流；项目根为 `/home/ubuntu/workspace/h3-video-platform`

## Phase 1：ComfyUI/CUDA/API — 通过

- 官方 ComfyUI 仓库，固定 Git `0ab8332bfa41c695b1c104a6535ff1fde81c7939`
- ComfyUI 0.30.0，独立 uv 环境 `/home/ubuntu/ComfyUI/.venv`
- PyTorch 2.13.0+cu130；CUDA tensor 实测成功并识别 Blackwell GPU
- `/system_stats` 正常；仅绑定 `127.0.0.1:8188`

## Phase 2：H3 INT8 T2V — 通过

模型源 `Comfy-Org/MiniMax-H3`，固定 revision `eb8a16107c595128b3a578f82d2ce2f75920c355`。统一目录 `/home/ubuntu/models/minimax-h3`，ComfyUI 通过额外模型路径引用。

| 文件 | bytes | SHA-256 |
|---|---:|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 20970379616 | `e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 15687142551 | `35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6` |
| `minimax_h3_video_vae_fp16.safetensors` | 5207808496 | `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522` |
| `minimax_h3_audio_vae_fp32.safetensors` | 605254808 | `8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48` |

工作流 `h3_t2v_int8.json`；真实 prompt `beba7047-469d-4897-9599-d38196605ed2`，状态 success，首次 132.41 秒。输出 H.264 608×352@24fps、AAC 32kHz 双声道、5.167 秒。

## Phase 3：H3 INT8 I2V — 通过

将 T2V 首帧真实上传至 ComfyUI `/upload/image`，工作流 `h3_i2v_int8.json` 的 LoadImage 动态引用该文件。prompt `b0d357a5-0b08-4372-840c-efc3ebbb6c4e`，状态 success，热启动 30.50 秒；历史记录证明采样节点实际执行。输出 H.264 608×352@24fps、AAC 双声道、5.167 秒。

## Phase 4：无 UI API 脚本 — 通过

- `scripts/comfyui_test_client.py`
- `scripts/test_comfyui_t2v.py`：prompt `2ae85d69-6153-4a07-b546-1a907add3e40`
- `scripts/test_comfyui_i2v.py`：prompt `6e7dac24-cbb6-4789-bb7e-c30be1fae542`

脚本完成健康检查、上传、`POST /prompt`、history 轮询和输出解析，两种模式均真实成功。

## Phase 5：FastAPI/数据/任务队列 — 通过

- PostgreSQL 16.14、Redis 7.0.15，仅监听回环
- SQLAlchemy async + Alembic，迁移 `707a748fc7ac_create_users_assets_video_jobs.py` 已应用
- Argon2id、JWT HttpOnly Cookie、会话版本强制失效、登录限速与统一失败信息
- 没有注册路由；初始管理员仅能用 CLI 创建；普通账号仅能由 `/admin/users` 后台开通
- 用户/角色/启停/重置密码/素材/私有任务/取消/重试/系统健康 API 完成
- Redis 队列、GPU 锁和单 worker；ComfyUI adapter 支持 HTTP、WebSocket、上传、中断和输出拉取
- 最终后端全量测试：10 passed

## Phase 6：Next.js 工作台 — 通过

- Next.js 16.3.0、React 19.2.8、Tailwind CSS 4.3.3
- 页面：login、change-password、create、history、task detail、assets、admin、admin/users
- 无 register/signup 页面；登录页明确“账号由管理员统一开通”
- 管理员页面支持开通账号、初始密码仅显示一次、重置、禁用、启用、角色与删除
- 最终 `npm run lint` 和 `npm run build` 通过；TypeScript 通过

## Phase 7：临时公网 IPv4 HTTP 部署 — 通过

用户于实施期间明确当前为 2026-08-31 前临时内部测试环境，因此本 Phase 的最终口径替换为不绑定域名、不依赖 HTTPS：

- 统一公网入口：`http://54.89.116.205`，实测 `/login` 返回 HTTP 200
- Nginx 1.24 监听 `0.0.0.0:80` / `[::]:80`，`server_name _`
- Next.js 3000、FastAPI 8000、ComfyUI 8188、PostgreSQL 5432、Redis 6379 均只监听回环
- systemd 服务 `h3-comfyui`、`h3-backend`、`h3-worker`、`h3-frontend`、`nginx` 均 active 且开机自启
- Nginx 反代 API/WebSocket/前端，并以最小 ACL 读取 `/home/ubuntu/data`
- `COOKIE_SECURE=false` 仅用于当前 HTTP；TrustedHost 不依赖域名
- Certbot 已安装但未签发证书、未改 Nginx；`scripts/enable_https.sh` 作为以后显式执行的可选项
- 空队列 worker 使用原生阻塞等待；共享 Redis 客户端显式设置 `socket_timeout=None`、连接超时 5 秒，修复 redis-py 默认 5 秒读超时导致的误重启

当时正式域名 `ai-psy.shlzjin.cn` 解析为 `47.116.38.96`，与本机 `54.89.116.205` 不同，因此没有错误签发或绑定。

## Phase 8：Ref2VA 渐进增强 — 通过

下载独立权重 `minimax_h3_ref2va_pruned_int8_convrot.safetensors`（20970379616 bytes），SHA-256：

`9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779`

使用官方本地节点 `MiniMaxH3ReferenceToVideo` 创建 `h3_ref2va_int8.json`。单参考图真实 prompt `3ce227de-8531-4cdb-ac8f-69474321d282`，状态 success，首次 181.80 秒。输出 H.264 608×352@24fps、AAC 32kHz 双声道、5.167 秒。

后端和 UI 仅开放已验证的单参考图，提示词使用 `<Picture 1>`；多图、参考视频和参考音频保持隐藏。支持矩阵见 `docs/COMFYUI.md`。

平台级端到端验收经公网 Nginx 上传素材并创建任务 `47fbbf8f-b228-48ce-bbe7-438fdccecc39`，worker 对应 ComfyUI prompt `528b95a1-227a-46ff-b63d-619a4bf7e3f4`。任务完成并写入用户隔离目录；公网媒体返回 200，输出为 H.264 864×480@24fps、AAC 32kHz 双声道、5.167 秒。

## 最终验收

- `scripts/healthcheck.sh`：DB、Redis、ComfyUI、GPU 及 Nginx 全部通过
- 后端测试：10 passed
- 前端 lint/build：通过
- 管理员 `admin` 已通过 CLI 创建；公网 Cookie 登录与管理员用户列表实测通过
- `/register` 与 `/api/v1/auth/register` 均为 404
- 当前服务入口：`http://54.89.116.205`
- 普通用户账号必须由管理员登录后在 `/admin/users` 开通


