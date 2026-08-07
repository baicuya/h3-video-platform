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
  "prompt": "Use <Picture 1> as the exact visual reference...",
  "duration_seconds": 5,
  "aspect_ratio": "16:9",
  "resolution": "480p",
  "seed": -1,
  "steps": 20,
  "asset_ids": ["image-asset-uuid"]
}
```

`t2v` 不需要素材；`i2v` 必须恰好使用首帧图片；当前 `ref2va` 只开放并强校验一张参考图片。任务数据和输出默认仅所有者可见，管理员可按后端授权规则查看详情。

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

