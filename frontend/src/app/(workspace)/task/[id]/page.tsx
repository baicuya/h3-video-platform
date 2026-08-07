"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Download, RotateCcw, Trash2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { VideoJob } from "@/lib/types";
import { formatDate, modeLabel, statusLabel } from "@/lib/utils";

export default function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [job, setJob] = useState<VideoJob | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setJob(await api<VideoJob>(`/video-jobs/${id}`));
  }, [id]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!job) return <div className="py-20 text-center text-sm text-slate-400">正在加载任务…</div>;
  const terminal = ["completed", "failed", "cancelled"].includes(job.status);

  async function cancel() {
    if (!window.confirm("中断当前任务可能导致模型进入清理阶段。确认取消？")) return;
    await api(`/video-jobs/${id}/cancel`, { method: "POST" });
    await load();
  }
  async function retry() {
    const result = await api<{ id: string }>(`/video-jobs/${id}/retry`, { method: "POST" });
    router.push(`/task/${result.id}`);
  }
  async function remove() {
    if (!window.confirm("确认删除这条任务记录？")) return;
    await api(`/video-jobs/${id}`, { method: "DELETE" });
    router.push("/history");
  }
  async function copyParams() {
    await navigator.clipboard.writeText(JSON.stringify({
      mode: job?.mode, prompt: job?.prompt, duration_seconds: job?.duration_seconds,
      aspect_ratio: job?.aspect_ratio, resolution: job?.resolution, seed: job?.seed, steps: job?.steps,
    }, null, 2));
    setMessage("参数已复制");
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><Badge tone={job.status === "completed" ? "success" : job.status === "failed" ? "danger" : "accent"}>{statusLabel(job.status)}</Badge><h1 className="mt-3 text-2xl font-semibold text-slate-950">任务详情</h1><p className="mt-1 text-xs text-slate-400">{job.id}</p></div>
        <div className="flex flex-wrap gap-2">
          {!terminal && <Button variant="danger" onClick={cancel}><XCircle className="size-4" />取消任务</Button>}
          {terminal && <Button variant="outline" onClick={retry}><RotateCcw className="size-4" />重新生成</Button>}
          <Button variant="outline" onClick={copyParams}><Copy className="size-4" />复制参数</Button>
          {terminal && <Button variant="danger" onClick={remove}><Trash2 className="size-4" />删除</Button>}
        </div>
      </div>
      {message && <p className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</p>}
      <div className="mt-7 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="aspect-video bg-slate-950">
          {job.output_url ? <video className="size-full" controls autoPlay={false} src={job.output_url} /> : <div className="flex size-full flex-col items-center justify-center text-sm text-slate-400"><span>{job.stage || statusLabel(job.status)}</span>{job.progress !== null && <span className="mt-2">{Math.round(job.progress * 100)}%</span>}</div>}
        </div>
        <div className="p-6">
          <div className="flex items-start justify-between gap-5"><p className="max-w-3xl whitespace-pre-wrap text-sm leading-7 text-slate-700">{job.prompt}</p>{job.output_url && <Button asChild variant="outline"><a href={job.output_url} download><Download className="size-4" />下载视频</a></Button>}</div>
          <dl className="mt-7 grid gap-5 border-t border-slate-100 pt-6 text-sm sm:grid-cols-3">
            <div><dt className="text-xs text-slate-400">模式</dt><dd className="mt-1 font-medium">{modeLabel(job.mode)}</dd></div>
            <div><dt className="text-xs text-slate-400">规格</dt><dd className="mt-1 font-medium">{job.aspect_ratio} · {job.resolution} · {job.duration_seconds}s</dd></div>
            <div><dt className="text-xs text-slate-400">Seed / Steps</dt><dd className="mt-1 font-medium">{job.seed} / {job.steps}</dd></div>
            <div><dt className="text-xs text-slate-400">创建时间</dt><dd className="mt-1 font-medium">{formatDate(job.created_at)}</dd></div>
            <div><dt className="text-xs text-slate-400">开始时间</dt><dd className="mt-1 font-medium">{formatDate(job.started_at)}</dd></div>
            <div><dt className="text-xs text-slate-400">完成时间</dt><dd className="mt-1 font-medium">{formatDate(job.finished_at)}</dd></div>
          </dl>
          {job.error_message && <div className="mt-6 rounded-xl bg-rose-50 p-4 text-sm text-rose-700">{job.error_code}: {job.error_message}</div>}
        </div>
      </div>
    </div>
  );
}
