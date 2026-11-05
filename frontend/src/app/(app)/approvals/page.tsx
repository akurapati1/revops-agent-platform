"use client";
import { useState } from "react";
import { CheckSquare } from "lucide-react";
import { useFetch } from "@/lib/hooks";
import type { Approval } from "@/lib/types";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Tabs } from "@/components/ui/tabs";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/states";

type Tab = "pending" | "approved" | "sent" | "rejected";

export default function ApprovalsPage() {
  const [tab, setTab] = useState<Tab>("pending");
  const { data, error, loading, reload, setData } = useFetch<Approval[]>(`/approvals?status=${tab}`, { interval: 10000 });

  return (
    <div className="animate-fade-in">
      <PageHeader title="Approval queue" description="Agents draft. You decide. Nothing is sent until you approve it here." />
      <Tabs<Tab> value={tab} onChange={setTab} tabs={[
        { id: "pending", label: "Needs review" }, { id: "approved", label: "Scheduled" }, { id: "sent", label: "Sent" }, { id: "rejected", label: "Rejected" },
      ]} />
      {error && !data ? <ErrorState message={error} onRetry={reload} /> : loading && !data ? (
        <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-44" />)}</div>
      ) : data && data.length === 0 ? (
        <div className="glass"><EmptyState icon={<CheckSquare className="h-6 w-6" />} title={tab === "pending" ? "Inbox zero" : "Nothing here yet"}
          description={tab === "pending" ? "No drafts are waiting for review. Launch an agent run from the Leads page." : "Items will appear here as they move through the pipeline."} /></div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {data?.map((a) => (
            <ApprovalCard key={a.id} approval={a} onChange={(u) => { setData((cur) => cur ? cur.map((x) => x.id === u.id ? u : x).filter((x) => x.status === tab) : cur); }} />
          ))}
        </div>
      )}
    </div>
  );
}
