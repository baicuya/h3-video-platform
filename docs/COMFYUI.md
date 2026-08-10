# ComfyUI 与 MiniMax H3

## 固定版本

- ComfyUI：0.30.0，Git `0ab8332bfa41c695b1c104a6535ff1fde81c7939`
- workflow templates：0.11.31
- PyTorch：2.13.0+cu130
- SageAttention：2.2.0，Git `eb615cf6cf4d221338033340ee2de1c37fbdba4a`，针对 Blackwell `sm_120` 编译
- 模型仓库：`Comfy-Org/MiniMax-H3`
- 模型 revision：`93acf8c91365d40dc32a3abd19af06df6b6f7c65`
- ComfyUI：`127.0.0.1:8188`，禁止公网直连

模型只保存在 `/home/ubuntu/models/minimax-h3`，通过 `/home/ubuntu/ComfyUI/extra_model_paths.yaml` 引用。

## 生产加速配置

- ComfyUI 使用 `--gpu-only --use-sage-attention` 启动；本机 98 GB VRAM 足以让单任务模型常驻 GPU。
- T2V、I2V、Ref2VA 的 INT8 工作流保持 eager 执行；不要接入 `TorchCompileModel`，否则 `comfy_kitchen` 的 INT8 CUDA 算子会在 Dynamo FakeTensor 跟踪期间调用 `__dlpack__` 并失败。
- SageAttention 依赖 CUDA 13.0 编译器及 cuBLAS、cuSPARSE、cuSOLVER 开发库。升级 PyTorch、CUDA 或 GPU 架构后必须重新编译该扩展。

## 模型校验

| 模型 | SHA-256 |
|---|---|
| FL2VA INT8 ConvRot | `e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a` |
| Ref2VA INT8 ConvRot | `9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779` |
| Qwen3-VL 32B NVFP4 AWQ | `35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6` |
| Video VAE FP16 | `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522` |
| Audio VAE FP32 | `8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48` |

## 支持矩阵

| 模式/输入 | 状态 | 工作流 | 说明 |
|---|---|---|---|
| 文生视频 | 已开放、真实通过 | `h3_t2v_int8.json` | FL2VA INT8，原生视频+立体声音频 |
| 图生视频首帧 | 已开放、真实通过 | `h3_i2v_int8.json` | 动态上传到 LoadImage |
| Ref2VA 多素材 | 已开放 | `h3_ref2va_int8.json` | 最多 9 图、3 视频、3 音频，总素材最多 12 个 |
| Ref2VA 多参考图 | 未开放 | 官方节点支持 | 尚未独立做端到端产品验收 |
| Ref2VA 参考视频 | 未开放 | 官方节点支持 | 页面隐藏，不伪实现 |
| Ref2VA 参考音频 | 未开放 | 官方节点支持 | 页面隐藏，不伪实现 |

官方本地节点接受最多 9 张参考图、3 段参考视频和 3 段独立音频。平台按同类型顺序映射为 `<Picture N>`、`<Video N>`、`<Audio N>`；参考视频和参考音频各自总时长最多 15 秒，图片、视频、音频合计最多 12 个。

## 真实验收

- T2V：prompt `beba7047-469d-4897-9599-d38196605ed2`，132.41 秒
- I2V：prompt `b0d357a5-0b08-4372-840c-efc3ebbb6c4e`，30.50 秒
- Phase 4 API T2V：`2ae85d69-6153-4a07-b546-1a907add3e40`
- Phase 4 API I2V：`6e7dac24-cbb6-4789-bb7e-c30be1fae542`
- Ref2VA 单图（多素材链路以自动化请求图测试覆盖，尚未做真实 GPU 混合素材验收）：`3ce227de-8531-4cdb-ac8f-69474321d282`，冷启动 181.80 秒
- 公网平台端到端 Ref2VA：任务 `47fbbf8f-b228-48ce-bbe7-438fdccecc39`，ComfyUI prompt `528b95a1-227a-46ff-b63d-619a4bf7e3f4`

Ref2VA 输出经 `ffprobe`：H.264 608×352 24fps、AAC 32kHz 双声道、5.167 秒。

## 工作流参数化

当前生产链路不调用 `/v1/videos` 或 SGLang；后端上传素材到本机 ComfyUI `/upload/image`，然后向 `/prompt` 提交 prompt graph。云端 Hailuo H3 的请求 schema 仅作为字段语义对照，不混入本地工作流。

`WorkflowService` 每次深复制 JSON，根据固定 node map 写入 prompt、尺寸、帧数、seed、steps、输出前缀和已上传图片名。后端会先确认关键节点存在；不会用字符串全局替换，也不接受用户提交任意 workflow。

帧数按 24fps 并对齐 H3 的 17 帧步长。worker 固定单并发，以 Redis 锁保护 GPU。生产输出由 ComfyUI 拉回后保存到 `/home/ubuntu/data/outputs/{user_id}/{job_id}.mp4`。

## 手工检查

```bash
curl -fsS http://127.0.0.1:8188/system_stats | jq
curl -fsS http://127.0.0.1:8188/queue | jq
journalctl -u h3-comfyui -f
nvidia-smi
```

Phase 4 脚本：

```bash
backend/.venv/bin/python scripts/test_comfyui_t2v.py
backend/.venv/bin/python scripts/test_comfyui_i2v.py /path/to/image.png
backend/.venv/bin/python scripts/test_comfyui_ref2va.py /path/to/image.png
```
