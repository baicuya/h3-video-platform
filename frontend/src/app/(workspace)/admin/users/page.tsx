"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Check,
  Copy,
  KeyRound,
  LoaderCircle,
  Plus,
  Search,
  Settings2,
  Trash2,
  UserRoundCheck,
  UserRoundX,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { PageResult, User } from "@/lib/types";
import { formatDate } from "@/lib/utils";

type CreateForm = {
  username: string;
  display_name: string;
  initial_password: string;
  confirm_password: string;
  role: "user" | "admin";
  is_active: boolean;
  remark: string;
};

type EditForm = {
  display_name: string;
  role: "user" | "admin";
  remark: string;
};

type ConfirmAction =
  | { kind: "enable" | "disable" | "delete"; user: User }
  | { kind: "update-role"; user: User; changes: EditForm };

const emptyForm: CreateForm = {
  username: "",
  display_name: "",
  initial_password: "",
  confirm_password: "",
  role: "user",
  is_active: true,
  remark: "",
};

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof ApiError ? reason.message : fallback;
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [pageError, setPageError] = useState("");
  const [notice, setNotice] = useState("");

  const [form, setForm] = useState<CreateForm>(emptyForm);
  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState("");

  const [manageUser, setManageUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState<EditForm>({ display_name: "", role: "user", remark: "" });
  const [manageError, setManageError] = useState("");

  const [resetUser, setResetUser] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirmPassword, setResetConfirmPassword] = useState("");
  const [resetError, setResetError] = useState("");

  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);
  const [confirmError, setConfirmError] = useState("");
  const [createdCredentials, setCreatedCredentials] = useState<{ username: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setPageError("");
    try {
      const params = new URLSearchParams({ page_size: "100" });
      if (search) params.set("query", search);
      const result = await api<PageResult<User>>(`/admin/users?${params}`);
      setUsers(result.items);
      setTotal(result.total);
    } catch (reason) {
      setPageError(errorMessage(reason, "账号列表加载失败"));
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    void api<User>("/auth/me").then(setCurrentUser).catch(() => setCurrentUser(null));
  }, []);

  function showNotice(message: string) {
    setPageError("");
    setNotice(message);
    window.setTimeout(() => setNotice(""), 4000);
  }

  function openManage(user: User) {
    setManageUser(user);
    setEditForm({
      display_name: user.display_name,
      role: user.role,
      remark: user.remark ?? "",
    });
    setManageError("");
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    setCreateError("");
    if (form.initial_password !== form.confirm_password) {
      setCreateError("两次输入的初始密码不一致");
      return;
    }
    setBusy("create");
    try {
      const result = await api<{ user: User; initial_password: string }>("/admin/users", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setCreateOpen(false);
      setForm(emptyForm);
      setCreatedCredentials({ username: result.user.username, password: result.initial_password });
      showNotice(`账号 ${result.user.username} 已创建`);
      await load();
    } catch (reason) {
      setCreateError(errorMessage(reason, "账号创建失败"));
    } finally {
      setBusy("");
    }
  }

  async function saveUser(event: FormEvent) {
    event.preventDefault();
    if (!manageUser) return;
    setManageError("");
    if (editForm.role !== manageUser.role) {
      setManageUser(null);
      setConfirmError("");
      setConfirmAction({ kind: "update-role", user: manageUser, changes: editForm });
      return;
    }
    setBusy(`save:${manageUser.id}`);
    try {
      const updated = await api<User>(`/admin/users/${manageUser.id}`, {
        method: "PATCH",
        body: JSON.stringify(editForm),
      });
      setManageUser(updated);
      setEditForm({
        display_name: updated.display_name,
        role: updated.role,
        remark: updated.remark ?? "",
      });
      showNotice(`账号 ${updated.username} 的资料已更新`);
      await load();
    } catch (reason) {
      setManageError(errorMessage(reason, "账号资料更新失败"));
    } finally {
      setBusy("");
    }
  }

  async function reset(event: FormEvent) {
    event.preventDefault();
    if (!resetUser) return;
    setResetError("");
    if (resetPassword !== resetConfirmPassword) {
      setResetError("两次输入的新密码不一致");
      return;
    }
    setBusy(`reset:${resetUser.id}`);
    try {
      const result = await api<{ username: string; initial_password: string }>(
        `/admin/users/${resetUser.id}/reset-password`,
        {
          method: "POST",
          body: JSON.stringify({
            new_password: resetPassword,
            confirm_password: resetConfirmPassword,
          }),
        },
      );
      setResetUser(null);
      setResetPassword("");
      setResetConfirmPassword("");
      setCreatedCredentials({ username: result.username, password: result.initial_password });
      showNotice(`账号 ${result.username} 的密码已重置`);
      await load();
    } catch (reason) {
      setResetError(errorMessage(reason, "密码重置失败"));
    } finally {
      setBusy("");
    }
  }

  function requestAction(kind: "enable" | "disable" | "delete", user: User) {
    setManageUser(null);
    setConfirmError("");
    setConfirmAction({ kind, user });
  }

  async function executeAction() {
    if (!confirmAction) return;
    const { kind, user } = confirmAction;
    setConfirmError("");
    setBusy(`${kind}:${user.id}`);
    try {
      if (kind === "update-role") {
        await api(`/admin/users/${user.id}`, {
          method: "PATCH",
          body: JSON.stringify(confirmAction.changes),
        });
      } else if (kind === "delete") {
        await api(`/admin/users/${user.id}`, { method: "DELETE" });
      } else {
        await api(`/admin/users/${user.id}/${kind}`, { method: "POST" });
      }
      setConfirmAction(null);
      showNotice(
        kind === "update-role"
          ? `账号 ${user.username} 已调整为${confirmAction.changes.role === "admin" ? "管理员" : "普通用户"}`
          : kind === "delete"
          ? `账号 ${user.username} 已删除`
          : `账号 ${user.username} 已${kind === "enable" ? "启用" : "禁用"}`,
      );
      await load();
    } catch (reason) {
      setConfirmError(errorMessage(
        reason,
        kind === "update-role" ? "角色调整失败" : kind === "delete" ? "账号删除失败" : "账号状态更新失败",
      ));
    } finally {
      setBusy("");
    }
  }

  async function copyCredentials() {
    if (!createdCredentials) return;
    try {
      await navigator.clipboard.writeText(
        `用户名：${createdCredentials.username}\n初始密码：${createdCredentials.password}`,
      );
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  const isManagingSelf = Boolean(manageUser && currentUser?.id === manageUser.id);
  const actionTitle = confirmAction?.kind === "update-role"
    ? "调整角色"
    : confirmAction?.kind === "delete"
    ? "删除账号"
    : confirmAction?.kind === "disable"
      ? "禁用账号"
      : "启用账号";
  const actionDescription = confirmAction?.kind === "update-role"
    ? `确认将该账号调整为${confirmAction.changes.role === "admin" ? "管理员" : "普通用户"}？管理员可以管理全部账号和系统设置。`
    : confirmAction?.kind === "delete"
    ? "只有从未产生任务或素材的账号才能删除；已有业务数据的账号应改为禁用。"
    : confirmAction?.kind === "disable"
      ? "该账号的现有登录会话将立即失效，之后无法登录，历史业务数据会保留。"
      : "启用后，该账号可以重新登录并使用平台。";

  return (
    <div>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <Badge tone="accent">管理员</Badge>
          <h1 className="mt-3 text-3xl font-semibold text-slate-950">账号管理</h1>
          <p className="mt-2 text-sm text-slate-500">集中管理账号资料、权限、登录状态与密码。</p>
        </div>
        <Button variant="accent" onClick={() => { setCreateError(""); setCreateOpen(true); }}>
          <Plus className="size-4" />开通新账号
        </Button>
      </div>

      {notice && <p className="mt-5 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{notice}</p>}
      {pageError && <p className="mt-5 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{pageError}</p>}

      <div className="mt-7 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <form
          className="relative w-full max-w-md"
          onSubmit={(event) => { event.preventDefault(); setSearch(query.trim()); }}
        >
          <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <Input
            className="pl-10 pr-10"
            placeholder="搜索用户名或显示名称"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query && (
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100"
              onClick={() => { setQuery(""); setSearch(""); }}
              aria-label="清除搜索"
            >
              <X className="size-4" />
            </button>
          )}
        </form>
        <p className="text-xs text-slate-400">共 {total} 个账号</p>
      </div>

      <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="border-b border-slate-100 bg-slate-50/70 text-xs font-medium text-slate-400">
            <tr>
              <th className="px-5 py-3.5">账号</th>
              <th className="px-5 py-3.5">角色</th>
              <th className="px-5 py-3.5">状态</th>
              <th className="px-5 py-3.5">最近登录</th>
              <th className="px-5 py-3.5">创建时间</th>
              <th className="px-5 py-3.5 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((user) => {
              const isSelf = currentUser?.id === user.id;
              return (
                <tr key={user.id} className="text-slate-600 transition hover:bg-slate-50/60">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900">{user.display_name}</span>
                      {isSelf && <Badge tone="accent">当前账号</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-slate-400">@{user.username}{user.remark ? ` · ${user.remark}` : ""}</p>
                  </td>
                  <td className="px-5 py-4">
                    <Badge tone={user.role === "admin" ? "accent" : "neutral"}>
                      {user.role === "admin" ? "管理员" : "普通用户"}
                    </Badge>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={user.is_active ? "success" : "danger"}>{user.is_active ? "已启用" : "已禁用"}</Badge>
                      {user.must_change_password && <span className="text-xs text-amber-600">待修改初始密码</span>}
                    </div>
                  </td>
                  <td className="px-5 py-4 text-xs">{formatDate(user.last_login_at)}</td>
                  <td className="px-5 py-4 text-xs">{formatDate(user.created_at)}</td>
                  <td className="px-5 py-4">
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" disabled={!currentUser} onClick={() => openManage(user)}>
                        <Settings2 className="size-3.5" />管理账号
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={!currentUser || isSelf}
                        title={isSelf ? "请通过个人修改密码页面管理当前账号密码" : "重置初始密码"}
                        onClick={() => {
                          setResetUser(user);
                          setResetPassword("");
                          setResetConfirmPassword("");
                          setResetError("");
                        }}
                      >
                        <KeyRound className="size-3.5" />重置密码
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {loading && <div className="flex py-16 items-center justify-center gap-2 text-sm text-slate-400"><LoaderCircle className="size-5 animate-spin" />正在加载账号…</div>}
        {!loading && !users.length && <div className="py-16 text-center text-sm text-slate-400">没有找到账号</div>}
      </div>

      <Dialog open={createOpen} onOpenChange={(open) => { if (!busy) setCreateOpen(open); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>开通新账号</DialogTitle>
            <DialogDescription>初始密码只在创建成功后显示一次，请安全交给使用者。</DialogDescription>
          </DialogHeader>
          <form className="grid gap-4 sm:grid-cols-2" onSubmit={create}>
            <label className="space-y-2 text-sm font-medium">用户名 *
              <Input value={form.username} pattern="[A-Za-z0-9_.-]{3,32}" onChange={(event) => setForm({ ...form, username: event.target.value })} required />
              <span className="block text-xs font-normal text-slate-400">3–32 位字母、数字、点、下划线或短横线</span>
            </label>
            <label className="space-y-2 text-sm font-medium">显示名称 *
              <Input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} required />
            </label>
            <label className="space-y-2 text-sm font-medium">初始密码 *
              <Input type="password" minLength={8} value={form.initial_password} onChange={(event) => setForm({ ...form, initial_password: event.target.value })} required />
            </label>
            <label className="space-y-2 text-sm font-medium">确认密码 *
              <Input type="password" minLength={8} value={form.confirm_password} onChange={(event) => setForm({ ...form, confirm_password: event.target.value })} required />
            </label>
            <label className="space-y-2 text-sm font-medium">角色
              <select className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as "user" | "admin" })}>
                <option value="user">普通用户</option><option value="admin">管理员</option>
              </select>
            </label>
            <label className="space-y-2 text-sm font-medium">初始状态
              <select className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3" value={form.is_active ? "active" : "disabled"} onChange={(event) => setForm({ ...form, is_active: event.target.value === "active" })}>
                <option value="active">启用</option><option value="disabled">禁用</option>
              </select>
            </label>
            <label className="space-y-2 text-sm font-medium sm:col-span-2">备注
              <Input value={form.remark} maxLength={2000} onChange={(event) => setForm({ ...form, remark: event.target.value })} />
            </label>
            {createError && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700 sm:col-span-2">{createError}</p>}
            <Button className="sm:col-span-2" variant="accent" size="lg" disabled={busy === "create"}>
              {busy === "create" && <LoaderCircle className="size-4 animate-spin" />}
              {busy === "create" ? "正在创建…" : "创建账号"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(manageUser)} onOpenChange={(open) => { if (!open && !busy) setManageUser(null); }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>管理账号 · {manageUser?.username}</DialogTitle>
            <DialogDescription>修改基础资料与权限；状态和删除操作需要单独确认。</DialogDescription>
          </DialogHeader>
          {manageUser && (
            <>
              <form className="grid gap-4 sm:grid-cols-2" onSubmit={saveUser}>
                <label className="space-y-2 text-sm font-medium">显示名称
                  <Input value={editForm.display_name} onChange={(event) => setEditForm({ ...editForm, display_name: event.target.value })} required />
                </label>
                <label className="space-y-2 text-sm font-medium">角色
                  <select
                    className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3 disabled:bg-slate-100"
                    value={editForm.role}
                    disabled={isManagingSelf}
                    onChange={(event) => setEditForm({ ...editForm, role: event.target.value as "user" | "admin" })}
                  >
                    <option value="user">普通用户</option><option value="admin">管理员</option>
                  </select>
                  {isManagingSelf && <span className="block text-xs font-normal text-slate-400">不能降低当前登录管理员的角色</span>}
                </label>
                <label className="space-y-2 text-sm font-medium sm:col-span-2">备注
                  <textarea
                    className="min-h-24 w-full resize-y rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-violet-400"
                    maxLength={2000}
                    value={editForm.remark}
                    onChange={(event) => setEditForm({ ...editForm, remark: event.target.value })}
                  />
                </label>
                {editForm.role === "admin" && manageUser.role !== "admin" && (
                  <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-700 sm:col-span-2">授予管理员角色后，该账号可以管理全部用户和系统设置。</p>
                )}
                {manageError && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700 sm:col-span-2">{manageError}</p>}
                <Button className="sm:col-span-2" variant="accent" disabled={busy === `save:${manageUser.id}`}>
                  {busy === `save:${manageUser.id}` && <LoaderCircle className="size-4 animate-spin" />}
                  {busy === `save:${manageUser.id}` ? "正在保存…" : "保存资料与权限"}
                </Button>
              </form>

              <div className="mt-6 border-t border-slate-100 pt-5">
                <h3 className="text-sm font-semibold text-slate-800">账号操作</h3>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <button
                    type="button"
                    disabled={isManagingSelf}
                    onClick={() => requestAction(manageUser.is_active ? "disable" : "enable", manageUser)}
                    className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-left transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    {manageUser.is_active ? <UserRoundX className="size-5 text-amber-600" /> : <UserRoundCheck className="size-5 text-emerald-600" />}
                    <span><span className="block text-sm font-medium text-slate-800">{manageUser.is_active ? "禁用账号" : "启用账号"}</span><span className="mt-0.5 block text-xs text-slate-400">{manageUser.is_active ? "立即终止登录权限" : "恢复平台登录权限"}</span></span>
                  </button>
                  <button
                    type="button"
                    disabled={isManagingSelf}
                    onClick={() => {
                      setManageUser(null);
                      setResetUser(manageUser);
                      setResetPassword("");
                      setResetConfirmPassword("");
                      setResetError("");
                    }}
                    className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-left transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <KeyRound className="size-5 text-violet-600" />
                    <span><span className="block text-sm font-medium text-slate-800">重置密码</span><span className="mt-0.5 block text-xs text-slate-400">旧会话立即失效</span></span>
                  </button>
                </div>
                <button
                  type="button"
                  disabled={isManagingSelf}
                  onClick={() => requestAction("delete", manageUser)}
                  className="mt-3 flex w-full items-center gap-3 rounded-xl border border-rose-100 bg-rose-50/50 p-3 text-left text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <Trash2 className="size-5" />
                  <span><span className="block text-sm font-medium">删除账号</span><span className="mt-0.5 block text-xs text-rose-500">仅适用于从未产生业务数据的账号</span></span>
                </button>
                {isManagingSelf && <p className="mt-3 text-xs text-slate-400">当前登录账号不能被禁用、删除或在此重置密码。</p>}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(resetUser)} onOpenChange={(open) => { if (!open && !busy) setResetUser(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>重置密码 · {resetUser?.username}</DialogTitle>
            <DialogDescription>重置后旧会话立即失效，用户下次登录必须修改密码。</DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={reset}>
            <label className="space-y-2 text-sm font-medium">新初始密码
              <Input type="password" minLength={8} value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} required />
            </label>
            <label className="space-y-2 text-sm font-medium">确认新初始密码
              <Input type="password" minLength={8} value={resetConfirmPassword} onChange={(event) => setResetConfirmPassword(event.target.value)} required />
            </label>
            {resetError && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{resetError}</p>}
            <Button className="w-full" variant="accent" disabled={Boolean(resetUser && busy === `reset:${resetUser.id}`)}>
              {resetUser && busy === `reset:${resetUser.id}` && <LoaderCircle className="size-4 animate-spin" />}
              {resetUser && busy === `reset:${resetUser.id}` ? "正在重置…" : "确认重置密码"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(confirmAction)} onOpenChange={(open) => { if (!open && !busy) setConfirmAction(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{actionTitle} · {confirmAction?.user.username}</DialogTitle>
            <DialogDescription>{actionDescription}</DialogDescription>
          </DialogHeader>
          {confirmAction?.kind === "delete" && (
            <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">删除不可撤销。若接口发现该账号已有任务或素材，将拒绝删除。</p>
          )}
          {confirmError && <p className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{confirmError}</p>}
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmAction(null)} disabled={Boolean(busy)}>取消</Button>
            <Button
              variant={confirmAction?.kind === "delete" || confirmAction?.kind === "disable" ? "danger" : "accent"}
              onClick={() => void executeAction()}
              disabled={Boolean(busy)}
            >
              {busy && <LoaderCircle className="size-4 animate-spin" />}
              确认{actionTitle}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(createdCredentials)} onOpenChange={(open) => { if (!open) { setCreatedCredentials(null); setCopied(false); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>账号信息只显示一次</DialogTitle>
            <DialogDescription>请安全地将账号信息发送给使用者，关闭后无法再次查询原始密码。</DialogDescription>
          </DialogHeader>
          {createdCredentials && (
            <div className="space-y-3 rounded-2xl bg-slate-950 p-5 font-mono text-sm text-white">
              <p><span className="text-slate-400">用户名：</span>{createdCredentials.username}</p>
              <p><span className="text-slate-400">初始密码：</span>{createdCredentials.password}</p>
            </div>
          )}
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Button variant="outline" onClick={() => void copyCredentials()}>
              {copied ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4" />}
              {copied ? "已复制" : "复制账号和密码"}
            </Button>
            <Button onClick={() => { setCreatedCredentials(null); setCopied(false); }}>我已安全保存</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
