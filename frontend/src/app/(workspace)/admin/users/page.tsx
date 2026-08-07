"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { KeyRound, MoreHorizontal, Plus, Search, ShieldCheck, UserRoundCheck, UserRoundX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { PageResult, User } from "@/lib/types";
import { formatDate } from "@/lib/utils";

type CreateForm = {
  username: string; display_name: string; initial_password: string;
  confirm_password: string; role: "user" | "admin"; is_active: boolean; remark: string;
};
const emptyForm: CreateForm = { username: "", display_name: "", initial_password: "", confirm_password: "", role: "user", is_active: true, remark: "" };

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<CreateForm>(emptyForm);
  const [createOpen, setCreateOpen] = useState(false);
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [createdCredentials, setCreatedCredentials] = useState<{ username: string; password: string } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page_size: "100" });
    if (search) params.set("query", search);
    const result = await api<PageResult<User>>(`/admin/users?${params}`);
    setUsers(result.items); setTotal(result.total);
  }, [search]);
  useEffect(() => { void load(); }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault(); setError("");
    try {
      const result = await api<{ user: User; initial_password: string }>("/admin/users", { method: "POST", body: JSON.stringify(form) });
      setCreateOpen(false); setForm(emptyForm); setCreatedCredentials({ username: result.user.username, password: result.initial_password }); await load();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "账号创建失败"); }
  }
  async function toggle(user: User) {
    await api(`/admin/users/${user.id}/${user.is_active ? "disable" : "enable"}`, { method: "POST" }); await load();
  }
  async function reset(event: FormEvent) {
    event.preventDefault(); if (!resetUser) return; setError("");
    try {
      const result = await api<{ username: string; initial_password: string }>(`/admin/users/${resetUser.id}/reset-password`, { method: "POST", body: JSON.stringify({ new_password: resetPassword, confirm_password: resetPassword }) });
      setResetUser(null); setResetPassword(""); setCreatedCredentials({ username: result.username, password: result.initial_password }); await load();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "重置失败"); }
  }
  async function updateRole(user: User) {
    await api(`/admin/users/${user.id}`, { method: "PATCH", body: JSON.stringify({ role: user.role === "admin" ? "user" : "admin" }) }); await load();
  }
  async function remove(user: User) {
    if (!confirm(`确认删除账号 ${user.username}？仅无业务数据的账号可删除。`)) return;
    try { await api(`/admin/users/${user.id}`, { method: "DELETE" }); await load(); }
    catch (reason) { alert(reason instanceof ApiError ? reason.message : "删除失败"); }
  }

  return (
    <div>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><Badge tone="accent">管理员</Badge><h1 className="mt-3 text-3xl font-semibold text-slate-950">账号管理</h1><p className="mt-2 text-sm text-slate-500">普通用户只能由管理员开通，系统不提供公开注册。</p></div><Button variant="accent" onClick={() => { setError(""); setCreateOpen(true); }}><Plus className="size-4" />开通新账号</Button></div>
      <form className="relative mt-7 max-w-md" onSubmit={(event) => { event.preventDefault(); setSearch(query); }}><Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><Input className="pl-10" placeholder="搜索用户名或显示名称" value={query} onChange={(e) => setQuery(e.target.value)} /></form>
      <div className="mt-5 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[900px] text-left text-sm"><thead className="border-b border-slate-100 bg-slate-50/70 text-xs font-medium text-slate-400"><tr><th className="px-5 py-3.5">用户名</th><th className="px-5 py-3.5">显示名称</th><th className="px-5 py-3.5">角色</th><th className="px-5 py-3.5">状态</th><th className="px-5 py-3.5">最近登录</th><th className="px-5 py-3.5">创建时间</th><th className="px-5 py-3.5">操作</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{users.map((user) => <tr key={user.id} className="text-slate-600"><td className="px-5 py-4 font-medium text-slate-900">{user.username}</td><td className="px-5 py-4">{user.display_name}</td><td className="px-5 py-4"><Badge tone={user.role === "admin" ? "accent" : "neutral"}>{user.role}</Badge></td><td className="px-5 py-4"><Badge tone={user.is_active ? "success" : "danger"}>{user.is_active ? "启用" : "禁用"}</Badge>{user.must_change_password && <span className="ml-2 text-xs text-amber-600">待改密码</span>}</td><td className="px-5 py-4 text-xs">{formatDate(user.last_login_at)}</td><td className="px-5 py-4 text-xs">{formatDate(user.created_at)}</td><td className="px-5 py-4"><div className="flex gap-1"><Button variant="ghost" size="sm" onClick={() => { setResetUser(user); setError(""); }}><KeyRound className="size-3.5" />重置</Button><Button variant="ghost" size="sm" onClick={() => toggle(user)}>{user.is_active ? <UserRoundX className="size-3.5" /> : <UserRoundCheck className="size-3.5" />}{user.is_active ? "禁用" : "启用"}</Button><Button variant="ghost" size="icon" title="切换角色" onClick={() => updateRole(user)}><ShieldCheck className="size-4" /></Button><Button variant="ghost" size="icon" title="删除" onClick={() => remove(user)}><MoreHorizontal className="size-4" /></Button></div></td></tr>)}</tbody>
        </table>
        {!users.length && <div className="py-16 text-center text-sm text-slate-400">没有找到账号</div>}
      </div>
      <p className="mt-3 text-xs text-slate-400">共 {total} 个账号</p>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}><DialogContent><DialogHeader><DialogTitle>开通新账号</DialogTitle><DialogDescription>初始密码只在创建成功后显示一次，请安全交给使用者。</DialogDescription></DialogHeader><form className="grid gap-4 sm:grid-cols-2" onSubmit={create}><label className="space-y-2 text-sm font-medium">用户名 *<Input value={form.username} pattern="[A-Za-z0-9_.-]{3,32}" onChange={(e) => setForm({ ...form, username: e.target.value })} required /></label><label className="space-y-2 text-sm font-medium">显示名称 *<Input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required /></label><label className="space-y-2 text-sm font-medium">初始密码 *<Input type="password" minLength={8} value={form.initial_password} onChange={(e) => setForm({ ...form, initial_password: e.target.value })} required /></label><label className="space-y-2 text-sm font-medium">确认密码 *<Input type="password" minLength={8} value={form.confirm_password} onChange={(e) => setForm({ ...form, confirm_password: e.target.value })} required /></label><label className="space-y-2 text-sm font-medium">角色<select className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as "user" | "admin" })}><option value="user">user</option><option value="admin">admin</option></select></label><label className="space-y-2 text-sm font-medium">状态<select className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3" value={form.is_active ? "active" : "disabled"} onChange={(e) => setForm({ ...form, is_active: e.target.value === "active" })}><option value="active">启用</option><option value="disabled">禁用</option></select></label><label className="space-y-2 text-sm font-medium sm:col-span-2">备注<Input value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} /></label>{error && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700 sm:col-span-2">{error}</p>}<Button className="sm:col-span-2" variant="accent" size="lg">创建账号</Button></form></DialogContent></Dialog>
      <Dialog open={Boolean(resetUser)} onOpenChange={(open) => !open && setResetUser(null)}><DialogContent><DialogHeader><DialogTitle>重置密码</DialogTitle><DialogDescription>重置后旧会话立即失效，用户下次登录必须修改密码。</DialogDescription></DialogHeader><form className="space-y-4" onSubmit={reset}><label className="space-y-2 text-sm font-medium">新初始密码<Input type="password" minLength={8} value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} required /></label>{error && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}<Button className="w-full" variant="accent">确认重置</Button></form></DialogContent></Dialog>
      <Dialog open={Boolean(createdCredentials)} onOpenChange={(open) => !open && setCreatedCredentials(null)}><DialogContent><DialogHeader><DialogTitle>账号信息只显示一次</DialogTitle><DialogDescription>请安全地将账号信息发送给使用者，关闭后无法再次查询原始密码。</DialogDescription></DialogHeader>{createdCredentials && <div className="space-y-3 rounded-2xl bg-slate-950 p-5 font-mono text-sm text-white"><p><span className="text-slate-400">用户名：</span>{createdCredentials.username}</p><p><span className="text-slate-400">初始密码：</span>{createdCredentials.password}</p></div>}<Button className="mt-4 w-full" onClick={() => setCreatedCredentials(null)}>我已安全保存</Button></DialogContent></Dialog>
    </div>
  );
}
