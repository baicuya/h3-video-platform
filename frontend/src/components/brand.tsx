import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export function Brand({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span className="grid size-10 place-items-center rounded-2xl bg-slate-950 text-white shadow-lg shadow-slate-950/15">
        <Sparkles className="size-5" />
      </span>
      {!compact && (
        <span>
          <span className="block text-sm font-semibold tracking-wide text-slate-950">锦宿 Jinxiu</span>
          <span className="block text-xs text-slate-500">AI 视频工作台</span>
        </span>
      )}
    </div>
  );
}
