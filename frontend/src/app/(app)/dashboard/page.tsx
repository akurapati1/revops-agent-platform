"use client";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CheckSquare, Coins, Mail, MessageSquareReply, Target, Users, Workflow } from "lucide-react";
import { useFetch } from "@/lib/hooks";
import { fmtCost, fmtNumber, timeAgo } from "@/lib/utils";
import type { Run, Stats } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const COLORS = ["#8b5cf6", "#9a6cf5", "#a87bf0", "#8f8ff2", "#66a7f5", "#34c2ef", "#22d3ee"];
const tooltipStyle = { background: "hsl(226 32% 9%)", border: "1px solid hsl(225 22% 18%)", borderRadius: 12, fontSize: 12, color: "#e5e7eb" };

function Kpi({ label, value, hint, icon: Icon, href, tone }: { label: string; value: string; hint?: string; icon: typeof Users; href?: string; tone: string }) {
  const body = (
    <Card className="p-5 transition hover:-translate-y-0.5 hover:border-primary/40">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${tone}`}><Icon className="h-4 w-4" /></span>
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </Card>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

export default function Dashboard() {
  const stats = useFetch<Stats>("/dashboard/stats", { interval: 10000 });
  const runs = useFetch<Run[]>("/runs?limit=6", { interval: 5000 });

  if (stats.error && !stats.data) return <ErrorState message={stats.error} onRetry={stats.reload} />;
  const s = stats.data;

  return (
    <div className="animate-fade-in">
      <PageHeader title="Dashboard" description="Pipeline health, agent activity and spend at a glance."
        actions={<><Link href="/leads"><Button variant="outline" size="sm">Add leads</Button></Link><Link href="/approvals"><Button size="sm">Review approvals</Button></Link></>} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {!s ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32" />) : (
          <>
            <Kpi label="Total leads" value={fmtNumber(s.kpis.total_leads)} hint={s.kpis.avg_icp_score != null ? `Avg ICP score ${s.kpis.avg_icp_score}` : "No scored leads yet"} icon={Users} href="/leads" tone="bg-primary/15 text-primary" />
            <Kpi label="Pending approvals" value={fmtNumber(s.kpis.pending_approvals)} hint="Drafts waiting for review" icon={CheckSquare} href="/approvals" tone="bg-warning/15 text-warning" />
            <Kpi label="Emails sent" value={fmtNumber(s.kpis.emails_sent)} hint={`Reply rate ${(s.kpis.reply_rate * 100).toFixed(0)}%`} icon={Mail} tone="bg-success/15 text-success" />
            <Kpi label="AI spend (month)" value={fmtCost(s.usage.cost_usd)} hint={`${fmtNumber(s.usage.tokens)} / ${fmtNumber(s.usage.limit)} tokens`} icon={Coins} href="/settings?tab=usage" tone="bg-accent/15 text-accent" />
          </>
        )}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader title="Pipeline funnel" description="From raw lead to interested reply" />
          <CardBody className="h-72">
            {!s ? <Skeleton className="h-full" /> : s.funnel[0].count === 0 ? (
              <EmptyState icon={<Target className="h-6 w-6" />} title="No pipeline yet" description="Add leads and launch an agent run to see your funnel fill up." />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={s.funnel} layout="vertical" margin={{ left: 8, right: 24 }}>
                  <CartesianGrid horizontal={false} stroke="hsl(225 22% 18%)" />
                  <XAxis type="number" allowDecimals={false} stroke="#6b7280" fontSize={11} />
                  <YAxis type="category" dataKey="stage" width={96} stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(139,92,246,0.08)" }} />
                  <Bar dataKey="count" radius={[0, 8, 8, 0]} barSize={22}>
                    {s.funnel.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Agent runs" description="Last 14 days" />
          <CardBody className="h-72">
            {!s ? <Skeleton className="h-full" /> : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={s.runs_per_day.map((d) => ({ ...d, label: d.date.slice(5) }))} margin={{ left: -20, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="hsl(225 22% 18%)" />
                  <XAxis dataKey="label" stroke="#6b7280" fontSize={11} tickLine={false} interval={2} />
                  <YAxis allowDecimals={false} stroke="#6b7280" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="runs" stroke="#22d3ee" strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Recent activity" action={<Link href="/runs" className="text-xs text-primary hover:underline">View all</Link>} />
        {runs.error && !runs.data ? <ErrorState message={runs.error} onRetry={runs.reload} /> : !runs.data ? (
          <CardBody className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</CardBody>
        ) : runs.data.length === 0 ? (
          <EmptyState icon={<Workflow className="h-6 w-6" />} title="No runs yet" description="Launch your first agent run from a lead's page." action={<Link href="/leads"><Button size="sm">Go to leads</Button></Link>} />
        ) : (
          <ul className="divide-y">
            {runs.data.map((r) => (
              <li key={r.id}>
                <Link href={`/runs/${r.id}`} className="flex items-center gap-4 px-5 py-3 transition hover:bg-muted/40">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">{r.kind === "triage" ? <MessageSquareReply className="h-4 w-4" /> : <Workflow className="h-4 w-4" />}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{r.lead_company || r.lead_email}</p>
                    <p className="truncate text-xs text-muted-foreground">{r.kind === "triage" ? "Reply triage" : r.campaign || "Outreach"} · {timeAgo(r.created_at)}</p>
                  </div>
                  <span className="hidden text-xs text-muted-foreground sm:block">{fmtNumber(r.total_tokens)} tok</span>
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
