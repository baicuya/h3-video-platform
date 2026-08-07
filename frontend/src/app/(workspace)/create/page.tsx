"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";
import { ChevronDown, ImagePlus, LoaderCircle, Sparkles, Upload, X } from "lucide-react";
import { JobCard } from "@/components/job-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { Asset, PageResult, VideoJob } from "@/lib/types";
import { cn } from "@/lib/utils";

const modes = [
  { id: "t2v", title: "文生视频", description: "只需一段描述，从零生成画面与声音", enabled: true },
  { id: "i2v", title: "图生视频", description: "上传首帧，让静态画面自然运动", enabled: true },
  { id: "ref2va", title: "全能参考", description: "单张参考图锁定主体、风格与场景", enabled: true },
] as const;

export default function CreatePage() {
  const [mode, setMode] = useState<"t2v" | "i2v" | "ref2va">("t2v");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(5);
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [resolution, setResolution] = useState("768p");
  const [seed, setSeed] = useState(-1);
  const [steps, setSteps] = useState(20);
  const [advanced, setAdvanced] = useState(false);
  const [asset, setAsset] = useState<Asset | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState<VideoJob[]>([]);

  const loadJobs = useCallback(async () => {
    try {
      const result = await api<PageResult<VideoJob>>("/video-jobs?page_size=6");
      setJobs(result.items);
    } catch {
      setJobs([]);
    }
  }, []);

  useEffect(() => {
    void loadJobs();
    const timer = window.setInterval(loadJobs, 5000);
    return () => window.clearInterval(timer);
  }, [loadJobs]);

  async function uploadImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    try {
      setAsset(await api<Asset>("/assets/images", { method: "POST", body: form }));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "图片上传失败");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (mode !== "t2v" && !asset) {
      setError(mode === "i2v" ? "图生视频需要先上传一张首帧图片" : "全能参考需要先上传一张参考图片");
      return;
    }
    setSubmitting(true);
    try {
      await api("/video-jobs", {
        method: "POST",
        body: JSON.stringify({
          mode,
          prompt,
          duration_seconds: duration,
          aspect_ratio: aspectRatio,
          resolution,
          seed,
          steps,
          asset_ids: asset ? [asset.id] : [],
        }),
      });
      setPrompt("");
      await loadJobs();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "任务提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="mb-7">
        <Badge tone="accent">创作空间</Badge>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">今天想创造什么？</h1>
        <p className="mt-2 text-sm text-slate-500">锦宿内部模型服务 · GPU 单并发排队执行</p>
      </div>
      <form onSubmit={submit} className="overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white shadow-xl shadow-slate-200/45">
        <div className="grid border-b border-slate-100 md:grid-cols-3">
          {modes.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={!item.enabled}
              onClick={() => item.enabled && setMode(item.id)}
              className={cn(
                "relative border-b border-slate-100 px-5 py-4 text-left transition last:border-0 md:border-b-0 md:border-r",
                mode === item.id ? "bg-violet-50/70" : "hover:bg-slate-50",
                !item.enabled && "cursor-not-allowed opacity-50",
              )}
            >
              <span className="block text-sm font-semibold text-slate-900">{item.title}</span>
              <span className="mt-1 block text-xs text-slate-400">{item.description}</span>
              {mode === item.id && <span className="absolute inset-x-5 bottom-0 h-0.5 rounded-full bg-violet-500" />}
            </button>
          ))}
        </div>
        <div className="p-5 md:p-7">
          {mode !== "t2v" && (
            <div className="mb-5">
              {asset ? (
                <div className="flex items-center gap-3 rounded-2xl border border-violet-200 bg-violet-50 p-3.5">
                  <span className="grid size-10 place-items-center rounded-xl bg-white text-violet-600"><ImagePlus className="size-5" /></span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-700">{asset.original_name}</span>
                  <Button type="button" variant="ghost" size="icon" onClick={() => setAsset(null)}><X className="size-4" /></Button>
                </div>
              ) : (
                <label className="flex cursor-pointer items-center justify-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-7 text-sm text-slate-500 transition hover:border-violet-300 hover:bg-violet-50">
                  {uploading ? <LoaderCircle className="size-5 animate-spin" /> : <Upload className="size-5" />}
                  {uploading ? "正在上传…" : mode === "i2v" ? "上传首帧图片 · JPG / PNG / WebP · 最大 20MB" : "上传参考图片 · 在提示词中用 <Picture 1> 引用 · 最大 20MB"}
                  <input className="sr-only" type="file" accept=".jpg,.jpeg,.png,.webp" onChange={uploadImage} disabled={uploading} />
                </label>
              )}
            </div>
          )}
          <textarea
            className="min-h-48 w-full resize-y border-0 bg-transparent text-lg leading-8 text-slate-800 outline-none placeholder:text-slate-300"
            placeholder={mode === "ref2va" ? "用 <Picture 1> 引用参考图，描述需要保留的主体、风格、动作、镜头与声音…" : "描述你想生成的视频内容、镜头运动、环境声音和整体氛围…"}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            maxLength={10000}
            required
          />
          {error && <p className="mb-4 rounded-xl bg-rose-50 px-3.5 py-3 text-sm text-rose-700">{error}</p>}
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-5">
            <label className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
              时长
              <select className="ml-2 bg-transparent font-medium text-slate-800 outline-none" value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                <option value={5}>5 秒</option><option value={10}>10 秒</option><option value={15}>15 秒</option>
              </select>
            </label>
            <label className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
              比例
              <select className="ml-2 bg-transparent font-medium text-slate-800 outline-none" value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
                <option>16:9</option><option>9:16</option><option>1:1</option><option>4:3</option><option>3:4</option>
              </select>
            </label>
            <label className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
              清晰度
              <select className="ml-2 bg-transparent font-medium text-slate-800 outline-none" value={resolution} onChange={(e) => setResolution(e.target.value)}>
                <option value="480p">480p</option><option value="720p">720p</option><option value="768p">768p</option>
              </select>
            </label>
            <button type="button" className="flex items-center gap-1 rounded-xl px-3 py-2 text-xs font-medium text-slate-500 hover:bg-slate-100" onClick={() => setAdvanced(!advanced)}>
              高级设置 <ChevronDown className={cn("size-3.5 transition", advanced && "rotate-180")} />
            </button>
            <Button className="ml-auto" variant="accent" size="lg" disabled={submitting || !prompt.trim()}>
              {submitting ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {submitting ? "提交中…" : "生成视频"}
            </Button>
          </div>
          {advanced && (
            <div className="mt-4 grid gap-4 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2">
              <label className="text-xs font-medium text-slate-500">Seed（-1 为随机）
                <input className="mt-2 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-violet-400" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
              </label>
              <label className="text-xs font-medium text-slate-500">Steps
                <input className="mt-2 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-violet-400" type="number" min={1} max={100} value={steps} onChange={(e) => setSteps(Number(e.target.value))} />
              </label>
            </div>
          )}
        </div>
      </form>
      <section className="mt-10">
        <div className="mb-4 flex items-end justify-between">
          <div><h2 className="text-lg font-semibold text-slate-900">最近生成</h2><p className="mt-1 text-xs text-slate-400">任务状态每 5 秒自动刷新</p></div>
        </div>
        {jobs.length ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{jobs.map((job) => <JobCard key={job.id} job={job} />)}</div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/55 py-16 text-center text-sm text-slate-400">还没有生成记录，提交第一个创意吧。</div>
        )}
      </section>
    </div>
  );
}

