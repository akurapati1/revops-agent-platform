"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Copy, KeyRound, Mail, Plug, Trash2, UserPlus } from "lucide-react";
import { api, API_URL, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/hooks";
import { cn, fmtCost, fmtNumber, initials } from "@/lib/utils";
import type { AgentInfo, Integrations, Invite, Member, OrgFull, Usage } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Tabs } from "@/components/ui/tabs";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";

type Tab = "org" | "members" | "usage" | "integrations";
const TABS: { id: Tab; label: string }[] = [
  { id: "org", label: "Organization" }, { id: "members", label: "Members" }, { id: "usage", label: "API usage" }, { id: "integrations", label: "Integrations" },
];
const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

function OrgTab({ org, reload, canEdit }: { org: OrgFull; reload: () => void; canEdit: boolean }) {
  const toast = useToast();
  const { reload: reloadMe } = useAuth();
  const st = org.settings;
  const [f, setF] = useState({
    name: org.name, sender_name: st.sender_name, product_pitch: st.product_pitch,
    industries: st.icp.industries.join(", "), regions: st.icp.regions.join(", "),
    min: st.icp.min_employees?.toString() ?? "", max: st.icp.max_employees?.toString() ?? "",
  });
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/orgs/current", { method: "PATCH", json: { name: f.name, settings: {
        sender_name: f.sender_name, product_pitch: f.product_pitch,
        icp: { industries: csv(f.industries), regions: csv(f.regions), min_employees: f.min ? Number(f.min) : null, max_employees: f.max ? Number(f.max) : null },
      } } });
      toast("ok", "Organization saved");
      reload(); reloadMe();
    } catch (x) { toast("err", x instanceof ApiError ? x.message : "Save failed"); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={save} className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader title="Workspace" description="Used by the Personalizer when writing emails" />
        <CardBody className="space-y-4">
          <Field label="Organization name"><Input value={f.name} onChange={set("name")} disabled={!canEdit} required /></Field>
          <Field label="Sender name" hint="Signature on generated emails"><Input value={f.sender_name} onChange={set("sender_name")} disabled={!canEdit} /></Field>
          <Field label="Product pitch" hint="One or two sentences describing what you sell"><Textarea value={f.product_pitch} onChange={set("product_pitch")} disabled={!canEdit} maxLength={500} /></Field>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Ideal customer profile" description="The Enricher scores every lead against this" />
        <CardBody className="space-y-4">
          <Field label="Target industries" hint="Comma separated"><Input value={f.industries} onChange={set("industries")} disabled={!canEdit} placeholder="B2B SaaS, FinTech" /></Field>
          <Field label="Target regions" hint="Comma separated"><Input value={f.regions} onChange={set("regions")} disabled={!canEdit} placeholder="North America, EMEA" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Min employees"><Input type="number" min={1} value={f.min} onChange={set("min")} disabled={!canEdit} /></Field>
            <Field label="Max employees"><Input type="number" min={1} value={f.max} onChange={set("max")} disabled={!canEdit} /></Field>
          </div>
          {canEdit ? <div className="flex justify-end"><Button type="submit" loading={busy}>Save changes</Button></div> : <p className="text-xs text-muted-foreground">Only admins can edit organization settings.</p>}
        </CardBody>
      </Card>
    </form>
  );
}

function MembersTab({ canEdit, isOwner }: { canEdit: boolean; isOwner: boolean }) {
  const toast = useToast();
  const { me } = useAuth();
  const { data, error, reload } = useFetch<Member[]>("/orgs/current/members");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [invite, setInvite] = useState<Invite | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      setInvite(await api<Invite>("/orgs/current/invitations", { method: "POST", json: { email, role } }));
      setEmail("");
    } catch (x) { toast("err", x instanceof ApiError ? x.message : "Invite failed"); } finally { setBusy(false); }
  }
  async function changeRole(id: string, r: string) {
    try { await api(`/orgs/current/members/${id}`, { method: "PATCH", json: { role: r } }); reload(); toast("ok", "Role updated"); }
    catch (x) { toast("err", x instanceof ApiError ? x.message : "Could not change role"); }
  }
  async function remove(id: string) {
    if (!window.confirm("Remove this member?")) return;
    try { await api(`/orgs/current/members/${id}`, { method: "DELETE" }); reload(); }
    catch (x) { toast("err", x instanceof ApiError ? x.message : "Could not remove member"); }
  }
  const inviteLink = invite ? `${window.location.origin}/signup?invite=${invite.token}&email=${encodeURIComponent(invite.email)}` : "";

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader title="Team" description={data ? `${data.length} member${data.length === 1 ? "" : "s"}` : undefined} />
        {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <CardBody><Skeleton className="h-32" /></CardBody> : (
          <ul className="divide-y">
            {data.map((m) => (
              <li key={m.user_id} className="flex items-center gap-3 px-5 py-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-primary/80 to-accent/80 text-xs font-bold text-white">{initials(m.name || m.email)}</div>
                <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{m.name || m.email}</p><p className="truncate text-xs text-muted-foreground">{m.email}</p></div>
                {canEdit && m.user_id !== me?.user.id ? (
                  <>
                    <Select className="h-8 w-28 text-xs" value={m.role} onChange={(e) => changeRole(m.user_id, e.target.value)} aria-label={`Role for ${m.email}`}>
                      <option value="member">member</option><option value="admin">admin</option>{isOwner && <option value="owner">owner</option>}
                    </Select>
                    <button onClick={() => remove(m.user_id)} aria-label={`Remove ${m.email}`} className="rounded-md p-1.5 text-muted-foreground hover:bg-danger/10 hover:text-danger"><Trash2 className="h-4 w-4" /></button>
                  </>
                ) : <Badge tone={m.role === "owner" ? "primary" : "neutral"}>{m.role}</Badge>}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <CardHeader title="Invite a teammate" description="Share the generated link with them" />
        <CardBody>
          {canEdit ? (
            <form onSubmit={send} className="space-y-3">
              <Field label="Email"><Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" /></Field>
              <Field label="Role"><Select value={role} onChange={(e) => setRole(e.target.value)}><option value="member">Member</option><option value="admin">Admin</option></Select></Field>
              <Button type="submit" className="w-full" loading={busy}><UserPlus className="h-4 w-4" /> Create invitation</Button>
            </form>
          ) : <p className="text-sm text-muted-foreground">Only admins can invite members.</p>}
          {invite && (
            <div className="mt-4 space-y-2 rounded-xl border border-success/30 bg-success/10 p-3 text-xs">
              <p className="font-medium text-success">Invitation created for {invite.email}</p>
              <p className="break-all text-muted-foreground">{inviteLink}</p>
              <Button size="sm" variant="outline" onClick={() => { navigator.clipboard?.writeText(inviteLink); toast("ok", "Link copied"); }}><Copy className="h-3.5 w-3.5" /> Copy link</Button>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function UsageTab({ org, canEdit, reloadOrg }: { org: OrgFull; canEdit: boolean; reloadOrg: () => void }) {
  const toast = useToast();
  const { data, error, reload } = useFetch<Usage>("/usage");
  const [limit, setLimit] = useState(String(org.monthly_token_limit));
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <Skeleton className="h-72" />;
  const pct = Math.min(100, (data.tokens / data.limit) * 100);

  async function saveLimit(e: React.FormEvent) {
    e.preventDefault();
    try { await api("/orgs/current", { method: "PATCH", json: { monthly_token_limit: Number(limit) } }); toast("ok", "Limit updated"); reload(); reloadOrg(); }
    catch (x) { toast("err", x instanceof ApiError ? x.message : "Could not update limit"); }
  }
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader title="Monthly token usage" description={`Since ${new Date(data.period_start).toLocaleDateString()}`} />
        <CardBody>
          <div className="flex items-end justify-between">
            <p className="text-3xl font-semibold">{fmtNumber(data.tokens)}<span className="text-base font-normal text-muted-foreground"> / {fmtNumber(data.limit)}</span></p>
            <p className="text-sm text-muted-foreground">{fmtCost(data.cost_usd)} · {data.calls} calls</p>
          </div>
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
            <div className={cn("h-full rounded-full transition-all", pct > 90 ? "bg-danger" : pct > 70 ? "bg-warning" : "bg-gradient-to-r from-primary to-accent")} style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-6 h-52">
            {data.daily.length === 0 ? <p className="pt-16 text-center text-sm text-muted-foreground">No usage this month yet.</p> : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.daily.map((d) => ({ ...d, label: d.date.slice(5) }))} margin={{ left: -10 }}>
                  <CartesianGrid vertical={false} stroke="hsl(225 22% 18%)" />
                  <XAxis dataKey="label" stroke="#6b7280" fontSize={11} tickLine={false} />
                  <YAxis stroke="#6b7280" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: "hsl(226 32% 9%)", border: "1px solid hsl(225 22% 18%)", borderRadius: 12, fontSize: 12 }} />
                  <Bar dataKey="tokens" fill="#8b5cf6" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </CardBody>
      </Card>
      <div className="space-y-4">
        <Card>
          <CardHeader title="By agent" />
          <CardBody className="space-y-3">
            {data.by_agent.length === 0 ? <p className="text-sm text-muted-foreground">-</p> : data.by_agent.map((a) => (
              <div key={a.agent} className="flex items-center justify-between text-sm"><span className="capitalize">{a.agent}</span><span className="text-muted-foreground">{fmtNumber(a.tokens)} tok · {fmtCost(a.cost_usd)}</span></div>
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Monthly limit" description="Runs stop when this is reached" />
          <CardBody>
            <form onSubmit={saveLimit} className="flex gap-2">
              <Input type="number" min={1000} step={1000} value={limit} onChange={(e) => setLimit(e.target.value)} disabled={!canEdit} aria-label="Monthly token limit" />
              <Button type="submit" disabled={!canEdit}>Save</Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function IntegrationsTab({ org }: { org: OrgFull }) {
  const toast = useToast();
  const integ = useFetch<Integrations>("/integrations");
  const agents = useFetch<{ agents: AgentInfo[] }>("/agents");
  if (integ.error) return <ErrorState message={integ.error} onRetry={integ.reload} />;
  if (!integ.data) return <Skeleton className="h-72" />;
  const i = integ.data;
  const webhook = org.webhook_token ? `${API_URL}/webhooks/replies/${org.webhook_token}` : null;
  const Status = ({ ok }: { ok: boolean }) => ok ? <Badge tone="success" dot>Connected</Badge> : <Badge tone="neutral" dot>Not configured</Badge>;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader title="Language model" description="Configured on the server via environment variables" action={<Status ok={i.llm.configured} />} />
        <CardBody className="space-y-3 text-sm">
          <div className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-primary" /> Provider <Badge tone={i.llm.provider === "mock" ? "warning" : "primary"}>{i.llm.provider === "mock" ? "mock (offline demo)" : i.llm.provider}</Badge></div>
          <ul className="space-y-1.5">{Object.entries(i.llm.models).map(([a, m]) => <li key={a} className="flex justify-between"><span className="capitalize text-muted-foreground">{a}</span><code className="text-xs">{m}</code></li>)}</ul>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Email delivery" description="Pluggable EmailProvider" action={<Status ok={i.email.configured} />} />
        <CardBody className="space-y-2 text-sm">
          <div className="flex items-center gap-2"><Mail className="h-4 w-4 text-primary" /> Provider <Badge tone={i.email.provider === "console" ? "warning" : "primary"}>{i.email.provider === "console" ? "console (logs only)" : i.email.provider}</Badge></div>
          <p className="text-muted-foreground">From: <code className="text-xs">{i.email.from}</code></p>
          <p className="text-muted-foreground">Job queue: {i.queue.backend}</p>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Single sign-on" />
        <CardBody className="space-y-2 text-sm">
          {Object.entries(i.oauth).map(([p, ok]) => <div key={p} className="flex items-center justify-between"><span className="capitalize">{p}</span><Status ok={ok} /></div>)}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Inbound reply webhook" description="POST replies from your email provider to triage them automatically" />
        <CardBody className="space-y-2 text-sm">
          {webhook ? (
            <>
              <code className="block break-all rounded-lg bg-muted/60 p-2 text-xs">POST {webhook}</code>
              <code className="block rounded-lg bg-muted/60 p-2 text-xs">{`{"from_email": "lead@acme.com", "body": "..."}`}</code>
              <Button size="sm" variant="outline" onClick={() => { navigator.clipboard?.writeText(webhook); toast("ok", "Webhook URL copied"); }}><Copy className="h-3.5 w-3.5" /> Copy URL</Button>
            </>
          ) : <p className="text-muted-foreground">Visible to admins only.</p>}
        </CardBody>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader title="Agent registry" description="Each agent has its own prompt, tools and structured output" action={<Plug className="h-4 w-4 text-muted-foreground" />} />
        <CardBody className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {agents.data?.agents.map((a) => (
            <div key={a.name} className="rounded-xl border bg-muted/30 p-3">
              <div className="flex items-center justify-between"><p className="text-sm font-semibold capitalize">{a.name}</p><Badge tone={a.uses_llm ? "primary" : "neutral"}>{a.uses_llm ? "LLM" : "deterministic"}</Badge></div>
              <p className="mt-1 text-xs text-muted-foreground">{a.description}</p>
              {a.tools.length > 0 && <p className="mt-2 text-xs text-muted-foreground">Tools: {a.tools.map((t) => t.name).join(", ")}</p>}
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

function SettingsInner() {
  const router = useRouter();
  const params = useSearchParams();
  const initial = (params.get("tab") as Tab) || "org";
  const [tab, setTab] = useState<Tab>(TABS.some((t) => t.id === initial) ? initial : "org");
  const org = useFetch<OrgFull>("/orgs/current");
  useEffect(() => { router.replace(`/settings?tab=${tab}`, { scroll: false }); }, [tab, router]);

  if (org.error && !org.data) return <ErrorState message={org.error} onRetry={org.reload} />;
  const o = org.data;
  const canEdit = !!o && (o.role === "owner" || o.role === "admin");
  return (
    <div className="animate-fade-in">
      <PageHeader title="Settings" description={o ? `${o.name} · you are ${o.role}` : undefined} />
      <Tabs<Tab> tabs={TABS} value={tab} onChange={setTab} />
      {!o ? <Skeleton className="h-72" /> : (
        <>
          {tab === "org" && <OrgTab key={o.id + o.name} org={o} reload={org.reload} canEdit={canEdit} />}
          {tab === "members" && <MembersTab canEdit={canEdit} isOwner={o.role === "owner"} />}
          {tab === "usage" && <UsageTab org={o} canEdit={canEdit} reloadOrg={org.reload} />}
          {tab === "integrations" && <IntegrationsTab org={o} />}
        </>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return <Suspense fallback={<Skeleton className="h-72" />}><SettingsInner /></Suspense>;
}


