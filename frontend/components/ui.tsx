"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import type { FindingStatus, ReportStatus } from "@/lib/api";

/* ---------------------------------------------------------------- shell */
export function Shell({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth();
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="border-b bg-background sticky top-0 z-10">
        <div className="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-3">
            <Logomark />
            <span className="text-lg font-semibold tracking-tight text-foreground">MediSense AI</span>
          </Link>
          {user && (
            <div className="flex items-center gap-6 text-sm">
              <span className="text-muted-foreground hidden sm:inline font-medium">{user.email}</span>
              <button
                onClick={signOut}
                className="text-muted-foreground hover:text-foreground font-medium transition-colors"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="flex-1 w-full bg-background">
        <div className="mx-auto max-w-6xl px-6 py-8">{children}</div>
      </main>
      <footer className="border-t bg-muted/30">
        <div className="mx-auto max-w-6xl px-6 py-6 text-sm text-muted-foreground text-center">
          MediSense AI explains reports; it does not diagnose. Always confirm findings with a licensed clinician.
        </div>
      </footer>
    </div>
  );
}

import { Stethoscope } from "./Icons";

export function Logomark({ size = 26 }: { size?: number }) {
  return (
    <div className="flex items-center justify-center bg-primary rounded-lg shadow-sm" style={{ width: size, height: size }}>
      <Stethoscope className="text-primary-foreground" width={size * 0.65} height={size * 0.65} />
    </div>
  );
}

/* ---------------------------------------------------------------- buttons */
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  busy?: boolean;
};

export function Button({ variant = "primary", busy, className = "", children, disabled, ...rest }: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 h-10 px-4 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm";
  const styles = {
    primary: "bg-primary text-primary-foreground hover:bg-primary/90",
    secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
    ghost: "hover:bg-accent hover:text-accent-foreground shadow-none",
    danger: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
  }[variant];
  return (
    <button className={`${base} ${styles} ${className}`} disabled={disabled || busy} {...rest}>
      {busy && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={`animate-spin h-4 w-4 ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/* ---------------------------------------------------------------- forms */
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-foreground mb-1.5">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted-foreground mt-1.5">{hint}</span>}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full h-10 px-3 rounded-md border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-shadow ${props.className ?? ""}`}
    />
  );
}

export function Notice({ kind = "error", children }: { kind?: "error" | "info"; children: React.ReactNode }) {
  const styles = kind === "error" ? "bg-status-critical-bg text-status-critical border-status-critical/20" : "bg-primary/10 text-primary border-primary/20";
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-md border px-4 py-3 text-sm font-medium ${styles}`}>
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------- status */
export const STATUS_LABEL: Record<ReportStatus, string> = {
  uploaded: "Uploaded",
  extracting: "Extracting text",
  extracted: "Text extracted",
  analyzing: "Analyzing",
  analyzed: "Analyzed",
  failed: "Needs attention",
};

export function StatusDot({ status }: { status: ReportStatus }) {
  let color = "bg-primary";
  if (status === "failed") color = "bg-status-critical";
  else if (status === "analyzed") color = "bg-status-normal";
  else if (status === "uploaded") color = "bg-muted-foreground";

  const live = status === "extracting" || status === "analyzing";
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${color} ${live ? "animate-pulse" : ""}`} aria-hidden="true" />;
}

export function findingColor(status: FindingStatus): { bar: string; text: string; word: string; bg: string; badge: string } {
  switch (status) {
    case "low":
      return { bar: "bg-status-caution", text: "text-status-caution", word: "Low", bg: "bg-status-caution-bg", badge: "bg-status-caution/10 text-status-caution border-status-caution/20" };
    case "high":
      return { bar: "bg-status-critical", text: "text-status-critical", word: "High", bg: "bg-status-critical-bg", badge: "bg-status-critical/10 text-status-critical border-status-critical/20" };
    case "abnormal":
      return { bar: "bg-status-abnormal", text: "text-status-abnormal", word: "Abnormal", bg: "bg-status-abnormal-bg", badge: "bg-status-abnormal/10 text-status-abnormal border-status-abnormal/20" };
    case "normal":
      return { bar: "bg-status-normal", text: "text-status-normal", word: "Normal", bg: "bg-status-normal-bg", badge: "bg-status-normal/10 text-status-normal border-status-normal/20" };
    default:
      return { bar: "bg-muted", text: "text-muted-foreground", word: "Not graded", bg: "bg-muted/50", badge: "bg-muted text-muted-foreground border-muted/20" };
  }
}

export function StatCard({ label, value, icon: Icon }: { label: string; value: string | number; icon?: React.ElementType }) {
  return (
    <div className="bg-background border border-border rounded-xl p-5 shadow-sm flex flex-col gap-1 relative overflow-hidden group">
      {Icon && <div className="absolute -right-4 -bottom-4 opacity-[0.03] text-foreground pointer-events-none group-hover:scale-110 group-hover:rotate-0 transform -rotate-12 transition-transform duration-700 ease-out z-0"><Icon className="w-24 h-24" /></div>}
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground relative z-10">
        {Icon && <Icon className="w-4 h-4" />}
        {label}
      </div>
      <div className="text-3xl font-bold tracking-tight text-foreground relative z-10">{value}</div>
    </div>
  );
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
