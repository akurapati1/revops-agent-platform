"use client";
import { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";

interface Toast { id: number; kind: "ok" | "err"; text: string }
const Ctx = createContext<(kind: Toast["kind"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, kind, text }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 4500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="glass flex items-start gap-3 bg-card p-3 text-sm animate-fade-in">
            {t.kind === "ok" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
export const useToast = () => useContext(Ctx);
