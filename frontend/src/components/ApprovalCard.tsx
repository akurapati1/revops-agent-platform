"use client";
import Link from "next/link";
import { useState } from "react";
import { CalendarClock, Check, Pencil, Reply, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import type { Approval } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { Input, Textarea } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";

export function ApprovalCard({ approval, onChange, showLead = true }: { approval: Approval; onChange: (a: Approval) => void; showLead?: boolean }) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(approval.subject);
  const [body, setBody] = useState(approval.body);
  const [busy, setBusy] = useState<string | null>(null);
  const pending = approval.status === "pending";

  async function act(kind: "approve" | "reject" | "save") {
    setBusy(kind);
    try {
      if (kind === "save") {
        onChange(await api<Approval>(`/approvals/${approval.id}`, { method: "PATCH", json: { subject, body } }));
        setEditing(false);
        toast("ok", "Draft updated");
      } else {
        const a = await api<Approval>(`/approvals/${approval.id}/${kind}`, { method: "POST" });
        onChange(a);
        toast("ok", kind === "reject" ? "Draft rejected" : a.status === "sent" ? "Approved and sent" : "Approved and scheduled");
      }
    } catch (e) {
      toast("err", e instanceof ApiError ? e.message : "Action failed");
    } finally { setBusy(null); }
  }

  return (
    <div className="glass overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-5 py-3">
        {approval.kind === "reply" ? <Reply className="h-4 w-4 text-accent" /> : <span className="rounded-md bg-primary/15 px-2 py-0.5 text-xs font-semibold text-primary">Step {approval.step_number}</span>}
        <div className="min-w-0 flex-1 text-sm">
          {showLead && <Link href={`/leads/${approval.lead_id}`} className="font-medium hover:text-primary">{approval.lead_name}</Link>}
          {showLead && approval.lead_company && <span className="text-muted-foreground"> · {approval.lead_company}</span>}
          <p className="truncate text-xs text-muted-foreground">To: {approval.to_email}</p>
        </div>
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><CalendarClock className="h-3.5 w-3.5" />{approval.status === "sent" ? `Sent ${fmtDate(approval.sent_at)}` : `Sends ${fmtDate(approval.scheduled_at)}`}</span>
        <StatusBadge status={approval.status} />
      </div>
      <div className="space-y-3 px-5 py-4">
        {editing ? (
          <>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
            <Textarea rows={9} value={body} onChange={(e) => setBody(e.target.value)} aria-label="Body" />
          </>
        ) : (
          <>
            <p className="font-medium">{approval.subject}</p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{approval.body}</p>
          </>
        )}
        {approval.error && <p className="text-xs text-danger">{approval.error}</p>}
      </div>
      {pending && (
        <div className="flex flex-wrap justify-end gap-2 border-t bg-muted/30 px-5 py-3">
          {editing ? (
            <>
              <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setSubject(approval.subject); setBody(approval.body); }}>Cancel</Button>
              <Button variant="secondary" size="sm" loading={busy === "save"} onClick={() => act("save")}>Save changes</Button>
            </>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" /> Edit</Button>
          )}
          <Button variant="danger" size="sm" loading={busy === "reject"} disabled={editing} onClick={() => act("reject")}><X className="h-3.5 w-3.5" /> Reject</Button>
          <Button size="sm" loading={busy === "approve"} disabled={editing} onClick={() => act("approve")}><Check className="h-3.5 w-3.5" /> Approve</Button>
        </div>
      )}
    </div>
  );
}
