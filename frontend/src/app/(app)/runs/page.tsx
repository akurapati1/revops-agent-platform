"use client";
import Link from "next/link";
import { useState } from "react";
import { MessageSquareReply, Workflow } from "lucide-react";
import { useFetch } from "@/lib/hooks";
import { fmtCost, fmtNumber, timeAgo } from "@/lib/utils";
import type { Run } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { StatusBadge } from "@/components/ui/badge";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { Button } from "@/components/ui/button";

const ACTIVE = new Set(["queued", "running"]);

export default function RunsPage() {
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useFetch<Run[]>(`/runs?limit=100${status ? `&status=${status}` : ""}`, { interval: 3000 });
  return (
    <div className="animate-fade-in">
      <PageHeader title="Agent runs" description="Every run is a traced DAG: researcher, enricher, personalizer, sequencer."
        actions={<Select className="w-44" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          <option value="">All statuses</option>
          {["queued", "running", "awaiting_approval", "scheduled", "completed", "failed", "rejected", "cancelled"].map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </Select>} />
      <Card>
        {error && !data ? <ErrorState message={error} onRetry={reload} /> : loading && !data ? (
          <div className="space-y-2 p-4">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
        ) : data && data.length === 0 ? (
          <EmptyState icon={<Workflow className="h-6 w-6" />} title="No runs found" description="Open a lead and launch an agent run, or select several leads and run them together."
            action={<Link href="/leads"><Button size="sm">Go to leads</Button></Link>} />
        ) : (
          <ul className="divide-y">
            {data?.map((r) => (
              <li key={r.id}>
                <Link href={`/runs/${r.id}`} className="flex items-center gap-4 px-5 py-4 transition hover:bg-muted/40">
                  <span className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    {r.kind === "triage" ? <MessageSquareReply className="h-5 w-5" /> : <Workflow className="h-5 w-5" />}
                    {ACTIVE.has(r.status) && <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 animate-pulse rounded-full bg-primary" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{r.lead_company || r.lead_email}</p>
                    <p className="truncate text-xs text-muted-foreground">{r.lead_email} · {r.kind === "triage" ? "Reply triage" : r.campaign || "Outreach"} · {timeAgo(r.created_at)}</p>
                  </div>
                  <div className="hidden text-right text-xs text-muted-foreground sm:block"><p>{fmtNumber(r.total_tokens)} tokens</p><p>{fmtCost(r.total_cost_usd)}</p></div>
                  <StatusBadge status={r.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
