import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "@/components/ui/toast";

export const metadata: Metadata = {
  title: "RevOps Agent Platform",
  description: "Autonomous multi-agent sales pipeline with a human approval gate.",
};

const themeScript = `try{if(localStorage.getItem('revops.theme')==='light')document.documentElement.classList.add('light')}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body className="min-h-screen font-sans">
        <ToastProvider>
          <AuthProvider>{children}</AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
