"use client";
import { useState } from "react";
import { AlertCircle, Brain, CalendarClock, CheckCircle2, ChevronDown, Circle, Clock, Coins, Inbox, Loader2, Mail, Search, Target, Wrench, XCircle } from "lucide-react";
import { cn, fmtCost, fmtMs } from "@/lib/utils";
import type { Step } from "@/lib/types";

const AGENT_META: Record<string, { label: string; icon: typeof Search; blurb: string }> = {
  researcher: { label: "Researcher", icon: Search, blurb: "Company and person brief" },
  enricher: { label: "Enricher", icon: Target, blurb: "Firmographics and ICP score" },
  personalizer: { label: "Personalizer", icon: Mail, blurb: "Tailored email sequence" },
  sequencer: { label: "Sequencer", icon: CalendarClock, blurb: "Business-day schedule" },
  triage: { label: "Reply Triage", icon: Inbox, blurb: "Classification and draft reply" },
};

function StatusIcon({ status }: { status: Step["status"] }) {
  if (status === "succeeded") return <CheckCircle2 className="h-5 w-5 text-success" />;
  if (status === "failed") return <XCircle className="h-5 w-5 text-danger" />;
  if (status === "running") return <Loader2 className="h-5 w-5 animate-spin text-primary" />;
  return <Circle className="h-5 w-5 text-muted-foreground/50" />;
}

function Json({ value }: { value: unknown }) {
  return <pre className="max-h-80 overflow-auto rounded-lg bg-background/60 p-3 font-mono text-xs leading-relaxed text-muted-foreground">{JSON.stringify(value, null, 2)}</pre>;
}

function StepCard({ step, last }: { step: Step; last: boolean }) {
  const [open, setOpen] = useState(step.status === "failed");
  const meta = AGENT_META[step.agent] ?? { label: step.agent, icon: Brain, blurb: "" };
  const Icon = meta.icon;
  const tokens = step.tokens_in + step.tokens_out;
  return (
    <li className="relative flex gap-4">
      {!last && <span className="absolute left-[19px] top-10 h-[calc(100%-1.5rem)] w-px bg-border" />}
      <div className={cn("z-10 mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border bg-card", step.status === "running" && "animate-pulseRing border-primary")}>
        <StatusIcon status={step.status} />
      </div>
      <div className="mb-4 min-w-0 flex-1 rounded-xl border bg-card/50">
        <button className="flex w-full items-center gap-3 px-4 py-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
          <Icon className="h-4 w-4 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">{meta.label}</p>
            <p className="truncate text-xs text-muted-foreground">{meta.blurb}{step.model ? ` · ${step.model}` : ""}</p>
          </div>
          <div className="hidden items-center gap-4 text-xs text-muted-foreground sm:flex">
            {step.status !== "pending" && step.status !== "running" && (
              <>
                <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{fmtMs(step.latency_ms)}</span>
                {tokens > 0 && <span className="inline-flex items-center gap-1"><Brain className="h-3 w-3" />{tokens.toLocaleString()} tok</span>}
                {tokens > 0 && <span className="inline-flex items-center gap-1"><Coins className="h-3 w-3" />{fmtCost(step.cost_usd)}</span>}
              </>
            )}
          </div>
          <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition", open && "rotate-180")} />
        </button>
        {open && (
          <div className="space-y-4 border-t px-4 py-4">
            {step.error && <p className="flex items-start gap-2 rounded-lg bg-danger/10 p-3 text-sm text-danger"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{step.error}</p>}
            {step.attempts > 1 && <p className="text-xs text-warning">Needed {step.attempts} attempts to produce valid structured output.</p>}
            {step.tool_calls.length > 0 && (
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground"><Wrench className="h-3 w-3" /> Tool calls</p>
                <Json value={step.tool_calls} />
              </div>
            )}
            <div className="grid gap-4 lg:grid-cols-2">
              <div><p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Input</p><Json value={step.input} /></div>
              <div><p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Output</p>{step.output ? <Json value={step.output} /> : <p className="text-xs text-muted-foreground">No output.</p>}</div>
            </div>
            <p className="text-xs text-muted-foreground sm:hidden">{fmtMs(step.latency_ms)} · {tokens.toLocaleString()} tokens · {fmtCost(step.cost_usd)}</p>
          </div>
        )}
      </div>
    </li>
  );
}

export function RunTrace({ steps }: { steps: Step[] }) {
  return <ol aria-label="Run trace">{steps.map((s, i) => <StepCard key={s.id} step={s} last={i === steps.length - 1} />)}</ol>;
}
