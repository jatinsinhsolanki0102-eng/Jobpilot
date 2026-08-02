"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, formatSalary } from "@/lib/api";
import type { DashboardStats } from "@/lib/types";
import {
  Card,
  MatchBadge,
  StatusBadge,
  Spinner,
  EmptyState,
  Button,
} from "@/components/ui";
import { cn } from "@/lib/utils";
import { timeAgo } from "@/lib/utils";

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent?: string;
}) {
  return (
    <Card className="flex flex-col gap-1">
      <span className="text-xs font-medium text-zinc-500">{label}</span>
      <span className={cn("text-3xl font-bold", accent ?? "text-zinc-100")}>
        {value}
      </span>
    </Card>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<DashboardStats>("/api/v1/dashboard/stats")
      .then(setStats)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load dashboard")
      );
  }, []);

  if (error) {
    return (
      <EmptyState
        icon="⚠️"
        title="Couldn't load the dashboard"
        description={error}
      />
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center py-24 text-zinc-500">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Your job search at a glance
          </p>
        </div>
        <Link href="/jobs">
          <Button>Browse ranked jobs</Button>
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-7">
        <StatCard label="Total jobs" value={stats.total_jobs} />
        <StatCard label="Applied" value={stats.applied} accent="text-sky-400" />
        <StatCard label="Pending" value={stats.pending} accent="text-amber-400" />
        <StatCard label="Interviews" value={stats.interviews} accent="text-violet-400" />
        <StatCard label="Offers" value={stats.offers} accent="text-emerald-400" />
        <StatCard label="Rejected" value={stats.rejected} accent="text-red-400" />
        <StatCard label="Saved" value={stats.saved} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-0">
          <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
            <h2 className="font-semibold">Top matches for you</h2>
            <Link
              href="/jobs"
              className="text-xs font-medium text-indigo-400 hover:text-indigo-300"
            >
              View all →
            </Link>
          </div>
          {stats.top_matches.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-zinc-500">
              {stats.applied > 0
                ? "You've applied to your top matches. New opportunities will show here."
                : "Upload a resume to see AI-ranked matches."}
            </div>
          ) : (
            <ul className="divide-y divide-zinc-800">
              {stats.top_matches.map((m) => (
                <li key={m.id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/jobs/${m.id}`}
                        className="font-medium text-zinc-100 hover:text-indigo-300"
                      >
                        {m.title}
                      </Link>
                      <p className="mt-0.5 text-sm text-zinc-500">
                        {m.company_name}
                        {m.location ? ` · ${m.location}` : ""}
                        {m.work_mode ? ` · ${m.work_mode}` : ""}
                      </p>
                      <p className="mt-0.5 text-xs text-zinc-600">
                        {formatSalary(m.salary_min, m.salary_max)} ·{" "}
                        {m.matched_skills.slice(0, 3).join(", ")}
                      </p>
                    </div>
                    <MatchBadge score={m.match_score} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-0">
          <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
            <h2 className="font-semibold">Recent applications</h2>
            <Link
              href="/applications"
              className="text-xs font-medium text-indigo-400 hover:text-indigo-300"
            >
              View all →
            </Link>
          </div>
          {stats.recent_applications.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-zinc-500">
              No applications yet.{" "}
              <Link href="/jobs" className="text-indigo-400 hover:text-indigo-300">
                Find your first match
              </Link>
              .
            </div>
          ) : (
            <ul className="divide-y divide-zinc-800">
              {stats.recent_applications.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-3 px-5 py-4">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-zinc-100">
                      {a.job_title}
                    </p>
                    <p className="text-sm text-zinc-500">
                      {a.company_name} · {timeAgo(a.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={a.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {stats.top_skills.length > 0 && (
        <Card>
          <h2 className="mb-4 font-semibold">Skills on your resume</h2>
          <div className="flex flex-wrap gap-2">
            {stats.top_skills.map((s) => (
              <span
                key={s.category}
                className="inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-800/60 px-3 py-1 text-sm text-zinc-300"
              >
                {s.category}
                <span className="rounded-full bg-indigo-500/20 px-1.5 text-xs font-semibold text-indigo-300">
                  {s.count}
                </span>
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
