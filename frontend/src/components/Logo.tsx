import { Workflow } from "lucide-react";
import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent shadow-lg shadow-primary/30">
        <Workflow className="h-4.5 w-4.5 text-white" size={18} />
      </span>
      RevOps<span className="text-muted-foreground">Agents</span>
    </span>
  );
}
