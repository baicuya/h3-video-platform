"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Copy, Download, LoaderCircle, RotateCcw, Trash2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import type { VideoJob } from "@/lib/types";
import { formatDate, generationProfileLabel, modeLabel, statusLabel } from "@/lib/utils";

export default function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [job, setJob] = useState<VideoJob | null>(null);
  const [message, setMessage] = useState("");
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  const [confirmAction, setConfirmAction] = useState<"retry" | "cancel" | "delete" | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState("");

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

  function requestAction(action: "retry" | "cancel" | "delete") {
    setActionError("");
    setConfirmAction(action);
  }
  async function executeAction() {
    if (!confirmAction) return;
    setActionBusy(true);
    setActionError("");
    try {
      if (confirmAction === "cancel") {
        await api(`/video-jobs/${id}/cancel`, { method: "POST" });
        setConfirmAction(null);
        await load();
      } else if (confirmAction === "retry") {
        const result = await api<{ id: string }>(`/video-jobs/${id}/retry`, { method: "POST" });
        router.push(`/task/${result.id}`);
      } else {
        await api(`/video-jobs/${id}`, { method: "DELETE" });
        router.push("/history");
      }
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "操作失败，请稍后重试");
    } finally {
      setActionBusy(false);
    }
  }

  const actionTitle = confirmAction === "retry" ? "重新生成" : confirmAction === "cancel" ? "取消任务" : "删除任务记录";
  const actionDescription = confirmAction === "retry"
    ? "将使用原任务的参数和参考素材创建一个新任务，并重新进入队列。"
    : confirmAction === "cancel"
      ? "任务会被中断，正在执行的 ComfyUI 推理也会停止；取消后不能继续，只能重新生成。"
      : "只删除这条已结束的任务记录；此操作不可撤销。";
  async function copyPrompt() {
    if (!job) return;
    try {
      let copied = false;
      if (navigator.clipboard && window.isSecureContext) {
        try {
          await navigator.clipboard.writeText(job.prompt);
          copied = true;
        } catch {
          copied = false;
        }
      }
      if (!copied) {
        const textarea = document.createElement("textarea");
        textarea.value = job.prompt;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        copied = document.execCommand("copy");
        textarea.remove();
        if (!copied) throw new Error("copy failed");
      }
      setCopyState("copied");
      setMessage("创意提示词已复制到剪贴板");
      window.setTimeout(() => { setCopyState("idle"); setMessage(""); }, 3000);
    } catch {
      setCopyState("error");
      setMessage("复制失败，浏览器未授予剪贴板权限");
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><Badge tone={job.status === "completed" ? "success" : job.status === "failed" ? "danger" : "accent"}>{statusLabel(job.status)}</Badge><h1 className="mt-3 text-2xl font-semibold text-slate-950">任务详情</h1><p className="mt-1 text-xs text-slate-400">{job.id}</p></div>
        <div className="flex flex-wrap gap-2">
          {!terminal && <Button variant="danger" onClick={() => requestAction("cancel")}><XCircle className="size-4" />取消任务</Button>}
          {terminal && <Button variant="outline" onClick={() => requestAction("retry")}><RotateCcw className="size-4" />重新生成</Button>}
          <Button variant="outline" onClick={copyPrompt}>
            {copyState === "copied" ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4" />}
            {copyState === "copied" ? "已复制" : "复制创意"}
          </Button>
          {terminal && <Button variant="danger" onClick={() => requestAction("delete")}><Trash2 className="size-4" />删除</Button>}
        </div>
      </div>
      {message && <p className={`mt-4 rounded-xl px-4 py-3 text-sm ${copyState === "error" ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>{message}</p>}
      <div className="mt-7 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="aspect-video bg-slate-950">
          {job.output_url ? <video className="size-full" controls autoPlay={false} src={job.output_url} /> : <div className="flex size-full flex-col items-center justify-center text-sm text-slate-400"><span>{job.stage || statusLabel(job.status)}</span>{job.progress !== null && <span className="mt-2">{Math.round(job.progress * 100)}%</span>}</div>}
        </div>
        <div className="p-6">
          <div className="flex items-start justify-between gap-5"><p className="max-w-3xl whitespace-pre-wrap text-sm leading-7 text-slate-700">{job.prompt}</p>{job.output_url && <Button asChild variant="outline"><a href={job.output_url} download><Download className="size-4" />下载视频</a></Button>}</div>
          <dl className="mt-7 grid gap-5 border-t border-slate-100 pt-6 text-sm sm:grid-cols-3">
            <div><dt className="text-xs text-slate-400">模式</dt><dd className="mt-1 font-medium">{modeLabel(job.mode)}</dd></div>
            <div><dt className="text-xs text-slate-400">规格</dt><dd className="mt-1 font-medium">{job.aspect_ratio} · {job.resolution} · {job.duration_seconds}s</dd></div>
            <div><dt className="text-xs text-slate-400">档位 / Steps</dt><dd className="mt-1 font-medium">{generationProfileLabel(job.generation_profile)} / {job.steps}</dd></div>
            <div><dt className="text-xs text-slate-400">创建时间</dt><dd className="mt-1 font-medium">{formatDate(job.created_at)}</dd></div>
            <div><dt className="text-xs text-slate-400">开始时间</dt><dd className="mt-1 font-medium">{formatDate(job.started_at)}</dd></div>
            <div><dt className="text-xs text-slate-400">完成时间</dt><dd className="mt-1 font-medium">{formatDate(job.finished_at)}</dd></div>
          </dl>
          {job.error_message && <div className="mt-6 rounded-xl bg-rose-50 p-4 text-sm text-rose-700">{job.error_code}: {job.error_message}</div>}
        </div>
      </div>

      <Dialog
        open={Boolean(confirmAction)}
        onOpenChange={(open) => {
          if (!open && !actionBusy) {
            setConfirmAction(null);
            setActionError("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{actionTitle}</DialogTitle>
            <DialogDescription>{actionDescription}</DialogDescription>
          </DialogHeader>
          {confirmAction === "retry" && (
            <div className="rounded-xl bg-violet-50 px-4 py-3 text-sm text-violet-700">
              新任务会产生新的任务 ID，原任务记录保持不变。
            </div>
          )}
          {confirmAction === "delete" && (
            <div className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
              删除后无法在历史记录中恢复这条任务。
            </div>
          )}
          {actionError && <p className="mt-3 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{actionError}</p>}
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" disabled={actionBusy} onClick={() => setConfirmAction(null)}>返回</Button>
            <Button
              variant={confirmAction === "retry" ? "accent" : "danger"}
              disabled={actionBusy}
              onClick={() => void executeAction()}
            >
              {actionBusy && <LoaderCircle className="size-4 animate-spin" />}
              {actionBusy ? "正在处理…" : `确认${actionTitle}`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
