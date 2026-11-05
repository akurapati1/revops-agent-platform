export interface Tokens { access_token: string; refresh_token: string }
export interface OrgBrief { id: string; name: string; slug: string; role: "owner" | "admin" | "member" }
export interface User { id: string; email: string; name: string; avatar_url: string | null }
export interface Me { user: User; org: OrgBrief | null; orgs: OrgBrief[] }

export interface Lead {
  id: string; email: string; first_name: string; last_name: string; company: string; title: string;
  website: string; linkedin_url: string; notes: string; source: string; status: string;
  icp_score: number | null; created_at: string; updated_at: string;
}
export interface LeadDetail extends Lead {
  brief: Record<string, unknown> | null;
  firmographics: Record<string, unknown> | null;
}
export interface LeadPage { items: Lead[]; total: number; limit: number; offset: number }
export interface ImportResult { created: number; skipped: number; errors: { row: number; error: string }[] }

export interface Step {
  id: string; seq: number; agent: string; status: "pending" | "running" | "succeeded" | "failed" | "skipped";
  model: string | null; input: Record<string, unknown>; output: Record<string, unknown> | null;
  tool_calls: { tool: string; ok: boolean; result?: unknown; error?: string }[];
  error: string | null; attempts: number; tokens_in: number; tokens_out: number; cost_usd: number;
  latency_ms: number; started_at: string | null; finished_at: string | null;
}
export interface Approval {
  id: string; run_id: string; lead_id: string; kind: "sequence" | "reply"; step_number: number;
  to_email: string; subject: string; body: string; scheduled_at: string; status: string;
  reviewed_at: string | null; sent_at: string | null; error: string | null; created_at: string;
  lead_name: string | null; lead_company: string | null;
}
export interface Run {
  id: string; lead_id: string; kind: "outreach" | "triage"; status: string; campaign: string; error: string | null;
  total_tokens: number; total_cost_usd: number; created_at: string; finished_at: string | null;
  lead_email: string | null; lead_company: string | null;
}
export interface RunDetail extends Run { steps: Step[]; approvals: Approval[] }
export interface Reply {
  id: string; lead_id: string; run_id: string | null; source: string; body: string;
  classification: string | null; confidence: number | null; summary: string | null; created_at: string;
}

export interface Stats {
  kpis: {
    total_leads: number; pending_approvals: number; emails_sent: number; reply_rate: number;
    total_runs: number; active_runs: number; avg_icp_score: number | null;
  };
  funnel: { stage: string; count: number }[];
  runs_per_day: { date: string; runs: number }[];
  usage: { tokens: number; cost_usd: number; calls: number; limit: number };
}
export interface Usage {
  tokens: number; tokens_in: number; tokens_out: number; cost_usd: number; calls: number; limit: number;
  period_start: string;
  by_agent: { agent: string; tokens: number; cost_usd: number; calls: number }[];
  daily: { date: string; tokens: number; cost_usd: number }[];
}
export interface OrgSettings {
  icp: { industries: string[]; min_employees: number | null; max_employees: number | null; regions: string[] };
  sender_name: string; product_pitch: string;
}
export interface OrgFull {
  id: string; name: string; slug: string; role: string; monthly_token_limit: number;
  settings: OrgSettings; webhook_token: string | null;
}
export interface Member { user_id: string; email: string; name: string; role: string; created_at: string }
export interface Invite { id: string; email: string; role: string; token: string; accepted: boolean; created_at: string }
export interface Integrations {
  llm: { provider: string; configured: boolean; models: Record<string, string> };
  email: { provider: string; from: string; configured: boolean };
  oauth: Record<string, boolean>;
  queue: { backend: string };
  web_tools: boolean;
}
export interface AgentInfo { name: string; description: string; depends_on: string[]; uses_llm: boolean; tools: { name: string; description: string }[] }
