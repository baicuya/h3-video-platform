"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";

export default function ChangePasswordPage() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("两次输入的新密码不一致");
      return;
    }
    setLoading(true);
    try {
      await api("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });
      router.replace("/create");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "修改失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-5 py-10">
      <section className="w-full max-w-md rounded-[2rem] border border-white bg-white p-8 shadow-xl shadow-slate-300/35 sm:p-10">
        <Brand className="mb-9" />
        <h1 className="text-2xl font-semibold text-slate-950">设置你的新密码</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          首次登录必须修改管理员提供的初始密码，完成后才能进入创作页。
        </p>
        <form className="mt-7 space-y-4" onSubmit={submit}>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">当前密码</span>
            <Input type="password" autoComplete="current-password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required />
          </label>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">新密码</span>
            <Input type="password" autoComplete="new-password" minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
          </label>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">确认新密码</span>
            <Input type="password" autoComplete="new-password" minLength={8} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
          </label>
          {error && <p className="rounded-xl bg-rose-50 px-3.5 py-3 text-sm text-rose-700">{error}</p>}
          <Button className="w-full" variant="accent" size="lg" disabled={loading}>
            {loading ? "正在保存…" : "保存并进入工作台"}
          </Button>
        </form>
      </section>
    </main>
  );
}
