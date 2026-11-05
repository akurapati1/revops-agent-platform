"use client";
import { cn } from "@/lib/utils";

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="mb-6 flex gap-1 overflow-x-auto rounded-xl border bg-card/60 p-1" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cn("whitespace-nowrap rounded-lg px-4 py-1.5 text-sm font-medium transition", value === t.id ? "bg-primary/20 text-foreground shadow-inner" : "text-muted-foreground hover:text-foreground")}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
