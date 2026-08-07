"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Clapperboard,
  Clock3,
  FolderOpen,
  Gauge,
  LogOut,
  PanelLeft,
  Users,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";

const standardItems = [
  { href: "/create", label: "创作", icon: Clapperboard },
  { href: "/history", label: "历史记录", icon: Clock3 },
  { href: "/assets", label: "素材", icon: FolderOpen },
];
const adminItems = [
  { href: "/admin", label: "系统状态", icon: Gauge },
  { href: "/admin/users", label: "账号管理", icon: Users },
];

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [open, setOpen] = useState(false);

  const loadUser = useCallback(async () => {
    try {
      const current = await api<User>("/auth/me");
      if (current.must_change_password && pathname !== "/change-password") {
        router.replace("/change-password");
        return;
      }
      if (pathname.startsWith("/admin") && current.role !== "admin") {
        router.replace("/create");
        return;
      }
      setUser(current);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        router.replace("/login");
      }
    }
  }, [pathname, router]);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  if (!user) {
    return <div className="grid min-h-screen place-items-center text-sm text-slate-400">正在进入工作台…</div>;
  }

  const items = user.role === "admin" ? [...standardItems, ...adminItems] : standardItems;
  return (
    <div className="min-h-screen">
      {open && <button aria-label="关闭导航" className="fixed inset-0 z-30 bg-slate-950/25 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={cn("fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200/80 bg-white/95 p-4 backdrop-blur-xl transition-transform lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
        <Brand className="px-2 py-2" />
        <nav className="mt-8 space-y-1">
          {items.map((item) => {
            const active = pathname === item.href || (item.href !== "/create" && pathname.startsWith(`${item.href}/`));
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                  active ? "bg-slate-950 text-white shadow-sm" : "text-slate-500 hover:bg-slate-100 hover:text-slate-950",
                )}
              >
                <item.icon className="size-[18px]" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto rounded-2xl border border-slate-200 bg-slate-50 p-3.5">
          <p className="truncate text-sm font-medium text-slate-900">{user.display_name}</p>
          <p className="mt-0.5 truncate text-xs text-slate-400">@{user.username} · {user.role === "admin" ? "管理员" : "用户"}</p>
          <Button className="mt-3 w-full justify-start" variant="ghost" size="sm" onClick={logout}>
            <LogOut className="size-4" />
            退出登录
          </Button>
        </div>
      </aside>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center border-b border-slate-200/70 bg-canvas/85 px-5 backdrop-blur-xl lg:px-8">
          <Button className="lg:hidden" variant="ghost" size="icon" onClick={() => setOpen(true)}>
            <PanelLeft className="size-5" />
          </Button>
          <span className="ml-auto rounded-full border border-violet-100 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-700">
            MiniMax H3 · INT8
          </span>
        </header>
        <main className="mx-auto w-full max-w-[1500px] p-5 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
