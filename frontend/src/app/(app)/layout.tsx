"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckSquare, LayoutDashboard, Loader2, LogOut, Menu, Moon, Settings, Sun, Users, Workflow, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/hooks";
import { cn, initials } from "@/lib/utils";
import { Logo } from "@/components/Logo";
import type { Approval } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/runs", label: "Agent runs", icon: Workflow },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { me, loading, logout, switchOrg } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [light, setLight] = useState(false);
  const pending = useFetch<Approval[]>(me ? "/approvals?status=pending" : null, { interval: 8000 });

  useEffect(() => {
    if (!loading && !me) router.replace("/login");
  }, [loading, me, router]);
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => setLight(document.documentElement.classList.contains("light")), []);

  function toggleTheme() {
    const next = !light;
    document.documentElement.classList.toggle("light", next);
    try { localStorage.setItem("revops.theme", next ? "light" : "dark"); } catch { /* ignore */ }
    setLight(next);
  }

  if (loading || !me) {
    return <div className="flex min-h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>;
  }
  const pendingCount = pending.data?.length ?? 0;

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5"><Logo /></div>
      <nav className="flex-1 space-y-1 px-3" aria-label="Main">
        {NAV.map((n) => {
          const active = pathname === n.href || pathname.startsWith(n.href + "/");
          return (
            <Link key={n.href} href={n.href}
              className={cn("group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                active ? "bg-gradient-to-r from-primary/25 to-transparent text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground")}>
              <n.icon className={cn("h-4.5 w-4.5", active && "text-primary")} size={18} />
              {n.label}
              {n.href === "/approvals" && pendingCount > 0 && (
                <span className="ml-auto rounded-full bg-warning/20 px-2 py-0.5 text-xs font-semibold text-warning">{pendingCount}</span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="space-y-3 border-t p-4">
        {me.orgs.length > 1 && (
          <select aria-label="Switch organization" className="input h-9 text-xs" value={me.org?.id} onChange={(e) => switchOrg(e.target.value).then(() => router.refresh())}>
            {me.orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        )}
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-accent text-xs font-bold text-white">{initials(me.user.name || me.user.email)}</div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{me.user.name || me.user.email}</p>
            <p className="truncate text-xs text-muted-foreground">{me.org?.name} · {me.org?.role}</p>
          </div>
          <button onClick={toggleTheme} aria-label="Toggle theme" className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground">
            {light ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
          </button>
          <button onClick={logout} aria-label="Sign out" className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-danger"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r bg-card/60 backdrop-blur-xl lg:block">{sidebar}</aside>
      <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-background/70 px-4 py-3 backdrop-blur-xl lg:hidden">
        <Logo />
        <button onClick={() => setOpen(true)} aria-label="Open menu" className="rounded-md p-2 hover:bg-muted"><Menu className="h-5 w-5" /></button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 border-r bg-card animate-fade-in">
            <button onClick={() => setOpen(false)} aria-label="Close menu" className="absolute right-3 top-4 rounded-md p-1.5 hover:bg-muted"><X className="h-4 w-4" /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
    </div>
  );
}
