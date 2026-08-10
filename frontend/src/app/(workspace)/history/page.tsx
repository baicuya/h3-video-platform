"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { JobCard } from "@/components/job-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { PageResult, VideoJob } from "@/lib/types";

export default function HistoryPage() {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [mode, setMode] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: "12" });
    if (status) params.set("status", status);
    if (mode) params.set("mode", mode);
    if (search) params.set("query", search);
    try {
      const result = await api<PageResult<VideoJob>>(`/video-jobs?${params}`);
      setJobs(result.items);
      setTotal(result.total);
    } finally {
      setLoading(false);
    }
  }, [mode, page, search, status]);

  useEffect(() => { void load(); }, [load]);

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setSearch(query);
  }

  async function retry(job: VideoJob) {
    await api(`/video-jobs/${job.id}/retry`, { method: "POST" });
    await load();
  }

  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight text-slate-950">历史记录</h1>
      <p className="mt-2 text-sm text-slate-500">查找、播放和复用过去的生成任务。</p>
      <div className="mt-7 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:flex-row">
        <form className="relative flex-1" onSubmit={submitSearch}>
          <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <Input className="pl-10" placeholder="搜索 Prompt" value={query} onChange={(e) => setQuery(e.target.value)} />
        </form>
        <select className="h-11 rounded-xl border border-slate-200 bg-white px-3.5 text-sm text-slate-600 outline-none" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">全部状态</option><option value="queued">排队中</option><option value="running">生成中</option><option value="completed">已完成</option><option value="failed">失败</option><option value="cancelled">已取消</option>
        </select>
        <select className="h-11 rounded-xl border border-slate-200 bg-white px-3.5 text-sm text-slate-600 outline-none" value={mode} onChange={(e) => { setMode(e.target.value); setPage(1); }}>
          <option value="">全部模式</option><option value="t2v">文生视频 T2VA</option><option value="i2v">首尾帧 FL2VA</option><option value="ref2va">全能参考 Ref2VA</option>
        </select>
      </div>
      <p className="mt-5 text-xs text-slate-400">共 {total} 条任务</p>
      {loading ? (
        <div className="py-20 text-center text-sm text-slate-400">正在加载…</div>
      ) : jobs.length ? (
        <div className="mt-4 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{jobs.map((job) => <JobCard key={job.id} job={job} onRetry={retry} />)}</div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-300 py-20 text-center text-sm text-slate-400">没有符合条件的任务</div>
      )}
      {total > 12 && (
        <div className="mt-7 flex justify-center gap-2">
          <Button variant="outline" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>上一页</Button>
          <span className="grid min-w-12 place-items-center text-sm text-slate-500">{page}</span>
          <Button variant="outline" disabled={page * 12 >= total} onClick={() => setPage((value) => value + 1)}>下一页</Button>
        </div>
      )}
    </div>
  );
}
