"use client";

import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { FileAudio, FileVideo, ImageIcon, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { Asset } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const result = await api<{ items: Asset[] }>("/assets");
    setAssets(result.items);
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const kind = file.type.startsWith("image/") ? "images" : file.type.startsWith("video/") ? "videos" : "audio";
    const form = new FormData();
    form.append("file", file);
    try {
      await api(`/assets/${kind}`, { method: "POST", body: form });
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "上传失败");
    }
    event.target.value = "";
  }
  async function remove(id: string) {
    await api(`/assets/${id}`, { method: "DELETE" });
    await load();
  }
  const icons = { image: ImageIcon, video: FileVideo, audio: FileAudio };

  return (
    <div>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><h1 className="text-3xl font-semibold text-slate-950">素材</h1><p className="mt-2 text-sm text-slate-500">管理用于首尾帧和全能参考的图片、视频与音频素材。</p></div>
        <Button asChild variant="accent"><label className="cursor-pointer"><Upload className="size-4" />上传素材<input className="sr-only" type="file" accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm,.wav,.mp3,.m4a,.flac" onChange={upload} /></label></Button>
      </div>
      {error && <p className="mt-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <div className="mt-7 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        {assets.length ? assets.map((asset) => {
          const Icon = icons[asset.kind];
          return <div key={asset.id} className="flex items-center gap-4 border-b border-slate-100 p-4 last:border-0"><span className="grid size-11 place-items-center rounded-xl bg-slate-100 text-slate-500"><Icon className="size-5" /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-slate-800">{asset.original_name}</p><p className="mt-1 text-xs text-slate-400">{(asset.size_bytes / 1024 / 1024).toFixed(2)} MB · {formatDate(asset.created_at)}</p></div><Button variant="ghost" size="icon" onClick={() => remove(asset.id)}><Trash2 className="size-4" /></Button></div>;
        }) : <div className="py-20 text-center text-sm text-slate-400">还没有上传素材</div>}
      </div>
    </div>
  );
}

