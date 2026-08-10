"use client";

import { ChangeEvent, Dispatch, FormEvent, SetStateAction, useCallback, useEffect, useState } from "react";
import Image from "next/image";
import {
  Check,
  ChevronDown,
  FileAudio,
  FileVideo,
  FolderOpen,
  ImagePlus,
  LoaderCircle,
  Sparkles,
  Trash2,
} from "lucide-react";
import { JobCard } from "@/components/job-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import type { Asset, GenerationProfile, PageResult, VideoJob } from "@/lib/types";
import { cn } from "@/lib/utils";

type Mode = "t2v" | "i2v" | "ref2va";
type AssetKind = Asset["kind"];
type TailSeconds = 5 | 10 | 15;
type SelectedAsset = {
  asset: Asset;
  previewUrl: string;
  durationSeconds: number | null;
};
type PickerTarget = { scope: "fl2va" | "ref"; kind: AssetKind };
type StoredAsset = { asset: Asset; durationSeconds: number | null };
type CreateDraft = {
  mode: Mode;
  prompt: string;
  duration: number;
  aspectRatio: string;
  resolution: string;
  generationProfile: GenerationProfile;
  seed: number;
  steps?: number;
  advanced: boolean;
  videoTailSeconds: TailSeconds;
  fl2vaAssets: StoredAsset[];
  refAssets: StoredAsset[];
};

const CREATE_DRAFT_KEY = "h3:create-draft:v1";

const modes = [
  { id: "t2v", title: "文生视频 T2VA", description: "只需一段描述，从零生成画面与声音" },
  { id: "i2v", title: "首尾帧 FL2VA", description: "首帧必选、尾帧可选，控制镜头起止画面" },
  { id: "ref2va", title: "全能参考 Ref2VA", description: "组合图片、视频和音频参考生成完整视听内容" },
] as const;

const generationProfiles = [
  { id: "turbo", label: "Turbo 8步（推荐）", description: "速度与画质平衡，默认选择" },
  { id: "fast", label: "极速 6步", description: "更快完成，适合预览和批量尝试" },
  { id: "quality", label: "高质量 20步", description: "原始模型完整采样，耗时最长" },
] as const;

const limits = {
  image: { count: 9, duration: null },
  video: { count: 3, duration: 15 },
  audio: { count: 3, duration: 15 },
} as const;

function seconds(value: number) {
  return value.toFixed(1).replace(/\.0$/, "");
}

async function mediaDuration(file: File): Promise<number | null> {
  if (file.type.startsWith("image/")) return null;
  const url = URL.createObjectURL(file);
  const kind = file.type.startsWith("video/") ? "video" : "audio";
  try {
    return await mediaDurationFromUrl(url, kind);
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function mediaDurationFromUrl(url: string, kind: AssetKind): Promise<number | null> {
  if (kind === "image") return null;
  const media = document.createElement(kind === "video" ? "video" : "audio");
  media.preload = "metadata";
  return new Promise<number>((resolve, reject) => {
    media.onloadedmetadata = () => {
      if (Number.isFinite(media.duration) && media.duration > 0) resolve(media.duration);
      else reject(new Error("duration"));
    };
    media.onerror = () => reject(new Error("duration"));
    media.src = url;
  });
}

function contentUrl(asset: Asset) {
  return `/api/v1/assets/${asset.id}/content`;
}

function restoreStoredAssets(value: unknown): SelectedAsset[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!entry || typeof entry !== "object") return [];
    const stored = entry as Partial<StoredAsset>;
    if (!stored.asset || typeof stored.asset.id !== "string") return [];
    return [{
      asset: stored.asset,
      previewUrl: contentUrl(stored.asset),
      durationSeconds: typeof stored.durationSeconds === "number" ? stored.durationSeconds : null,
    }];
  });
}

function MaterialCard({
  item,
  label,
  onRemove,
}: {
  item: SelectedAsset;
  label: string;
  onRemove: () => void;
}) {
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="relative flex aspect-video items-center justify-center overflow-hidden bg-slate-100">
        {item.asset.kind === "image" ? (
          <Image src={item.previewUrl} alt={item.asset.original_name} fill unoptimized className="object-cover" />
        ) : item.asset.kind === "video" ? (
          <video src={item.previewUrl} controls preload="metadata" className="size-full object-cover" />
        ) : (
          <div className="flex w-full flex-col items-center gap-3 px-4 text-slate-500">
            <FileAudio className="size-8 text-violet-500" />
            <audio src={item.previewUrl} controls preload="metadata" className="h-9 w-full" />
          </div>
        )}
      </div>
      <div className="flex items-center gap-3 p-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-violet-600">{label}</p>
          <p className="mt-1 truncate text-sm text-slate-700">{item.asset.original_name}</p>
          {item.durationSeconds !== null && (
            <p className="mt-1 text-xs text-slate-400">{seconds(item.durationSeconds)} 秒</p>
          )}
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onRemove} aria-label={`移除${label}`}>
          <Trash2 className="size-4" />
        </Button>
      </div>
    </article>
  );
}

export default function CreatePage() {
  const [mode, setMode] = useState<Mode>("t2v");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(5);
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [resolution, setResolution] = useState("768p");
  const [seed, setSeed] = useState(-1);
  const [generationProfile, setGenerationProfile] = useState<GenerationProfile>("turbo");
  const [videoTailSeconds, setVideoTailSeconds] = useState<TailSeconds>(15);
  const [advanced, setAdvanced] = useState(false);
  const [fl2vaAssets, setFl2vaAssets] = useState<SelectedAsset[]>([]);
  const [refAssets, setRefAssets] = useState<SelectedAsset[]>([]);
  const [uploadingKind, setUploadingKind] = useState<AssetKind | null>(null);
  const [pickerTarget, setPickerTarget] = useState<PickerTarget | null>(null);
  const [libraryAssets, setLibraryAssets] = useState<Asset[]>([]);
  const [pickerSelection, setPickerSelection] = useState<string[]>([]);
  const [pickerError, setPickerError] = useState("");
  const [loadingLibrary, setLoadingLibrary] = useState(false);
  const [addingLibrary, setAddingLibrary] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState<VideoJob[]>([]);

  const refImages = refAssets.filter((item) => item.asset.kind === "image");
  const refVideos = refAssets.filter((item) => item.asset.kind === "video");
  const refAudios = refAssets.filter((item) => item.asset.kind === "audio");
  const videoDuration = refVideos.reduce((total, item) => total + (item.durationSeconds ?? 0), 0);
  const audioDuration = refAudios.reduce((total, item) => total + (item.durationSeconds ?? 0), 0);
  const pickerItems = pickerTarget
    ? libraryAssets.filter((asset) => {
        const current = pickerTarget.scope === "fl2va" ? fl2vaAssets : refAssets;
        return asset.kind === pickerTarget.kind
          && !current.some((item) => item.asset.id === asset.id);
      })
    : [];

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

  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(CREATE_DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw) as Partial<CreateDraft>;
      if (draft.mode && modes.some((item) => item.id === draft.mode)) setMode(draft.mode);
      if (typeof draft.prompt === "string") setPrompt(draft.prompt);
      if ([5, 10, 15].includes(draft.duration ?? 0)) setDuration(draft.duration as number);
      if (["16:9", "9:16", "1:1", "4:3", "3:4"].includes(draft.aspectRatio ?? "")) setAspectRatio(draft.aspectRatio as string);
      if (["480p", "720p", "768p"].includes(draft.resolution ?? "")) setResolution(draft.resolution as string);
      if (typeof draft.seed === "number") setSeed(draft.seed);
      if (draft.generationProfile && generationProfiles.some((item) => item.id === draft.generationProfile)) {
        setGenerationProfile(draft.generationProfile);
      }
      if (typeof draft.advanced === "boolean") setAdvanced(draft.advanced);
      if ([5, 10, 15].includes(draft.videoTailSeconds ?? 0)) setVideoTailSeconds(draft.videoTailSeconds as TailSeconds);
      setFl2vaAssets(restoreStoredAssets(draft.fl2vaAssets));
      setRefAssets(restoreStoredAssets(draft.refAssets));
    } catch {
      window.sessionStorage.removeItem(CREATE_DRAFT_KEY);
    } finally {
      setDraftRestored(true);
    }
  }, []);

  useEffect(() => {
    if (!draftRestored) return;
    const draft: CreateDraft = {
      mode,
      prompt,
      duration,
      aspectRatio,
      generationProfile,
      resolution,
      seed,
      advanced,
      videoTailSeconds,
      fl2vaAssets: fl2vaAssets.map(({ asset, durationSeconds }) => ({ asset, durationSeconds })),
      refAssets: refAssets.map(({ asset, durationSeconds }) => ({ asset, durationSeconds })),
    };
    try {
      window.sessionStorage.setItem(CREATE_DRAFT_KEY, JSON.stringify(draft));
    } catch {
      // The form remains usable when browser storage is unavailable.
    }
  }, [
    advanced,
    aspectRatio,
    draftRestored,
    duration,
    generationProfile,
    fl2vaAssets,
    mode,
    prompt,
    refAssets,
    resolution,
    seed,
    videoTailSeconds,
  ]);

  async function uploadFiles(
    files: File[],
    kind: AssetKind,
    knownDurations?: Array<number | null>,
  ): Promise<SelectedAsset[]> {
    const endpoint = kind === "image" ? "images" : kind === "video" ? "videos" : "audio";
    const durations = knownDurations ?? await Promise.all(files.map(mediaDuration));
    const uploaded: SelectedAsset[] = [];
    for (let index = 0; index < files.length; index += 1) {
      const form = new FormData();
      form.append("file", files[index]);
      const asset = await api<Asset>(`/assets/${endpoint}`, { method: "POST", body: form });
      uploaded.push({
        asset,
        previewUrl: URL.createObjectURL(files[index]),
        durationSeconds: durations[index],
      });
    }
    return uploaded;
  }

  async function trimVideoIfNeeded(item: SelectedAsset): Promise<SelectedAsset> {
    if (
      item.asset.kind !== "video"
      || item.durationSeconds === null
      || item.durationSeconds <= videoTailSeconds
    ) {
      return item;
    }
    const clipped = await api<Asset>(`/assets/${item.asset.id}/trim-tail`, {
      method: "POST",
      body: JSON.stringify({ duration_seconds: videoTailSeconds }),
    });
    URL.revokeObjectURL(item.previewUrl);
    return {
      asset: clipped,
      previewUrl: contentUrl(clipped),
      durationSeconds: videoTailSeconds,
    };
  }

  async function uploadFl2va(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    setError("");
    if (fl2vaAssets.length + files.length > 2) {
      setError("首尾帧最多上传两张图片：第 1 张为首帧，第 2 张为尾帧");
      return;
    }
    setUploadingKind("image");
    try {
      const uploaded = await uploadFiles(files, "image");
      setFl2vaAssets((current) => [...current, ...uploaded]);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "首尾帧图片上传失败");
    } finally {
      setUploadingKind(null);
    }
  }

  async function uploadReferences(kind: AssetKind, event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    setError("");

    const current = refAssets.filter((item) => item.asset.kind === kind);
    if (current.length + files.length > limits[kind].count) {
      const noun = kind === "image" ? "图片" : kind === "video" ? "视频" : "音频";
      setError(`参考${noun}最多上传 ${limits[kind].count} 个`);
      return;
    }
    if (refAssets.length + files.length > 12) {
      setError("图片、视频和音频总数最多 12 个");
      return;
    }

    setUploadingKind(kind);
    try {
      const durations = await Promise.all(files.map(mediaDuration));
      const effectiveDurations = kind === "video"
        ? durations.map((value) => value === null ? null : Math.min(value, videoTailSeconds))
        : durations;
      if (kind !== "image") {
        const tooShort = durations.find((value) => value !== null && value < 1.8);
        if (tooShort !== undefined) {
          setError(`参考${kind === "video" ? "视频" : "音频"}不能短于 2 秒`);
          return;
        }
        const currentDuration = current.reduce(
          (total, item) => total + (item.durationSeconds ?? 0),
          0,
        );
        const addedDuration = effectiveDurations.reduce<number>((total, value) => total + (value ?? 0), 0);
        if (currentDuration + addedDuration > 15) {
          setError(
            `参考${kind === "video" ? "视频" : "音频"}总时长最多 15 秒，当前选择后为 ${seconds(currentDuration + addedDuration)} 秒`,
          );
          return;
        }
      }
      const rawUploaded = await uploadFiles(files, kind, durations);
      const uploaded = kind === "video"
        ? await Promise.all(rawUploaded.map(trimVideoIfNeeded))
        : rawUploaded;
      setRefAssets((items) => [...items, ...uploaded]);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "参考素材上传失败，请检查文件格式");
    } finally {
      setUploadingKind(null);
    }
  }

  async function openLibrary(target: PickerTarget) {
    setError("");
    setPickerTarget(target);
    setPickerSelection([]);
    setPickerError("");
    setLoadingLibrary(true);
    try {
      const result = await api<{ items: Asset[] }>("/assets");
      setLibraryAssets(result.items);
    } catch (reason) {
      setPickerTarget(null);
      setError(reason instanceof ApiError ? reason.message : "素材库加载失败");
    } finally {
      setLoadingLibrary(false);
    }
  }

  function pickerCapacity(target: PickerTarget) {
    if (target.scope === "fl2va") return Math.max(0, 2 - fl2vaAssets.length);
    const sameKind = refAssets.filter((item) => item.asset.kind === target.kind).length;
    return Math.max(0, Math.min(limits[target.kind].count - sameKind, 12 - refAssets.length));
  }

  function toggleLibraryAsset(assetId: string) {
    if (!pickerTarget) return;
    setPickerSelection((selected) => {
      if (selected.includes(assetId)) return selected.filter((id) => id !== assetId);
      if (selected.length >= pickerCapacity(pickerTarget)) return selected;
      return [...selected, assetId];
    });
  }

  async function addLibraryAssets() {
    if (!pickerTarget || !pickerSelection.length) return;
    setPickerError("");
    setAddingLibrary(true);
    try {
      const byId = new Map(libraryAssets.map((asset) => [asset.id, asset]));
      const chosen = pickerSelection
        .map((id) => byId.get(id))
        .filter((asset): asset is Asset => Boolean(asset));
      let selected = await Promise.all(
        chosen.map(async (asset) => ({
          asset,
          previewUrl: contentUrl(asset),
          durationSeconds: await mediaDurationFromUrl(contentUrl(asset), asset.kind),
        })),
      );
      if (pickerTarget.kind === "video") {
        const currentDuration = refVideos.reduce(
          (total, item) => total + (item.durationSeconds ?? 0),
          0,
        );
        const selectedDuration = selected.reduce(
          (total, item) => total + Math.min(item.durationSeconds ?? 0, videoTailSeconds),
          0,
        );
        if (pickerTarget.scope === "ref" && currentDuration + selectedDuration > 15) {
          setPickerError(`参考视频总时长最多 15 秒，当前选择后为 ${seconds(currentDuration + selectedDuration)} 秒`);
          return;
        }
        selected = await Promise.all(selected.map(trimVideoIfNeeded));
      }

      if (pickerTarget.scope === "fl2va") {
        if (fl2vaAssets.length + selected.length > 2) {
          setPickerError("首尾帧最多选择两张图片");
          return;
        }
        setFl2vaAssets((current) => [...current, ...selected]);
      } else {
        const kind = pickerTarget.kind;
        const current = refAssets.filter((item) => item.asset.kind === kind);
        if (current.length + selected.length > limits[kind].count || refAssets.length + selected.length > 12) {
          setPickerError("所选素材超过当前模式的数量限制");
          return;
        }
        if (kind !== "image") {
          if (selected.some((item) => item.durationSeconds !== null && item.durationSeconds < 1.8)) {
            setPickerError(`参考${kind === "video" ? "视频" : "音频"}不能短于 2 秒`);
            return;
          }
          const currentDuration = current.reduce((total, item) => total + (item.durationSeconds ?? 0), 0);
          const addedDuration = selected.reduce((total, item) => total + (item.durationSeconds ?? 0), 0);
          if (currentDuration + addedDuration > 15) {
            setPickerError(`参考${kind === "video" ? "视频" : "音频"}总时长最多 15 秒，当前选择后为 ${seconds(currentDuration + addedDuration)} 秒`);
            return;
          }
        }
        setRefAssets((currentAssets) => [...currentAssets, ...selected]);
      }
      setPickerTarget(null);
      setPickerSelection([]);
    } catch {
      setPickerError("无法读取所选视频或音频的时长，请检查素材文件");
    } finally {
      setAddingLibrary(false);
    }
  }

  function removeSelected(
    item: SelectedAsset,
    setter: Dispatch<SetStateAction<SelectedAsset[]>>,
  ) {
    URL.revokeObjectURL(item.previewUrl);
    setter((items) => items.filter((candidate) => candidate.asset.id !== item.asset.id));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const selected = mode === "i2v" ? fl2vaAssets : mode === "ref2va" ? refAssets : [];
    if (mode === "i2v" && !fl2vaAssets.length) {
      setError("首尾帧 FL2VA 至少需要上传首帧图片");
      return;
    }
    if (mode === "ref2va" && !refImages.length && !refVideos.length) {
      setError("全能参考至少需要一张图片或一个视频，不能只上传音频");
      return;
    }

    setSubmitting(true);
    try {
      await api("/video-jobs", {
        method: "POST",
        body: JSON.stringify({
          mode,
          model_variant: "int8",
          prompt,
          generation_profile: generationProfile,
          duration_seconds: duration,
          aspect_ratio: aspectRatio,
          resolution,
          seed,
          asset_ids: selected.map((item) => item.asset.id),
        }),
      });
      setPrompt("");
      selected.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      if (mode === "i2v") setFl2vaAssets([]);
      if (mode === "ref2va") setRefAssets([]);
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
        <p className="mt-2 text-sm text-slate-500">锦宿内部模型服务 · MiniMax H3 INT8 · GPU 单并发排队执行</p>
      </div>
      <form onSubmit={submit} className="overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white shadow-xl shadow-slate-200/45">
        <div className="grid border-b border-slate-100 md:grid-cols-3">
          {modes.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setMode(item.id);
                setError("");
              }}
              className={cn(
                "relative border-b border-slate-100 px-5 py-4 text-left transition last:border-0 md:border-b-0 md:border-r",
                mode === item.id ? "bg-violet-50/70" : "hover:bg-slate-50",
              )}
            >
              <span className="block text-sm font-semibold text-slate-900">{item.title}</span>
              <span className="mt-1 block text-xs text-slate-400">{item.description}</span>
              {mode === item.id && <span className="absolute inset-x-5 bottom-0 h-0.5 rounded-full bg-violet-500" />}
            </button>
          ))}
        </div>

        <div className="p-5 md:p-7">
          {mode === "i2v" && (
            <section className="mb-7">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-slate-800">首尾帧</h2>
                  <p className="mt-1 text-xs text-slate-400">第 1 张作为首帧，第 2 张作为尾帧；尾帧可不上传。</p>
                </div>
                <span className="text-xs font-medium text-violet-600">图片 {fl2vaAssets.length}/2</span>
              </div>
              {fl2vaAssets.length > 0 && (
                <div className="mb-3 grid gap-3 sm:grid-cols-2">
                  {fl2vaAssets.map((item, index) => (
                    <MaterialCard
                      key={item.asset.id}
                      item={item}
                      label={index === 0 ? "首帧" : "尾帧"}
                      onRemove={() => removeSelected(item, setFl2vaAssets)}
                    />
                  ))}
                </div>
              )}
              {fl2vaAssets.length < 2 && (
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="flex cursor-pointer items-center justify-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-6 text-sm text-slate-500 transition hover:border-violet-300 hover:bg-violet-50">
                    {uploadingKind === "image" ? <LoaderCircle className="size-5 animate-spin" /> : <ImagePlus className="size-5" />}
                    {uploadingKind === "image" ? "正在上传…" : fl2vaAssets.length ? "上传可选尾帧" : "上传首帧或首尾帧"}
                    <input
                      className="sr-only"
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp"
                      multiple
                      onChange={uploadFl2va}
                      disabled={uploadingKind !== null}
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => void openLibrary({ scope: "fl2va", kind: "image" })}
                    className="flex items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-6 text-sm text-slate-600 transition hover:border-violet-300 hover:bg-violet-50"
                  >
                    <FolderOpen className="size-5 text-violet-500" />
                    从素材库选择
                  </button>
                </div>
              )}
            </section>
          )}

          {mode === "ref2va" && (
            <section className="mb-7">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-2xl bg-violet-50 p-3.5"><p className="text-xs text-violet-500">图片</p><p className="mt-1 text-lg font-semibold text-violet-900">{refImages.length}/9</p></div>
                <div className="rounded-2xl bg-sky-50 p-3.5"><p className="text-xs text-sky-500">视频</p><p className="mt-1 text-lg font-semibold text-sky-900">{refVideos.length}/3，{seconds(videoDuration)}/15s</p></div>
                <div className="rounded-2xl bg-amber-50 p-3.5"><p className="text-xs text-amber-600">音频</p><p className="mt-1 text-lg font-semibold text-amber-900">{refAudios.length}/3，{seconds(audioDuration)}/15s</p></div>
                <div className="rounded-2xl bg-slate-100 p-3.5"><p className="text-xs text-slate-500">总素材</p><p className="mt-1 text-lg font-semibold text-slate-900">{refAssets.length}/12</p></div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {([
                  ["image", "上传参考图片", ".jpg,.jpeg,.png,.webp", ImagePlus],
                  ["video", "上传动作视频", ".mp4,.mov,.webm", FileVideo],
                  ["audio", "上传声音音频", ".wav,.mp3,.m4a,.flac", FileAudio],
                ] as const).map(([kind, label, accept, Icon]) => (
                  <div key={kind} className="space-y-2">
                    <label className="flex cursor-pointer items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500 transition hover:border-violet-300 hover:bg-violet-50">
                      {uploadingKind === kind ? <LoaderCircle className="size-5 animate-spin" /> : <Icon className="size-5" />}
                      {uploadingKind === kind ? "正在上传…" : label}
                      <input
                        className="sr-only"
                        type="file"
                        accept={accept}
                        multiple
                        onChange={(event) => void uploadReferences(kind, event)}
                        disabled={uploadingKind !== null}
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => void openLibrary({ scope: "ref", kind })}
                      className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-medium text-slate-600 transition hover:border-violet-300 hover:bg-violet-50"
                    >
                      <FolderOpen className="size-4 text-violet-500" />从素材库选择
                    </button>
                    {kind === "video" && (
                      <label className="flex items-center justify-between rounded-xl bg-sky-50 px-3 py-2 text-xs text-sky-700">
                        超过时截取末尾
                        <select
                          className="rounded-lg border border-sky-200 bg-white px-2 py-1 font-medium outline-none"
                          value={videoTailSeconds}
                          onChange={(event) => setVideoTailSeconds(Number(event.target.value) as TailSeconds)}
                        >
                          <option value={5}>5 秒</option>
                          <option value={10}>10 秒</option>
                          <option value={15}>15 秒</option>
                        </select>
                      </label>
                    )}
                  </div>
                ))}
              </div>

              {refAssets.length > 0 && (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {refAssets.map((item) => {
                    const sameKind = refAssets.filter((candidate) => candidate.asset.kind === item.asset.kind);
                    const index = sameKind.findIndex((candidate) => candidate.asset.id === item.asset.id) + 1;
                    const label = item.asset.kind === "image" ? `参考图片 ${index}` : item.asset.kind === "video" ? `参考视频 ${index}` : `参考音频 ${index}`;
                    return (
                      <MaterialCard
                        key={item.asset.id}
                        item={item}
                        label={label}
                        onRemove={() => removeSelected(item, setRefAssets)}
                      />
                    );
                  })}
                </div>
              )}

              <p className="mt-4 rounded-xl bg-violet-50 px-4 py-3 text-xs leading-6 text-violet-700">
                Prompt 可写：人物参考图片1（<code>&lt;Picture 1&gt;</code>）、动作参考视频1（<code>&lt;Video 1&gt;</code>）、声音参考音频1（<code>&lt;Audio 1&gt;</code>）。编号按同类型素材的展示顺序填写。
              </p>
            </section>
          )}

          <textarea
            className="min-h-48 w-full resize-y border-0 bg-transparent text-lg leading-8 text-slate-800 outline-none placeholder:text-slate-300"
            placeholder={
              mode === "ref2va"
                ? "例如：人物参考图片1保持人物外观，动作参考视频1控制动作节奏，声音参考音频1作为声音参考；使用 <Picture 1>、<Video 1>、<Audio 1> 标签…"
                : mode === "i2v"
                  ? "描述从首帧到尾帧之间的动作、镜头运动、环境声音和整体氛围…"
                  : "描述你想生成的视频内容、镜头运动、环境声音和整体氛围…"
            }
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            maxLength={10000}
            required
          />
          {error && <p className="mb-4 rounded-xl bg-rose-50 px-3.5 py-3 text-sm text-rose-700">{error}</p>}
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-5">
            <label className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
              时长
              <select className="ml-2 bg-transparent font-medium text-slate-800 outline-none" value={duration} onChange={(event) => setDuration(Number(event.target.value))}>
                <option value={5}>5 秒</option><option value={10}>10 秒</option><option value={15}>15 秒</option>
              </select>
            </label>
            <label className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
              比例
              <select className="ml-2 bg-transparent font-medium text-slate-800 outline-none" value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value)}>
                <option>16:9</option><option>9:16</option><option>1:1</option><option>4:3</option><option>3:4</option>
              </select>
            </label>
            <label className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
              清晰度
              <select className="ml-2 bg-transparent font-medium text-slate-800 outline-none" value={resolution} onChange={(event) => setResolution(event.target.value)}>
                <option value="480p">480p</option><option value="720p">720p</option><option value="768p">768p</option>
              </select>
            </label>
            <button type="button" className="flex items-center gap-1 rounded-xl px-3 py-2 text-xs font-medium text-slate-500 hover:bg-slate-100" onClick={() => setAdvanced(!advanced)}>
              高级设置 <ChevronDown className={cn("size-3.5 transition", advanced && "rotate-180")} />
            </button>
            <label className="rounded-xl border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-600">
              生成档位
              <select className="ml-2 bg-transparent font-semibold text-violet-800 outline-none" value={generationProfile} onChange={(event) => setGenerationProfile(event.target.value as GenerationProfile)}>
                {generationProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.label}</option>)}
              </select>
            </label>
            <Button className="ml-auto" variant="accent" size="lg" disabled={submitting || uploadingKind !== null || !prompt.trim()}>
              {submitting ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {submitting ? "提交中…" : "生成视频"}
            </Button>
          </div>
          {advanced && (
            <div className="mt-4 grid gap-4 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2">
              <label className="text-xs font-medium text-slate-500">Seed（-1 为随机）
                <input className="mt-2 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-violet-400" type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} />
              </label>
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
                <span className="font-medium text-slate-700">{generationProfiles.find((profile) => profile.id === generationProfile)?.label}</span><span className="mt-1 block">{generationProfiles.find((profile) => profile.id === generationProfile)?.description}；步数和采样器由服务端锁定。</span>
              </div>
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

      <Dialog
        open={Boolean(pickerTarget)}
        onOpenChange={(open) => {
          if (!open && !addingLibrary) {
            setPickerTarget(null);
            setPickerSelection([]);
            setPickerError("");
          }
        }}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>从素材库选择</DialogTitle>
            <DialogDescription>
              {pickerTarget?.kind === "image" ? "选择图片素材" : pickerTarget?.kind === "video" ? "选择视频素材" : "选择音频素材"}
              {pickerTarget ? `，本次还可选择 ${pickerCapacity(pickerTarget)} 个` : ""}
            </DialogDescription>
          </DialogHeader>
          {loadingLibrary ? (
            <div className="flex min-h-56 items-center justify-center gap-2 text-sm text-slate-400">
              <LoaderCircle className="size-5 animate-spin" />正在加载素材库…
            </div>
          ) : pickerItems.length ? (
            <div className="grid max-h-[58vh] gap-3 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3">
              {pickerItems.map((asset) => {
                const selected = pickerSelection.includes(asset.id);
                const atCapacity = pickerTarget
                  ? pickerSelection.length >= pickerCapacity(pickerTarget)
                  : false;
                return (
                  <button
                    key={asset.id}
                    type="button"
                    disabled={!selected && atCapacity}
                    onClick={() => toggleLibraryAsset(asset.id)}
                    className={cn(
                      "overflow-hidden rounded-2xl border bg-white text-left transition",
                      selected ? "border-violet-500 ring-2 ring-violet-100" : "border-slate-200 hover:border-violet-300",
                      !selected && atCapacity && "cursor-not-allowed opacity-45",
                    )}
                  >
                    <div className="relative flex aspect-video items-center justify-center overflow-hidden bg-slate-100">
                      {asset.kind === "image" ? (
                        <Image src={contentUrl(asset)} alt={asset.original_name} fill unoptimized className="object-cover" />
                      ) : asset.kind === "video" ? (
                        <FileVideo className="size-10 text-sky-500" />
                      ) : (
                        <FileAudio className="size-10 text-amber-500" />
                      )}
                      {selected && <span className="absolute right-2 top-2 grid size-7 place-items-center rounded-full bg-violet-600 text-white shadow"><Check className="size-4" /></span>}
                    </div>
                    <div className="p-3">
                      <p className="truncate text-sm font-medium text-slate-800" title={asset.original_name}>{asset.original_name}</p>
                      <p className="mt-1 text-xs text-slate-400">{(asset.size_bytes / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-200 py-14 text-center text-sm text-slate-400">
              素材库中没有可选的此类素材，请先上传素材。
            </div>
          )}
          {pickerError && <p className="mt-4 rounded-xl bg-rose-50 px-3.5 py-3 text-sm text-rose-700">{pickerError}</p>}
          <div className="mt-5 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
            <p className="text-xs text-slate-400">已选择 {pickerSelection.length} 个</p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => { setPickerTarget(null); setPickerSelection([]); setPickerError(""); }} disabled={addingLibrary}>取消</Button>
              <Button type="button" variant="accent" onClick={() => void addLibraryAssets()} disabled={!pickerSelection.length || addingLibrary}>
                {addingLibrary && <LoaderCircle className="size-4 animate-spin" />}
                {addingLibrary ? "正在读取素材…" : "添加所选素材"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
