"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Building2, Globe, Play, Send, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { timeAgo } from "@/lib/utils";
import type { Approval, LeadDetail, Reply, Run } from "@/lib/types";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/form";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";

function List({ items }: { items: unknown }) {
  const arr = Array.isArray(items) ? (items as string[]) : [];
  if (!arr.length) return <p className="text-sm text-muted-foreground">-</p>;
  return <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">{arr.map((x, i) => <li key={i}>{x}</li>)}</ul>;
}

const CLS_TONE: Record<string, "success" | "warning" | "danger" | "neutral" | "accent"> = { interested: "success", objection: "warning", unsubscribe: "danger", out_of_office: "accent", other: "neutral" };

export default function LeadPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const lead = useFetch<LeadDetail>(`/leads/${id}`, { interval: 4000 });
  const runs = useFetch<Run[]>(`/runs?lead_id=${id}`, { interval: 3000 });
  const approvals = useFetch<Approval[]>(`/leads/${id}/approvals`, { interval: 6000 });
  const replies = useFetch<Reply[]>(`/leads/${id}/replies`, { interval: 4000 });
  const [starting, setStarting] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);

  if (lead.error && !lead.data) return <ErrorState message={lead.error} onRetry={lead.reload} />;
  const l = lead.data;
  if (!l) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>;
  const brief = l.brief as Record<string, unknown> | null;
  const firmo = l.firmographics as Record<string, unknown> | null;
  const name = `${l.first_name} ${l.last_name}`.trim() || l.email;

  async function start() {
    setStarting(true);
    try {
      const r = await api<Run>(`/leads/${id}/runs`, { method: "POST", json: { campaign: "Manual run" } });
      router.push(`/runs/${r.id}`);
    } catch (e) { toast("err", e instanceof ApiError ? e.message : "Could not start run"); setStarting(false); }
  }
  async function submitReply(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);
    try {
      const r = await api<Run>(`/leads/${id}/replies`, { method: "POST", json: { body: replyText } });
      toast("ok", "Reply submitted for triage");
      setReplyText("");
      router.push(`/runs/${r.id}`);
    } catch (e2) { toast("err", e2 instanceof ApiError ? e2.message : "Could not submit reply"); } finally { setSending(false); }
  }
  async function remove() {
    if (!window.confirm(`Delete ${name}? This removes their runs and drafts.`)) return;
    try { await api(`/leads/${id}`, { method: "DELETE" }); router.push("/leads"); } catch (e) { toast("err", e instanceof ApiError ? e.message : "Delete failed"); }
  }

  return (
    <div className="animate-fade-in">
      <Link href="/leads" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" /> All leads</Link>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-semibold tracking-tight">{name}</h1><StatusBadge status={l.status} />
            {l.icp_score != null && <Badge tone={l.icp_score >= 75 ? "success" : l.icp_score >= 50 ? "warning" : "danger"}>ICP {l.icp_score}</Badge>}</div>
          <p className="mt-1 text-sm text-muted-foreground">{l.title ? `${l.title} · ` : ""}{l.email}</p>
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
            {l.company && <span className="inline-flex items-center gap-1"><Building2 className="h-3.5 w-3.5" />{l.company}</span>}
            {l.website && <span className="inline-flex items-center gap-1"><Globe className="h-3.5 w-3.5" />{l.website}</span>}
            <span>Added {timeAgo(l.created_at)} via {l.source}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={remove}><Trash2 className="h-4 w-4" /> Delete</Button>
          <Button onClick={start} loading={starting} disabled={l.status === "unsubscribed"}><Play className="h-4 w-4" /> Run agents</Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Research brief" description={brief ? "Generated by the Researcher agent" : "Run the agents to generate a brief"} />
          <CardBody>
            {!brief ? <p className="text-sm text-muted-foreground">No research yet.</p> : (
              <div className="space-y-4">
                <p className="text-sm leading-relaxed">{String(brief.company_summary ?? "")}</p>
                <p className="text-sm leading-relaxed text-muted-foreground">{String(brief.person_summary ?? "")}</p>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div><p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Signals</p><List items={brief.recent_signals} /></div>
                  <div><p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Pain points</p><List items={brief.pain_points} /></div>
                  <div><p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Talking points</p><List items={brief.talking_points} /></div>
                </div>
              </div>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Firmographics" description="Enricher agent" />
          <CardBody>
            {!firmo ? <p className="text-sm text-muted-foreground">Not enriched yet.</p> : (
              <dl className="space-y-2 text-sm">
                {[["Industry", firmo.industry], ["Employees", firmo.employee_estimate], ["Region", firmo.region], ["Funding", firmo.funding_stage], ["Persona", String(firmo.buying_persona ?? "").replace(/_/g, " ")], ["Fit tier", firmo.fit_tier]].map(([k, v]) => (
                  <div key={String(k)} className="flex justify-between gap-3"><dt className="text-muted-foreground">{String(k)}</dt><dd className="text-right font-medium">{String(v ?? "-")}</dd></div>
                ))}
                {Array.isArray(firmo.tech_stack) && <div className="flex flex-wrap gap-1.5 pt-2">{(firmo.tech_stack as string[]).map((t) => <Badge key={t} tone="primary">{t}</Badge>)}</div>}
                <p className="pt-2 text-xs leading-relaxed text-muted-foreground">{String(firmo.icp_reasoning ?? "")}</p>
              </dl>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Email drafts" description="Sequence steps for this lead" />
          <CardBody className="space-y-4">
            {!approvals.data ? <Skeleton className="h-24" /> : approvals.data.length === 0 ? <p className="text-sm text-muted-foreground">No drafts yet.</p> :
              approvals.data.map((a) => <ApprovalCard key={a.id} approval={{ ...a, lead_name: name }} showLead={false} onChange={() => approvals.reload()} />)}
          </CardBody>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader title="Replies" description="Paste a reply to triage it, or connect the inbound webhook in Settings" />
            <CardBody className="space-y-4">
              <form onSubmit={submitReply} className="space-y-2">
                <Textarea required value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="Paste the lead's reply here..." aria-label="Reply text" />
                <div className="flex justify-end"><Button size="sm" type="submit" loading={sending} disabled={!replyText.trim()}><Send className="h-3.5 w-3.5" /> Triage reply</Button></div>
              </form>
              {replies.data?.map((r) => (
                <div key={r.id} className="rounded-xl border bg-muted/30 p-3">
                  <div className="mb-1.5 flex items-center gap-2">
                    {r.classification && <Badge tone={CLS_TONE[r.classification] ?? "neutral"}>{r.classification.replace(/_/g, " ")}</Badge>}
                    {r.confidence != null && <span className="text-xs text-muted-foreground">{Math.round(r.confidence * 100)}% confidence</span>}
                    <span className="ml-auto text-xs text-muted-foreground">{timeAgo(r.created_at)} · {r.source}</span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm">{r.body}</p>
                  {r.summary && <p className="mt-1.5 text-xs text-muted-foreground">{r.summary}</p>}
                </div>
              ))}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Run history" />
            <CardBody className="space-y-2">
              {!runs.data ? <Skeleton className="h-16" /> : runs.data.length === 0 ? <p className="text-sm text-muted-foreground">No runs yet.</p> :
                runs.data.map((r) => (
                  <Link key={r.id} href={`/runs/${r.id}`} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm transition hover:bg-muted/50">
                    <span>{r.kind === "triage" ? "Reply triage" : r.campaign || "Outreach"} <span className="text-xs text-muted-foreground">· {timeAgo(r.created_at)}</span></span>
                    <StatusBadge status={r.status} />
                  </Link>
                ))}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
