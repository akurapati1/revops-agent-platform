"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Play, Plus, Search, Upload, Users } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { cn, timeAgo } from "@/lib/utils";
import type { ImportResult, Lead, LeadPage } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";

const STATUSES = ["new", "researched", "awaiting_approval", "contacted", "replied", "interested", "unsubscribed"];
const PAGE = 25;

function ScoreBar({ score }: { score: number | null }) {
  if (score == null) return <span className="text-xs text-muted-foreground">-</span>;
  const tone = score >= 75 ? "bg-success" : score >= 50 ? "bg-warning" : "bg-danger";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted"><div className={cn("h-full rounded-full", tone)} style={{ width: `${score}%` }} /></div>
      <span className="text-xs tabular-nums">{score}</span>
    </div>
  );
}

export default function LeadsPage() {
  const router = useRouter();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [minScore, setMinScore] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(q); setOffset(0); }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
  if (debounced) params.set("q", debounced);
  if (status) params.set("status", status);
  if (minScore) params.set("min_score", minScore);
  const { data, error, loading, reload } = useFetch<LeadPage>(`/leads?${params}`);

  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const allOnPage = !!data && data.items.length > 0 && data.items.every((l) => selected.has(l.id));

  async function runSelected() {
    setRunning(true);
    try {
      await api("/runs/bulk", { method: "POST", json: { lead_ids: [...selected], campaign: "Bulk run" } });
      toast("ok", `Launched ${selected.size} agent run${selected.size > 1 ? "s" : ""}`);
      setSelected(new Set());
      router.push("/runs");
    } catch (e) {
      toast("err", e instanceof ApiError ? e.message : "Could not start runs");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader title="Leads" description="Manage prospects and launch agent runs."
        actions={<>
          <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}><Upload className="h-4 w-4" /> Import CSV</Button>
          <Button size="sm" onClick={() => setAddOpen(true)}><Plus className="h-4 w-4" /> Add lead</Button>
        </>} />

      <Card>
        <div className="flex flex-col gap-3 border-b p-4 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search name, company or email" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search leads" />
          </div>
          <Select className="lg:w-48" value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} aria-label="Filter by status">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </Select>
          <Select className="lg:w-40" value={minScore} onChange={(e) => { setMinScore(e.target.value); setOffset(0); }} aria-label="Minimum ICP score">
            <option value="">Any ICP score</option>
            <option value="50">ICP 50+</option>
            <option value="75">ICP 75+</option>
          </Select>
          {selected.size > 0 && <Button size="sm" onClick={runSelected} loading={running}><Play className="h-4 w-4" /> Run agents ({selected.size})</Button>}
        </div>

        {error && !data ? <ErrorState message={error} onRetry={reload} /> : loading && !data ? (
          <div className="space-y-2 p-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : data && data.items.length === 0 ? (
          <EmptyState icon={<Users className="h-6 w-6" />} title={debounced || status || minScore ? "No leads match your filters" : "No leads yet"}
            description={debounced || status || minScore ? "Try clearing a filter." : "Add a lead manually or import a CSV to get started."}
            action={!(debounced || status || minScore) ? <Button size="sm" onClick={() => setAddOpen(true)}><Plus className="h-4 w-4" /> Add your first lead</Button> : undefined} />
        ) : data && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="w-10 px-4 py-3"><input type="checkbox" aria-label="Select all" checked={allOnPage} onChange={() => setSelected(allOnPage ? new Set() : new Set(data.items.map((l) => l.id)))} /></th>
                    <th className="px-2 py-3 font-medium">Lead</th><th className="px-2 py-3 font-medium">Company</th>
                    <th className="px-2 py-3 font-medium">ICP fit</th><th className="px-2 py-3 font-medium">Status</th><th className="px-4 py-3 font-medium">Added</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.items.map((l: Lead) => (
                    <tr key={l.id} className="transition hover:bg-muted/40">
                      <td className="px-4 py-3"><input type="checkbox" aria-label={`Select ${l.email}`} checked={selected.has(l.id)} onChange={() => toggle(l.id)} /></td>
                      <td className="px-2 py-3">
                        <Link href={`/leads/${l.id}`} className="font-medium hover:text-primary">{`${l.first_name} ${l.last_name}`.trim() || l.email}</Link>
                        <p className="text-xs text-muted-foreground">{l.title ? `${l.title} · ` : ""}{l.email}</p>
                      </td>
                      <td className="px-2 py-3">{l.company || <span className="text-muted-foreground">-</span>}</td>
                      <td className="px-2 py-3"><ScoreBar score={l.icp_score} /></td>
                      <td className="px-2 py-3"><StatusBadge status={l.status} /></td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{timeAgo(l.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t px-4 py-3 text-xs text-muted-foreground">
              <span>{offset + 1}-{Math.min(offset + PAGE, data.total)} of {data.total}</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
                <Button variant="outline" size="sm" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
              </div>
            </div>
          </>
        )}
      </Card>

      <AddLeadDialog open={addOpen} onClose={() => setAddOpen(false)} onDone={() => { setAddOpen(false); reload(); }} />
      <ImportDialog open={importOpen} onClose={() => setImportOpen(false)} onDone={reload} />
    </div>
  );
}

function AddLeadDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const empty = { email: "", first_name: "", last_name: "", company: "", title: "", website: "", notes: "" };
  const [f, setF] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await api("/leads", { method: "POST", json: f });
      toast("ok", "Lead added");
      setF(empty);
      onDone();
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : "Could not add lead");
    } finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onClose={onClose} title="Add lead" description="Agents use these details to research and personalize outreach.">
      <form onSubmit={submit} className="space-y-3">
        <Field label="Email *"><Input type="email" required value={f.email} onChange={set("email")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="First name"><Input value={f.first_name} onChange={set("first_name")} /></Field>
          <Field label="Last name"><Input value={f.last_name} onChange={set("last_name")} /></Field>
          <Field label="Company"><Input value={f.company} onChange={set("company")} /></Field>
          <Field label="Title"><Input value={f.title} onChange={set("title")} /></Field>
        </div>
        <Field label="Website"><Input value={f.website} onChange={set("website")} placeholder="acme.com" /></Field>
        <Field label="Notes"><Textarea value={f.notes} onChange={set("notes")} placeholder="Context for the agents (optional)" /></Field>
        {err && <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{err}</p>}
        <div className="flex justify-end gap-2 pt-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button type="submit" loading={busy}>Add lead</Button></div>
      </form>
    </Dialog>
  );
}

function ImportDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) { setErr("Choose a CSV file first"); return; }
    const form = new FormData();
    form.append("file", file);
    setBusy(true); setErr(null);
    try {
      const r = await api<ImportResult>("/leads/import", { method: "POST", form });
      setResult(r);
      toast("ok", `Imported ${r.created} lead${r.created === 1 ? "" : "s"}`);
      onDone();
    } catch (x) { setErr(x instanceof ApiError ? x.message : "Import failed"); } finally { setBusy(false); }
  }
  function close() { setResult(null); setErr(null); onClose(); }

  return (
    <Dialog open={open} onClose={close} title="Import leads from CSV" description="Needs an email column. Optional: first_name, last_name, company, title, website, linkedin, notes. Duplicates are skipped.">
      {result ? (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3 text-center">
            {[["Created", result.created, "text-success"], ["Skipped", result.skipped, "text-warning"], ["Errors", result.errors.length, "text-danger"]].map(([l, n, c]) => (
              <div key={l as string} className="rounded-xl bg-muted/60 p-3"><p className={cn("text-2xl font-semibold", c as string)}>{n as number}</p><p className="text-xs text-muted-foreground">{l as string}</p></div>
            ))}
          </div>
          {result.errors.length > 0 && <ul className="max-h-32 space-y-1 overflow-y-auto rounded-lg bg-danger/10 p-3 text-xs text-danger">{result.errors.map((e) => <li key={e.row}>Row {e.row}: {e.error}</li>)}</ul>}
          <div className="flex justify-end"><Button onClick={close}>Done</Button></div>
        </div>
      ) : (
        <form onSubmit={upload} className="space-y-4">
          <input ref={fileRef} type="file" accept=".csv,text/csv" aria-label="CSV file" className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-primary/20 file:px-3 file:py-2 file:text-sm file:font-medium file:text-foreground" />
          {err && <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{err}</p>}
          <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={close}>Cancel</Button><Button type="submit" loading={busy}><Upload className="h-4 w-4" /> Import</Button></div>
        </form>
      )}
    </Dialog>
  );
}
