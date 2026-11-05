"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";

export default function OAuthCallback() {
  const { acceptTokens } = useAuth();
  const router = useRouter();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const p = new URLSearchParams(window.location.hash.slice(1));
    const access_token = p.get("access_token");
    const refresh_token = p.get("refresh_token");
    window.history.replaceState(null, "", window.location.pathname);
    if (!access_token || !refresh_token) {
      setFailed(true);
      return;
    }
    acceptTokens({ access_token, refresh_token }).then(() => router.replace("/dashboard"));
  }, [acceptTokens, router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
      {failed ? <a className="text-primary underline" href="/login">Sign-in failed. Back to login</a> : <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Signing you in...</>}
    </div>
  );
}
