"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, Database, Gauge, HardDrive, Pause, Play, Server } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type GpuStatus = {
  name: string; vram_used_mb: number; vram_total_mb: number;
  utilization_percent: number; temperature_c: number;
  current_job: string | null; queue_length: number;
  disk: { total: number; used: number; free: number };
};
type QueueStatus = { paused: boolean; length: number; jobs: string[] };

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
    { label: "GPU 利用率", value: `${gpu.utilization_percent}%`, detail: gpu.name, icon: Gauge },
    { label: "显存", value: `${(gpu.vram_used_mb / 1024).toFixed(1)} / ${(gpu.vram_total_mb / 1024).toFixed(1)} GB`, detail: `${gpu.temperature_c}°C`, icon: Activity },
    { label: "队列", value: String(gpu.queue_length), detail: gpu.current_job ? "正在生成" : "GPU 空闲", icon: Server },
    { label: "磁盘可用", value: `${(gpu.disk.free / 1024 ** 3).toFixed(0)} GB`, detail: `总计 ${(gpu.disk.total / 1024 ** 3).toFixed(0)} GB`, icon: HardDrive },
  ] : [];
  return (
    <div>
      <div className="flex items-end justify-between gap-4"><div><Badge tone="accent">管理员</Badge><h1 className="mt-3 text-3xl font-semibold text-slate-950">系统状态</h1><p className="mt-2 text-sm text-slate-500">GPU、队列和基础服务实时概览。</p></div><Button variant={queue?.paused ? "accent" : "outline"} onClick={toggleQueue}>{queue?.paused ? <Play className="size-4" /> : <Pause className="size-4" />}{queue?.paused ? "恢复队列" : "暂停队列"}</Button></div>
      <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map((card) => <div key={card.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><span className="text-xs font-medium text-slate-400">{card.label}</span><card.icon className="size-4 text-violet-500" /></div><p className="mt-4 text-2xl font-semibold text-slate-950">{card.value}</p><p className="mt-1 truncate text-xs text-slate-400">{card.detail}</p></div>)}</div>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="flex items-center gap-2 font-semibold"><Database className="size-4 text-violet-500" />服务健康</h2><div className="mt-5 space-y-3">{health ? Object.entries(health).filter(([key]) => key !== "status").map(([key, value]) => <div key={key} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3"><span className="text-sm capitalize text-slate-600">{key}</span><Badge tone={value === "ok" ? "success" : "danger"}>{value}</Badge></div>) : <p className="text-sm text-slate-400">正在检查…</p>}</div></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">业务队列</h2><p className="mt-1 text-xs text-slate-400">{queue?.paused ? "队列已暂停，不会领取新任务" : "单 GPU 串行执行"}</p><div className="mt-5 space-y-2">{queue?.jobs.length ? queue.jobs.map((id, index) => <div key={id} className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm"><span className="grid size-6 place-items-center rounded-full bg-white text-xs text-slate-500">{index + 1}</span><span className="truncate text-slate-600">{id}</span></div>) : <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-sm text-slate-400">当前没有排队任务</div>}</div></section>
      </div>
    </div>
  );
}
