"use client";
import { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export function Dialog({ open, onClose, title, description, children, className }: {
  open: boolean; onClose: () => void; title: string; description?: string; children: React.ReactNode; className?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className={cn("glass relative max-h-[90vh] w-full overflow-y-auto rounded-b-none bg-card p-6 animate-fade-in sm:max-w-lg sm:rounded-b-2xl", className)}>
        <button onClick={onClose} aria-label="Close" className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
        <h2 className="text-lg font-semibold">{title}</h2>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}
