import * as React from "react";
import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm text-slate-950 outline-none placeholder:text-slate-400 focus:border-violet-400 focus:ring-3 focus:ring-violet-100",
        className,
      )}
      {...props}
    />
  );
}
