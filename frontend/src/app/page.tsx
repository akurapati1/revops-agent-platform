import Link from "next/link";
import { ArrowRight, BadgeCheck, BarChart3, Bot, Brain, CalendarClock, Inbox, Mail, Search, ShieldCheck, Sparkles, Target, Workflow } from "lucide-react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";

const agents = [
  { icon: Search, name: "Researcher", text: "Builds a company and person brief with real signals and pain points." },
  { icon: Target, name: "Enricher", text: "Extracts firmographics and scores ICP fit with a transparent rubric." },
  { icon: Mail, name: "Personalizer", text: "Writes a tailored multi-step email sequence for every lead." },
  { icon: CalendarClock, name: "Sequencer", text: "Schedules each step onto business days, deterministically." },
  { icon: Inbox, name: "Reply Triage", text: "Classifies replies and drafts the response, ready for review." },
];

const features = [
  { icon: ShieldCheck, title: "Human approval gate", text: "Nothing is sent until a teammate reviews, edits and approves the draft. Every run pauses by design." },
  { icon: Workflow, title: "DAG orchestration", text: "Agents run in dependency order over a shared run state, and every step is persisted." },
  { icon: BarChart3, title: "Full trace and cost", text: "See each agent's input, output, tokens, latency and cost. Per-org monthly usage limits included." },
  { icon: Brain, title: "Bring your own model", text: "OpenRouter with per-agent model choice, or the offline mock LLM for demos and tests." },
  { icon: BadgeCheck, title: "Multi-tenant by default", text: "Orgs, roles and tenant-scoped queries, with email, Google and GitHub sign-in." },
  { icon: Bot, title: "Pluggable delivery", text: "Console provider out of the box, SMTP when you are ready. Swap with one env var." },
];

export default function Landing() {
  return (
    <div className="relative overflow-hidden">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-2">
          <Link href="/login"><Button variant="ghost" size="sm">Sign in</Button></Link>
          <Link href="/signup"><Button size="sm">Get started</Button></Link>
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-4 pb-16 pt-14 text-center sm:px-6 sm:pt-24">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border bg-card/60 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
          <Sparkles className="h-3.5 w-3.5 text-accent" /> Autonomous outbound, with a human in the loop
        </div>
        <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
          Your sales pipeline, run by <span className="gradient-text">a team of AI agents</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base text-muted-foreground sm:text-lg">
          Research every lead, score fit, write personalized sequences and triage replies, then approve with one click.
          Every step is traced, costed and tenant-isolated.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/signup"><Button size="lg">Start free <ArrowRight className="h-4 w-4" /></Button></Link>
          <Link href="/login"><Button size="lg" variant="outline">Sign in</Button></Link>
        </div>

        <div className="glass mx-auto mt-16 max-w-4xl p-4 sm:p-6">
          <p className="mb-4 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">Agent pipeline</p>
          <div className="grid gap-3 sm:grid-cols-5">
            {agents.map((a, i) => (
              <div key={a.name} className="relative rounded-xl border bg-muted/40 p-4 text-left animate-fade-in" style={{ animationDelay: `${i * 90}ms` }}>
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary"><a.icon className="h-4.5 w-4.5" size={18} /></div>
                <p className="text-sm font-semibold">{a.name}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{a.text}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-center gap-2 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
            <ShieldCheck className="h-4 w-4" /> Approval gate: nothing leaves your outbox until a human says so
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="glass p-6 transition hover:-translate-y-0.5 hover:border-primary/40">
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/25 to-accent/20 text-primary"><f.icon className="h-5 w-5" /></div>
              <h3 className="font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.text}</p>
            </div>
          ))}
        </div>
        <div className="glass mt-10 flex flex-col items-center gap-4 bg-gradient-to-br from-primary/15 to-accent/10 p-10 text-center">
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Ship your first agent run in minutes</h2>
          <p className="max-w-lg text-sm text-muted-foreground">Works offline with the built-in mock model, so you can explore the whole product without an API key.</p>
          <Link href="/signup"><Button size="lg">Create your workspace <ArrowRight className="h-4 w-4" /></Button></Link>
        </div>
      </section>
      <footer className="border-t py-8 text-center text-xs text-muted-foreground">RevOps Agent Platform · MIT licensed</footer>
    </div>
  );
}
