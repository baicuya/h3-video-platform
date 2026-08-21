# API

基址为 `/api/v1`，WebSocket 使用 `/ws`。认证为 HttpOnly JWT Cookie（`h3_session`）；当前 HTTP 测试环境 `Secure=false`，切换 HTTPS 时必须改回 `true`。除登录和健康检查外均需认证；强制改密用户只能访问改密相关接口。

系统没有 `register` 接口。普通用户只能由管理员调用管理员账号接口创建，前端入口为 `/admin/users`。

## 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | 用户名密码登录；失败信息不区分账号不存在/密码错误；同账号/IP 失败限速 |
| POST | `/auth/logout` | 清除会话 Cookie |
| GET | `/auth/me` | 当前用户 |
| POST | `/auth/change-password` | 修改密码并递增会话版本，使旧会话失效 |

## 管理员账号

全部要求 `admin` 角色。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/admin/users` | 分页列表 / 开通账号 |
| GET/PATCH | `/admin/users/{id}` | 详情 / 修改显示名、角色、备注 |
| POST | `/admin/users/{id}/reset-password` | 重置密码并使旧会话失效 |
| POST | `/admin/users/{id}/enable` | 启用 |
| POST | `/admin/users/{id}/disable` | 禁用并使旧会话失效 |
| DELETE | `/admin/users/{id}` | 删除没有业务数据的账号 |

创建响应仅当次返回初始密码；管理员应通过安全渠道交付。普通用户首次登录由 `must_change_password` 强制改密。

## 素材

| 方法 | 路径 | 限制 |
|---|---|---|
| POST | `/assets/images` | JPG/PNG/WebP，最大 20MB |
| POST | `/assets/videos` | MP4/MOV/WebM，最大 500MB |
| POST | `/assets/audio` | WAV/MP3/M4A/FLAC，最大 100MB |
| GET | `/assets` | 仅当前用户素材 |
| DELETE | `/assets/{id}` | 删除有权访问的素材 |

扩展名、声明 MIME、大小均在服务端校验，文件使用 UUID 路径保存。

## 视频任务

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/video-jobs` | 创建任务并进入 Redis 队列 |
| GET | `/video-jobs` | 查询自己的任务；支持 status/mode/query/date/page |
| GET | `/video-jobs/{id}` | 任务详情 |
| POST | `/video-jobs/{id}/cancel` | 取消排队或运行任务 |
| POST | `/video-jobs/{id}/retry` | 创建新任务，保留 parent_job_id |
| DELETE | `/video-jobs/{id}` | 仅删除终态任务 |
| WS | `/ws/video-jobs/{id}` | Cookie 鉴权的状态更新 |

创建示例：

```json
{
  "mode": "ref2va",
  "model_variant": "int8",
  "prompt": "Use <Picture 1>, <Video 1> and <Audio 1> as references...",
  "duration_seconds": 5,
  "aspect_ratio": "16:9",
  "resolution": "480p",
  "seed": -1,
  "generation_profile": "turbo",
  "asset_ids": [
    "image-asset-uuid",
    "video-asset-uuid",
    "audio-asset-uuid"
  ]
}
```

`model_variant` 仅支持 `int8`，省略时默认使用 `int8`。`generation_profile` 由服务端映射为固定工作流参数：`turbo` 为 Turbo LoRA 8 步（默认、推荐），`fast` 为 Turbo LoRA 6 步，`quality` 为不加载 Turbo LoRA 的原始 20 步。API 不接受客户端自定义步数。

`resolution` 支持既有的 `480p`、`720p`、`768p`，以及高清 `1080p`。`1080p` 固定为 Turbo 8 步：前 2 步在约 768p 的 H3 AV latent 上采样，之后仅放大 video latent，并在目标尺寸以二采起始 sigma 重新加 video 噪声；audio latent 不缩放、以零噪声续采。目标尺寸 conditioning 使用同一条 sigma schedule 的剩余 6 步完成细节。最终输出为 16:9 的 1920×1080 或 9:16 的 1080×1920。非 Turbo 的 1080p 请求会返回 422。

`t2v` 不需要素材；`i2v` 接受一张首帧和可选的一张尾帧，顺序为首帧、尾帧；`ref2va` 最多接受 9 张图片、3 个视频、3 个音频，全部素材合计最多 12 个。参考视频总时长和参考音频总时长分别不能超过 15 秒，单个视频或音频不能短于 2 秒，且不能只上传音频。前后端都会执行同样的限制校验。任务数据和输出默认仅所有者可见，管理员可按后端授权规则查看详情。

Ref2VA 的 `asset_ids` 保留用户提交顺序，后端按素材类型映射到本机 ComfyUI prompt graph：

- 图片：`LoadImage -> MiniMaxH3ReferenceToVideo.ref_images.ref_image_N`
- 视频：`LoadVideo -> GetVideoComponents.images -> ref_videos.ref_video_N`
- 独立音频：`LoadAudio -> ref_audios.ref_audio_N`

项目当前不调用 `/v1/videos` 或 SGLang；实际生成请求发送到本机 ComfyUI `/prompt`。

## 系统

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | `/health` | 公开；DB、Redis、ComfyUI、GPU 状态 |
| GET | `/system/gpu` | 管理员 |
| GET | `/system/comfyui` | 管理员 |
| GET | `/system/queue` | 管理员 |
| POST | `/admin/queue/pause` | 管理员 |
| POST | `/admin/queue/resume` | 管理员 |

常见状态码：400 参数/业务错误，401 未登录，403 无权限或须先改密，404 资源不可见，409 状态冲突，413 过大，415 类型不支持，422 校验失败，429 登录限速，500 服务端错误。
