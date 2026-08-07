"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { LockKeyhole, UserRound } from "lucide-react";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await api<User>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      router.replace(user.must_change_password ? "/change-password" : "/create");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "登录失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden px-5 py-10">
      <div className="absolute left-[-8rem] top-[-9rem] size-96 rounded-full bg-violet-200/40 blur-3xl" />
      <div className="absolute bottom-[-10rem] right-[-8rem] size-96 rounded-full bg-sky-200/45 blur-3xl" />
      <section className="relative w-full max-w-md rounded-[2rem] border border-white/80 bg-white/90 p-8 shadow-2xl shadow-slate-300/35 backdrop-blur-xl sm:p-10">
        <Brand className="mb-10" />
        <div className="mb-7">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">欢迎回来</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">登录锦宿内部创作空间，开始生成视频。</p>
        </div>
        <form className="space-y-5" onSubmit={submit}>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">账号</span>
            <span className="relative block">
              <UserRound className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                className="pl-10"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                placeholder="请输入管理员开通的账号"
                required
              />
            </span>
          </label>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">密码</span>
            <span className="relative block">
              <LockKeyhole className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                className="pl-10"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                placeholder="请输入密码"
                required
              />
            </span>
          </label>
          {error && (
            <p role="alert" className="rounded-xl bg-rose-50 px-3.5 py-3 text-sm text-rose-700">
              {error}
            </p>
          )}
          <Button className="w-full" size="lg" variant="accent" disabled={loading}>
            {loading ? "正在登录…" : "登录"}
          </Button>
        </form>
        <p className="mt-7 text-center text-xs leading-5 text-slate-400">
          账号由管理员统一开通，如需使用请联系管理员。
        </p>
      </section>
    </main>
  );
}
