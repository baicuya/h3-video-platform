"use client";

import Image from "next/image";
import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { FileAudio, FileVideo, ImageIcon, LoaderCircle, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import type { Asset } from "@/lib/types";
import { formatDate } from "@/lib/utils";

type Category = {
  kind: Asset["kind"];
  title: string;
  description: string;
  emptyText: string;
  icon: typeof ImageIcon;
};

const categories: Category[] = [
  { kind: "image", title: "图片素材", description: "用于首帧、尾帧和画面参考", emptyText: "还没有图片素材", icon: ImageIcon },
  { kind: "video", title: "视频素材", description: "用于动作、镜头和视频参考", emptyText: "还没有视频素材", icon: FileVideo },
  { kind: "audio", title: "音频素材", description: "用于声音、音乐和节奏参考", emptyText: "还没有音频素材", icon: FileAudio },
];

function contentUrl(asset: Asset) {
  return `/api/v1/assets/${asset.id}/content`;
}

function MaterialPreview({ asset, onOpenImage }: { asset: Asset; onOpenImage: () => void }) {
  const url = contentUrl(asset);
  if (asset.kind === "image") {
    return (
      <button
        type="button"
        className="relative block aspect-video w-full cursor-zoom-in overflow-hidden bg-slate-100"
        onClick={onOpenImage}
        aria-label={`预览图片 ${asset.original_name}`}
      >
        <Image src={url} alt={asset.original_name} fill unoptimized className="object-cover transition duration-300 hover:scale-[1.03]" />
      </button>
    );
  }
  if (asset.kind === "video") {
    return <video src={url} controls preload="metadata" className="aspect-video w-full bg-slate-950 object-contain" />;
  }
  return (
    <div className="flex aspect-video flex-col items-center justify-center gap-5 bg-gradient-to-br from-violet-50 to-fuchsia-50 px-5">
      <span className="grid size-14 place-items-center rounded-2xl bg-white text-violet-600 shadow-sm">
        <FileAudio className="size-7" />
      </span>
      <audio src={url} controls preload="metadata" className="h-10 w-full" />
    </div>
  );
}

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [previewImage, setPreviewImage] = useState<Asset | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await api<{ items: Asset[] }>("/assets");
      setAssets(result.items);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "素材加载失败");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const kind = file.type.startsWith("image/") ? "images" : file.type.startsWith("video/") ? "videos" : "audio";
    const form = new FormData();
    form.append("file", file);
    setError("");
    setUploading(true);
    try {
      await api(`/assets/${kind}`, { method: "POST", body: form });
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "上传失败");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function remove(asset: Asset) {
    if (!window.confirm(`确定删除素材“${asset.original_name}”吗？`)) return;
    setError("");
    try {
      await api(`/assets/${asset.id}`, { method: "DELETE" });
      if (previewImage?.id === asset.id) setPreviewImage(null);
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "删除失败");
    }
  }

  return (
    <div>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-3xl font-semibold text-slate-950">素材</h1>
          <p className="mt-2 text-sm text-slate-500">分类管理并预览用于首尾帧和全能参考的图片、视频与音频素材。</p>
        </div>
        <Button asChild variant="accent">
          <label className={uploading ? "pointer-events-none opacity-60" : "cursor-pointer"}>
            {uploading ? <LoaderCircle className="size-4 animate-spin" /> : <Upload className="size-4" />}
            {uploading ? "正在上传…" : "上传素材"}
            <input className="sr-only" type="file" accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm,.wav,.mp3,.m4a,.flac" onChange={upload} disabled={uploading} />
          </label>
        </Button>
      </div>

      {error && <p className="mt-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}

      <div className="mt-8 space-y-10">
        {categories.map((category) => {
          const items = assets.filter((asset) => asset.kind === category.kind);
          const Icon = category.icon;
          return (
            <section key={category.kind}>
              <div className="mb-4 flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-violet-100 text-violet-700"><Icon className="size-5" /></span>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="font-semibold text-slate-900">{category.title}</h2>
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">{items.length}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">{category.description}</p>
                </div>
              </div>

              {items.length ? (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {items.map((asset) => (
                    <article key={asset.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40">
                      <MaterialPreview asset={asset} onOpenImage={() => setPreviewImage(asset)} />
                      <div className="flex items-center gap-3 p-4">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-slate-800" title={asset.original_name}>{asset.original_name}</p>
                          <p className="mt-1 text-xs text-slate-400">{(asset.size_bytes / 1024 / 1024).toFixed(2)} MB · {formatDate(asset.created_at)}</p>
                        </div>
                        <Button variant="ghost" size="icon" onClick={() => void remove(asset)} aria-label={`删除 ${asset.original_name}`}>
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-white/60 py-10 text-center text-sm text-slate-400">{category.emptyText}</div>
              )}
            </section>
          );
        })}
      </div>

      <Dialog open={Boolean(previewImage)} onOpenChange={(open) => { if (!open) setPreviewImage(null); }}>
        <DialogContent className="max-w-5xl bg-slate-950 p-3">
          <DialogTitle className="sr-only">{previewImage ? `预览 ${previewImage.original_name}` : "图片预览"}</DialogTitle>
          {previewImage && (
            <div className="relative flex max-h-[84vh] min-h-72 items-center justify-center overflow-hidden rounded-xl">
              <Image
                src={contentUrl(previewImage)}
                alt={previewImage.original_name}
                width={1600}
                height={1200}
                unoptimized
                className="max-h-[84vh] h-auto w-auto max-w-full object-contain"
              />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
