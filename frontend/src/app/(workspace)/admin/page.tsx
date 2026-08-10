"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, Cpu, Database, Gauge, HardDrive, MemoryStick, Pause, Play, Server } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatDate, modeLabel, statusLabel } from "@/lib/utils";

type GpuStatus = {
  name: string; vram_used_mb: number; vram_total_mb: number;
  utilization_percent: number; temperature_c: number;
  current_job: string | null; queue_length: number;
  cpu: { utilization_percent: number; logical_cores: number };
  memory: { total: number; used: number; available: number; utilization_percent: number };
  disk: { total: number; used: number; free: number; utilization_percent: number };
};
type QueueJob = {
  id: string;
  status: string;
  queue_position: number | null;
  queue_state: "running" | "waiting" | "recovering";
  mode: string;
  duration_seconds: number;
  aspect_ratio: string;
  resolution: string;
  width: number;
  height: number;
  created_at: string;
  started_at: string | null;
  user_id: string;
  username: string;
  display_name: string;
  user_role: string;
};
type QueueStatus = { paused: boolean; length: number; jobs: QueueJob[] };

export default function AdminPage() {
  const [gpu, setGpu] = useState<GpuStatus | null>(null);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [health, setHealth] = useState<Record<string, string> | null>(null);
  const load = useCallback(async () => {
    const [gpuResult, queueResult, healthResult] = await Promise.all([
      api<GpuStatus>("/system/gpu"), api<QueueStatus>("/system/queue"), api<Record<string, string>>("/health"),
    ]);
    setGpu(gpuResult); setQueue(queueResult); setHealth(healthResult);
  }, []);
  useEffect(() => { void load(); const timer = window.setInterval(load, 5000); return () => clearInterval(timer); }, [load]);
  async function toggleQueue() {
    await api(queue?.paused ? "/admin/queue/resume" : "/admin/queue/pause", { method: "POST" });
    await load();
  }
  const cards = gpu ? [
    { label: "CPU 利用率", value: `${gpu.cpu.utilization_percent.toFixed(1)}%`, detail: `${gpu.cpu.logical_cores} 个逻辑核心`, icon: Cpu },
    { label: "内存", value: `${(gpu.memory.used / 1024 ** 3).toFixed(1)} / ${(gpu.memory.total / 1024 ** 3).toFixed(1)} GB`, detail: `已使用 ${gpu.memory.utilization_percent.toFixed(1)}%`, icon: MemoryStick },
    { label: "GPU 利用率", value: `${gpu.utilization_percent}%`, detail: gpu.name, icon: Gauge },
    { label: "显存", value: `${(gpu.vram_used_mb / 1024).toFixed(1)} / ${(gpu.vram_total_mb / 1024).toFixed(1)} GB`, detail: `${gpu.temperature_c}°C`, icon: Activity },
    { label: "队列", value: String(gpu.queue_length), detail: gpu.current_job ? "正在生成" : "GPU 空闲", icon: Server },
    { label: "磁盘", value: `${(gpu.disk.used / 1024 ** 3).toFixed(0)} / ${(gpu.disk.total / 1024 ** 3).toFixed(0)} GB`, detail: `已使用 ${gpu.disk.utilization_percent.toFixed(1)}% · 剩余 ${(gpu.disk.free / 1024 ** 3).toFixed(0)} GB`, icon: HardDrive },
  ] : [];
  return (
    <div>
      <div className="flex items-end justify-between gap-4"><div><Badge tone="accent">管理员</Badge><h1 className="mt-3 text-3xl font-semibold text-slate-950">系统状态</h1><p className="mt-2 text-sm text-slate-500">CPU、内存、GPU、磁盘和队列实时概览。</p></div><Button variant={queue?.paused ? "accent" : "outline"} onClick={toggleQueue}>{queue?.paused ? <Play className="size-4" /> : <Pause className="size-4" />}{queue?.paused ? "恢复队列" : "暂停队列"}</Button></div>
      <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{cards.map((card) => <div key={card.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><span className="text-xs font-medium text-slate-400">{card.label}</span><card.icon className="size-4 text-violet-500" /></div><p className="mt-4 text-2xl font-semibold text-slate-950">{card.value}</p><p className="mt-1 truncate text-xs text-slate-400">{card.detail}</p></div>)}</div>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="flex items-center gap-2 font-semibold"><Database className="size-4 text-violet-500" />服务健康</h2><div className="mt-5 space-y-3">{health ? Object.entries(health).filter(([key]) => key !== "status").map(([key, value]) => <div key={key} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3"><span className="text-sm capitalize text-slate-600">{key}</span><Badge tone={value === "ok" ? "success" : "danger"}>{value}</Badge></div>) : <p className="text-sm text-slate-400">正在检查…</p>}</div></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">业务队列</h2><p className="mt-1 text-xs text-slate-400">{queue?.paused ? "队列已暂停，不会领取新任务" : "单 GPU 串行执行 · 包含运行中和等待中的任务"}</p><div className="mt-5 space-y-2">{queue?.jobs.length ? queue.jobs.map((job) => <div key={job.id} className="rounded-xl bg-slate-50 px-4 py-3"><div className="flex items-start gap-3"><span className="grid h-7 min-w-7 place-items-center rounded-full bg-white px-1 text-xs text-slate-500">{job.queue_state === "running" ? "运行" : job.queue_state === "recovering" ? "恢复" : job.queue_position}</span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="truncate font-mono text-xs text-slate-600">{job.id}</span><Badge tone={job.queue_state === "recovering" ? "danger" : job.status === "queued" ? "warning" : "accent"}>{job.queue_state === "recovering" ? "等待恢复" : statusLabel(job.status)}</Badge></div><p className="mt-2 text-sm font-medium text-slate-800">{job.display_name} <span className="font-normal text-slate-500">@{job.username}</span>{job.user_role === "admin" && <span className="ml-2 text-xs text-violet-600">管理员</span>}</p><p className="mt-1 text-xs text-slate-400">{modeLabel(job.mode)} · {job.duration_seconds} 秒 · 创建于 {formatDate(job.created_at)}{job.started_at ? ` · 开始于 ${formatDate(job.started_at)}` : ""}</p></div><div className="shrink-0 text-right"><p className="text-sm font-medium text-slate-700">{job.width}×{job.height}</p><p className="mt-1 text-xs text-slate-400">{job.aspect_ratio} · {job.resolution}</p></div></div></div>) : <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-sm text-slate-400">当前没有运行或排队任务</div>}</div></section>
      </div>
    </div>
  );
}
