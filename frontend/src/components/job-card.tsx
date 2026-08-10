"use client";

import Link from "next/link";
import { ArrowUpRight, Download, RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { VideoJob } from "@/lib/types";
import { formatDate, generationProfileLabel, modeLabel, statusLabel } from "@/lib/utils";

function tone(status: string): "neutral" | "success" | "warning" | "danger" | "accent" {
  if (status === "completed") return "success";
  if (status === "failed" || status === "cancelled") return "danger";
  if (status === "queued") return "warning";
  return "accent";
}

export function JobCard({
  job,
  onRetry,
}: {
  job: VideoJob;
  onRetry?: (job: VideoJob) => void;
}) {
  return (
    <article className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/60">
      <div className="aspect-video bg-slate-100">
        {job.status === "completed" && job.output_url ? (
          <video className="size-full object-cover" src={job.output_url} controls preload="metadata" />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-3 px-6 text-center">
            <span className="size-10 animate-pulse rounded-full bg-violet-100" />
            <span className="text-sm font-medium text-slate-500">{job.stage || statusLabel(job.status)}</span>
            {job.progress !== null && (
              <div className="h-1.5 w-full max-w-48 overflow-hidden rounded-full bg-slate-200">
                <div className="h-full rounded-full bg-violet-500" style={{ width: `${Math.round(job.progress * 100)}%` }} />
              </div>
            )}
          </div>
        )}
      </div>
      <div className="p-4">
        <div className="flex items-center justify-between gap-3">
          <Badge tone={tone(job.status)}>{statusLabel(job.status)}</Badge>
          <span className="text-xs text-slate-400">{formatDate(job.created_at)}</span>
        </div>
        <p className="mt-3 line-clamp-2 min-h-10 text-sm leading-5 text-slate-700">{job.prompt}</p>
        <p className="mt-3 text-xs text-slate-400">
          {modeLabel(job.mode)} · {generationProfileLabel(job.generation_profile)} · {job.aspect_ratio} · {job.duration_seconds}s
        </p>
        <div className="mt-4 flex items-center gap-1 border-t border-slate-100 pt-3">
          <Button asChild variant="ghost" size="sm">
            <Link href={`/task/${job.id}`}>
              查看 <ArrowUpRight className="size-3.5" />
            </Link>
          </Button>
          {job.output_url && (
            <Button asChild variant="ghost" size="sm">
              <a href={job.output_url} download>
                <Download className="size-3.5" /> 下载
              </a>
            </Button>
          )}
          {onRetry && (
            <Button variant="ghost" size="sm" onClick={() => onRetry(job)}>
              <RotateCcw className="size-3.5" /> 重试
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
