"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Ban, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtCost, fmtDate, fmtNumber } from "@/lib/utils";
import type { Approval, RunDetail } from "@/lib/types";
import { RunTrace } from "@/components/RunTrace";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [cancelling, setCancelling] = useState(false);
  const { data, error, reload, setData } = useFetch<RunDetail>(`/runs/${id}`, {
    interval: () => (document.hidden ? false : 1500),
  });

  if (error && !data) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>;

  const live = data.status === "queued" || data.status === "running";
  const cancellable = ["queued", "awaiting_approval", "scheduled"].includes(data.status);

  async function cancel() {
    setCancelling(true);
    try {
      await api(`/runs/${id}/cancel`, { method: "POST" });
      toast("ok", "Run cancelled");
      reload();
    } catch (e) { toast("err", e instanceof ApiError ? e.message : "Could not cancel"); } finally { setCancelling(false); }
  }
  const onApproval = (a: Approval) => { setData((cur) => cur ? { ...cur, approvals: cur.approvals.map((x) => x.id === a.id ? a : x) } : cur); reload(); };

  return (
    <div className="animate-fade-in">
      <Link href="/runs" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" /> All runs</Link>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{data.lead_company || data.lead_email}</h1>
            <StatusBadge status={data.status} />
            {live && <span className="inline-flex items-center gap-1.5 text-xs text-primary"><span className="h-2 w-2 animate-pulse rounded-full bg-primary" /> Live</span>}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            <Link href={`/leads/${data.lead_id}`} className="hover:text-primary">{data.lead_email}</Link> · {data.kind === "triage" ? "Reply triage" : data.campaign || "Outreach run"} · started {fmtDate(data.created_at)}
          </p>
        </div>
        {cancellable && <Button variant="danger" size="sm" loading={cancelling} onClick={cancel}><Ban className="h-4 w-4" /> Cancel run</Button>}
      </div>

      <div className="mb-6 grid grid-cols-3 gap-3">
        {[["Tokens", fmtNumber(data.total_tokens)], ["Cost", fmtCost(data.total_cost_usd)], ["Steps", `${data.steps.filter((s) => s.status === "succeeded").length}/${data.steps.length}`]].map(([l, v]) => (
          <Card key={l} className="p-4"><p className="text-xs text-muted-foreground">{l}</p><p className="mt-1 text-xl font-semibold">{v}</p></Card>
        ))}
      </div>
      {data.error && <p role="alert" className="mb-6 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">{data.error}</p>}

      <div className="grid gap-6 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">Execution trace</h2>
          {data.steps.length === 0 ? <Skeleton className="h-40" /> : <RunTrace steps={data.steps} />}
          {data.status === "awaiting_approval" && (
            <div className="flex items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
              <ShieldCheck className="h-5 w-5 shrink-0" /> Paused at the human approval gate. Review the drafts to continue.
            </div>
          )}
        </div>
        <div className="xl:col-span-2">
          <Card>
            <CardHeader title="Drafts" description={data.approvals.length ? "Review before anything is sent" : "Drafts appear once the sequencer finishes"} />
            <CardBody className="space-y-4">
              {data.approvals.length === 0 ? <p className="text-sm text-muted-foreground">No drafts yet.</p> :
                data.approvals.map((a) => <ApprovalCard key={a.id} approval={{ ...a, lead_name: data.lead_email }} onChange={onApproval} showLead={false} />)}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
