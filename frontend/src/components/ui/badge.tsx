import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  neutral: "bg-muted text-muted-foreground",
  primary: "bg-primary/15 text-primary",
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  danger: "bg-danger/15 text-danger",
  accent: "bg-accent/15 text-accent",
};

export function Badge({ tone = "neutral", className, children, dot }: { tone?: keyof typeof tones; className?: string; children: React.ReactNode; dot?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", tones[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, keyof typeof tones> = {
  new: "neutral", researched: "accent", awaiting_approval: "warning", contacted: "primary", replied: "accent",
  interested: "success", unsubscribed: "danger", bounced: "danger",
  queued: "neutral", running: "primary", scheduled: "accent", completed: "success", failed: "danger", rejected: "danger", cancelled: "neutral",
  pending: "warning", approved: "accent", sent: "success", succeeded: "success", skipped: "neutral",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "neutral"} dot>{status.replace(/_/g, " ")}</Badge>;
}
