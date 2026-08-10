import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function modeLabel(mode: string) {
  return { t2v: "文生视频 T2VA", i2v: "首尾帧 FL2VA", ref2va: "全能参考 Ref2VA" }[mode] ?? mode;
}

export function generationProfileLabel(profile: string) {
  return {
    turbo: "Turbo 8步",
    fast: "极速 6步",
    quality: "高质量 20步",
  }[profile] ?? profile;
}

export function statusLabel(status: string) {
  return {
    queued: "排队中",
    switching: "切换模型",
    preparing: "准备素材",
    running: "生成中",
    encoding: "视频编码",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  }[status] ?? status;
}
