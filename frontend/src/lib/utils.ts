import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtNumber(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: n >= 100000 ? "compact" : "standard" }).format(n);
}

export function fmtCost(n: number): string {
  return n < 0.01 && n > 0 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}

export function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "-";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 0) return `in ${fmtDuration(-diff)}`;
  if (diff < 45) return "just now";
  return `${fmtDuration(diff)} ago`;
}

function fmtDuration(s: number): string {
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("") || "?";
}
