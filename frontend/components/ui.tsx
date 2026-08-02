import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5",
        className
      )}
    >
      {children}
    </div>
  );
}

export function Button({
  className,
  variant = "primary",
  type = "button",
  disabled,
  onClick,
  children,
}: {
  className?: string;
  variant?: "primary" | "ghost" | "danger" | "outline";
  type?: "button" | "submit";
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
}) {
  const variants = {
    primary:
      "bg-indigo-500 text-white hover:bg-indigo-400 disabled:bg-indigo-500/40 shadow-sm shadow-indigo-900/40",
    outline:
      "border border-zinc-700 text-zinc-200 hover:bg-zinc-800 disabled:opacity-50",
    ghost: "text-zinc-300 hover:bg-zinc-800 disabled:opacity-50",
    danger: "bg-red-500/15 text-red-400 hover:bg-red-500/25 disabled:opacity-50",
  };
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
        variants[variant],
        className
      )}
    >
      {children}
    </button>
  );
}

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-colors focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20",
        className
      )}
      {...props}
    />
  );
}

export function Label({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("mb-1.5 block text-xs font-medium text-zinc-400", className)}>
      {children}
    </label>
  );
}

export function Badge({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-zinc-700 bg-zinc-800/80 px-2.5 py-0.5 text-xs font-medium text-zinc-300",
        className
      )}
    >
      {children}
    </span>
  );
}

export function MatchBadge({ score }: { score: number }) {
  const color =
    score >= 75
      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
      : score >= 55
        ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
        : "bg-zinc-700/40 text-zinc-300 border-zinc-600";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-semibold",
        color
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {score.toFixed(0)}% match
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-indigo-400",
        className
      )}
    />
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-700 bg-zinc-900/40 px-6 py-14 text-center">
      <div className="mb-3 text-3xl">{icon ?? "📭"}</div>
      <h3 className="text-base font-semibold text-zinc-100">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-zinc-400">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    applied: "bg-sky-500/15 text-sky-400 border-sky-500/30",
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    interview: "bg-violet-500/15 text-violet-400 border-violet-500/30",
    rejected: "bg-red-500/15 text-red-400 border-red-500/30",
    offer: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    withdrawn: "bg-zinc-700/40 text-zinc-400 border-zinc-600",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
        map[status] ?? map.pending
      )}
    >
      {status}
    </span>
  );
}
