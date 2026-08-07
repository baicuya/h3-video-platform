import { WorkspaceShell } from "@/components/workspace-shell";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
