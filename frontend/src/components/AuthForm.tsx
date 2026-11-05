"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Github } from "lucide-react";
import { API_URL, api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.2 1.3-1.6 3.9-5.5 3.9-3.3 0-6-2.7-6-6s2.7-6 6-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.4 14.6 2.4 12 2.4 6.7 2.4 2.4 6.7 2.4 12s4.3 9.6 9.6 9.6c5.5 0 9.2-3.9 9.2-9.4 0-.6-.1-1.1-.2-1.6H12z" />
    </svg>
  );
}

function Inner({ mode }: { mode: "login" | "signup" }) {
  const { login, signup, me, loading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [providers, setProviders] = useState<Record<string, boolean>>({});
  const [form, setForm] = useState({ email: params.get("email") ?? "", password: "", name: "", org_name: "" });
  const [error, setError] = useState<string | null>(params.get("error") ? "Single sign-on failed. Please try again." : null);
  const [busy, setBusy] = useState(false);
  const invite = params.get("invite");

  useEffect(() => {
    api<Record<string, boolean>>("/auth/oauth/providers", { auth: false }).then(setProviders).catch(() => setProviders({}));
  }, []);
  useEffect(() => {
    if (!loading && me) router.replace("/dashboard");
  }, [loading, me, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(form.email, form.password);
      else await signup({ ...form, ...(invite ? { invite_token: invite } : {}) });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const sso = [
    { id: "google", label: "Google", icon: <GoogleIcon /> },
    { id: "github", label: "GitHub", icon: <Github className="h-4 w-4" /> },
  ];
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <Link href="/" className="mb-8 flex justify-center"><Logo className="text-lg" /></Link>
        <div className="glass p-6 sm:p-8">
          <h1 className="text-xl font-semibold tracking-tight">{mode === "login" ? "Welcome back" : "Create your workspace"}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{mode === "login" ? "Sign in to run your agents." : "Free to start. No API key needed in demo mode."}</p>

          <div className="mt-6 grid grid-cols-2 gap-3">
            {sso.map((p) => {
              const enabled = providers[p.id];
              return enabled ? (
                <a key={p.id} href={`${API_URL}/auth/oauth/${p.id}/login`}>
                  <Button type="button" variant="outline" className="w-full">{p.icon} {p.label}</Button>
                </a>
              ) : (
                <Button key={p.id} type="button" variant="outline" disabled title={`${p.label} sign-in is not configured`}>{p.icon} {p.label}</Button>
              );
            })}
          </div>
          {!Object.values(providers).some(Boolean) && <p className="mt-2 text-center text-xs text-muted-foreground">SSO is not configured on this server.</p>}

          <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />or with email<span className="h-px flex-1 bg-border" /></div>

          <form onSubmit={submit} className="space-y-4">
            {mode === "signup" && (
              <>
                <Field label="Your name"><Input required value={form.name} onChange={set("name")} autoComplete="name" placeholder="Ada Lovelace" /></Field>
                {!invite && <Field label="Organization"><Input required value={form.org_name} onChange={set("org_name")} placeholder="Acme Inc." /></Field>}
              </>
            )}
            <Field label="Email"><Input type="email" required value={form.email} onChange={set("email")} autoComplete="email" placeholder="you@company.com" /></Field>
            <Field label="Password" hint={mode === "signup" ? "At least 8 characters" : undefined}>
              <Input type="password" required minLength={mode === "signup" ? 8 : 1} value={form.password} onChange={set("password")} autoComplete={mode === "login" ? "current-password" : "new-password"} />
            </Field>
            {error && <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
            <Button type="submit" className="w-full" loading={busy}>{mode === "login" ? "Sign in" : "Create account"}</Button>
          </form>
        </div>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          {mode === "login" ? <>New here? <Link className="text-primary hover:underline" href="/signup">Create an account</Link></> : <>Already have an account? <Link className="text-primary hover:underline" href="/login">Sign in</Link></>}
        </p>
      </div>
    </div>
  );
}

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  return <Suspense><Inner mode={mode} /></Suspense>;
}
