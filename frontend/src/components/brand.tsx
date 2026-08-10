import Image from "next/image";
import { cn } from "@/lib/utils";

export function Brand({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <Image
        src="/brand/jinxiu-logo-black.jpg"
        alt="锦宿 Jinxiu"
        width={48}
        height={48}
        className="size-12 shrink-0 rounded-2xl object-cover shadow-lg shadow-fuchsia-950/15"
      />
      {!compact && (
        <span>
          <span className="block text-sm font-semibold tracking-wide text-slate-950">锦宿 Jinxiu</span>
          <span className="block text-xs text-slate-500">AI 视频工作台</span>
        </span>
      )}
    </div>
  );
}
